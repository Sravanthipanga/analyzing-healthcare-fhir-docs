"""The observability store: one object the service writes to and the
API reads from, plus the Prometheus exposition for scraping."""

from __future__ import annotations

import threading

from .cost import CostLedger
from .latency import LatencyTracker
from .quality import QualityTracker
from .tracing import Tracer


class ObservabilityStore:
    def __init__(self) -> None:
        self.tracer = Tracer()
        self.latency = LatencyTracker()
        self.cost = CostLedger()
        self.quality = QualityTracker()

    def snapshot(self) -> dict:
        return {
            "latency": self.latency.snapshot(),
            "cost": self.cost.snapshot(),
            "quality": self.quality.snapshot(),
            "tracing": {
                "otel_bridge_active": self.tracer.otel_active,
                "trace_file": self.tracer.trace_file_path(),
            },
        }

    def prometheus(self) -> str:
        """Prometheus text exposition for the measured window."""
        snap = self.snapshot()
        lines: list[str] = []
        for stage, s in snap["latency"].items():
            safe = stage.replace("-", "_")
            lines.append(f"# TYPE askfhir_stage_latency_ms summary")
            lines.append(f'askfhir_stage_requests{{stage="{safe}"}} {s["count"]}')
            lines.append(f'askfhir_stage_latency_p50_ms{{stage="{safe}"}} {s["p50_ms"]}')
            lines.append(f'askfhir_stage_latency_p95_ms{{stage="{safe}"}} {s["p95_ms"]}')
            lines.append(f'askfhir_stage_latency_p99_ms{{stage="{safe}"}} {s["p99_ms"]}')
        cost = snap["cost"]
        if cost.get("requests"):
            lines.append(f"askfhir_cost_total_usd {cost['total_usd']}")
            lines.append(f"askfhir_cost_mean_usd {cost['mean_usd']}")
            lines.append(f"askfhir_cost_p95_usd {cost['p95_usd']}")
            lines.append(f"askfhir_cost_per_1k_requests_usd {cost['per_1k_requests_usd']}")
        quality = snap["quality"]
        if quality.get("requests"):
            lines.append(f"askfhir_requests_total {quality['requests']}")
            lines.append(f"askfhir_abstention_rate {quality['abstention_rate']}")
            lines.append(f"askfhir_fallback_rate {quality['fallback_rate']}")
            lines.append(f"askfhir_citations_per_answer {quality['citations_per_answer']}")
        return "\n".join(lines) + "\n"


_store: ObservabilityStore | None = None
_lock = threading.Lock()


def get_store() -> ObservabilityStore:
    global _store
    if _store is None:
        with _lock:
            if _store is None:
                _store = ObservabilityStore()
    return _store
