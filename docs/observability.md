# Observability — design notes

## Why this layer exists

A RAG system has four production failure modes that unit tests cannot
see: retrieval quality rots as the corpus or models drift, tail latency
creeps as stages get slower, cost per request climbs with pricier
models or longer contexts, and answer quality decays silently. This
layer measures all four on every request and gates CI on regressions.

## What is measured

| Signal | Where | How |
|---|---|---|
| Traces | `observability/tracing.py` | One trace per `/ask`; spans per stage with model names, candidate counts, top rerank score, abstention + citation counts on the root span |
| Latency | `observability/latency.py` | Rolling 1,000-sample window per stage; p50/p95/p99 + mean + max |
| Cost | `observability/cost.py` | Per-span billing settled per request. Local ONNX stages: USD per CPU-second. API-shaped stages: USD per 1K tokens processed. Price table in code, overridable via `ASKFHIR_PRICE_TABLE` JSON env |
| Quality | `observability/quality.py` | Abstention rate, citations per answer, citation-validation fallback rate, empty-result rate |

## Exports

- `GET /observability` — JSON snapshot of all three trackers.
- `GET /observability/traces?limit=N` — recent traces with nested spans.
- `GET /observability/dashboard` — self-refreshing HTML page.
- `GET /metrics` — Prometheus text exposition (stage latency gauges,
  cost counters, quality rates) for scraping into Grafana.
- JSONL span export when `ASKFHIR_TRACE_FILE` is set.
- OpenTelemetry bridge: install the `observability` extra and set
  `OTEL_EXPORTER_OTLP_ENDPOINT` to mirror spans into Jaeger, Tempo,
  Langfuse, Arize Phoenix, or any OTLP collector. The bridge is
  best-effort by design — if the collector or SDK is unavailable, the
  app keeps serving and the local trackers keep recording.

## Regression gating

`eval/run_eval.py` writes quality metrics **and** an observability
snapshot (latency percentiles + cost over the golden set) into
`eval/report.json`. `eval/regression_gate.py` then compares the report
with `eval/baseline.json`:

- quality metrics may not fall more than their tolerance below baseline,
- end-to-end p95 latency may not exceed baseline × 1.25,
- mean cost per request may not exceed baseline × 1.25.

CI runs both gates. Updating the baseline is a deliberate act: run the
eval, inspect the diff, and commit the new baseline on its own when a
change is *supposed* to move the numbers (a bigger embedder, a new
reranker) — the same discipline as updating a golden snapshot.

## Honest limits

- Token counts are estimates (~4 chars/token) of *processed* text; the
  composer is extractive, so "compose" cost models what an LLM would
  charge for the same context, which is exactly the comparison a team
  needs before swapping one in.
- Local compute pricing uses a flat cloud-core rate; it exists to make
  relative regressions visible, not to produce an invoice.
- Online quality signals are proxies. The golden eval remains the
  ground truth; the proxies exist to catch fires between eval runs.
