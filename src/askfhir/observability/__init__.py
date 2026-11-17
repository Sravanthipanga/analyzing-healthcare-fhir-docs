"""Observability for AskFHIR: tracing, latency, cost, and quality metrics.

Production AI systems fail silently — retrieval rots, latencies creep,
costs drift, answer quality decays — unless every request is measured.
This package instruments the RAG pipeline with:

- **Tracing** — OpenTelemetry-semantic spans for every pipeline stage
  (``ask`` -> ``bm25_search`` / ``embed_query`` / ``vector_search`` /
  ``fusion`` / ``rerank`` / ``compose``), exportable as JSONL and, when the
  OpenTelemetry SDK is installed, bridged to any OTLP collector
  (Jaeger, Tempo, Langfuse, Phoenix, Datadog, ...).
- **Latency tracking** — per-stage and end-to-end p50 / p95 / p99.
- **Cost per request** — a priced ledger: local ONNX compute is billed
  per CPU-second; API-shaped stages (embedding / LLM) are billed per
  token from a configurable price table.
- **Quality signals** — abstention rate, citation density, fallback and
  empty-result rates: the online proxies that catch quality regressions
  between offline eval runs.

Everything is dependency-light (stdlib only). The OpenTelemetry bridge
activates automatically when ``opentelemetry-sdk`` is installed and
``OTEL_EXPORTER_OTLP_ENDPOINT`` is set.
"""

from .cost import CostLedger, CostRecord, PriceTable
from .latency import LatencyTracker, percentile
from .quality import QualityTracker
from .store import ObservabilityStore, get_store
from .tracing import Span, Tracer

__all__ = [
    "CostLedger",
    "CostRecord",
    "LatencyTracker",
    "ObservabilityStore",
    "PriceTable",
    "QualityTracker",
    "Span",
    "Tracer",
    "get_store",
    "percentile",
]
