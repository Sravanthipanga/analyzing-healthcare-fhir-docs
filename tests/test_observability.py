"""Observability: tracing, latency percentiles, cost, quality, endpoints."""

import time

from fastapi.testclient import TestClient

from askfhir.api import create_app
from askfhir.chunking import load_corpus
from askfhir.embeddings import FakeEmbedder
from askfhir.observability import (
    CostLedger,
    LatencyTracker,
    ObservabilityStore,
    PriceTable,
    QualityTracker,
    Tracer,
    percentile,
)
from askfhir.reranker import FakeReranker
from askfhir.service import AskFHIRService

from conftest import CORPUS_DIR


def _service(store=None) -> AskFHIRService:
    chunks = load_corpus(CORPUS_DIR)
    embedder = FakeEmbedder()
    emb = embedder.embed([c.index_text() for c in chunks])
    return AskFHIRService(chunks, emb, embedder, FakeReranker(),
                          fake_models=True, store=store or ObservabilityStore())


# ------------------------------------------------------------------ latency
def test_percentile_nearest_rank():
    samples = [float(i) for i in range(1, 101)]
    assert percentile(samples, 50) == 50.0
    assert percentile(samples, 95) == 95.0
    assert percentile([], 95) == 0.0


def test_latency_tracker_snapshot():
    tracker = LatencyTracker()
    for ms in (10.0, 20.0, 30.0, 40.0):
        tracker.record("rerank", ms)
    snap = tracker.snapshot()["rerank"]
    assert snap["count"] == 4
    assert snap["p50_ms"] == 20.0
    assert snap["max_ms"] == 40.0


# ------------------------------------------------------------------ tracing
def test_tracer_nests_spans_under_one_trace():
    tracer = Tracer()
    with tracer.span("ask") as root:
        with tracer.span("rerank"):
            time.sleep(0.001)
    traces = tracer.recent_traces()
    assert len(traces) == 1
    trace = traces[0]
    assert trace["trace_id"] == root.trace_id
    assert trace["root"] == "ask"
    assert [s["name"] for s in trace["spans"]] == ["ask", "rerank"]
    assert trace["duration_ms"] > 0


def test_tracer_error_status():
    tracer = Tracer()
    try:
        with tracer.span("boom"):
            raise ValueError("nope")
    except ValueError:
        pass
    assert tracer.recent_traces()[0]["spans"][0]["status"] == "error"


# ---------------------------------------------------------------------- cost
def test_cost_ledger_compute_and_token_billing():
    ledger = CostLedger(prices=PriceTable(compute_per_second=0.001,
                                          tokens_per_1k={"compose": 0.01}))
    ledger.bill_span("t1", "rerank", duration_ms=2000.0)          # compute
    ledger.bill_span("t1", "compose", duration_ms=5.0, tokens=2000)  # tokens
    record = ledger.settle("t1")
    assert record.stages["rerank"]["usd"] == 0.002
    assert record.stages["compose"]["usd"] == 0.02
    assert abs(record.total_usd - 0.022) < 1e-12
    snap = ledger.snapshot()
    assert snap["requests"] == 1
    assert snap["per_1k_requests_usd"] == 22.0


def test_cost_ledger_ignores_unpriced_stages():
    ledger = CostLedger()
    ledger.bill_span("t1", "fusion", duration_ms=100.0)
    assert ledger.settle("t1").total_usd == 0.0


# ------------------------------------------------------------------- quality
def test_quality_tracker_rates():
    quality = QualityTracker()
    quality.record(abstained=False, citations=2, sources=5, fallback_used=False)
    quality.record(abstained=True, citations=0, sources=0, fallback_used=False)
    quality.record(abstained=False, citations=1, sources=3, fallback_used=True)
    snap = quality.snapshot()
    assert snap["requests"] == 3
    assert snap["abstention_rate"] == round(1 / 3, 4)
    assert snap["empty_rate"] == round(1 / 3, 4)
    assert snap["fallback_rate"] == round(1 / 3, 4)
    assert snap["citations_per_answer"] == 1.5


# ------------------------------------------------------------------- service
def test_ask_is_instrumented():
    store = ObservabilityStore()
    svc = _service(store)
    result = svc.ask("What is a transaction Bundle in FHIR?")
    assert result["trace_id"]
    assert result["observability"]["latency_ms"] > 0
    assert result["observability"]["cost_usd"] > 0
    snap = store.snapshot()
    assert snap["quality"]["requests"] == 1
    assert "ask" in snap["latency"]
    assert "rerank" in snap["latency"]
    assert snap["cost"]["requests"] == 1
    traces = store.tracer.recent_traces()
    assert traces[0]["root"] == "ask"
    stage_names = {s["name"] for s in traces[0]["spans"]}
    assert {"bm25_search", "embed_query", "vector_search", "rerank"} <= stage_names


def test_stage_latencies_are_nonzero_after_real_ask():
    """Regression: stage latency/cost must be recorded AFTER the span
    closes. Reading span.duration_ms inside the span yields 0.0, which
    silently zeroed every per-stage p50/p95 in the first shipped version."""
    import time

    class SlowReranker(FakeReranker):
        def score(self, query, texts):
            time.sleep(0.01)
            return super().score(query, texts)

    store = ObservabilityStore()
    chunks = load_corpus(CORPUS_DIR)
    embedder = FakeEmbedder()
    emb = embedder.embed([c.index_text() for c in chunks])
    svc = AskFHIRService(chunks, emb, embedder, SlowReranker(),
                         fake_models=True, store=store)
    svc.ask("What is a transaction Bundle in FHIR?")
    snap = store.snapshot()
    assert snap["latency"]["rerank"]["p50_ms"] > 0
    assert snap["latency"]["rerank"]["max_ms"] >= 10.0
    assert snap["cost"]["by_stage"]["rerank"] > 0


def test_ask_abstention_is_instrumented():
    store = ObservabilityStore()
    svc = _service(store)
    result = svc.ask("   ")  # empty question always abstains
    assert result["abstained"] is True
    assert result["trace_id"]
    assert store.snapshot()["quality"]["abstention_rate"] == 1.0


# ----------------------------------------------------------------------- api
def test_observability_endpoints():
    svc = _service()
    client = TestClient(create_app(service=svc))
    client.post("/ask", json={"question": "What is a transaction Bundle in FHIR?"})
    snap = client.get("/observability").json()
    assert snap["quality"]["requests"] >= 1
    assert "latency" in snap and "cost" in snap
    traces = client.get("/observability/traces").json()
    assert traces and traces[0]["root"] == "ask"
    metrics = client.get("/metrics").text
    assert "askfhir_cost_total_usd" in metrics
    assert "askfhir_stage_latency_p95_ms" in metrics
    page = client.get("/observability/dashboard")
    assert page.status_code == 200
    assert "Observability" in page.text
