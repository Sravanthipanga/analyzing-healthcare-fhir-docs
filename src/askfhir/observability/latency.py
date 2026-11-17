"""Latency tracking: per-stage and end-to-end percentile budgets.

Averages hide the tail, and the tail is where users live. Every stage
keeps a bounded sample window; snapshots report p50 / p95 / p99 so a
regression in the reranker (say) is visible as *its* p95 moving, not
just a vaguer, slower product.
"""

from __future__ import annotations

import threading
from collections import defaultdict, deque


def percentile(samples: list[float], pct: float) -> float:
    """Nearest-rank percentile; 0.0 for an empty sample set."""
    if not samples:
        return 0.0
    ordered = sorted(samples)
    rank = max(1, int(round(pct / 100.0 * len(ordered))))
    return ordered[min(rank, len(ordered)) - 1]


class LatencyTracker:
    def __init__(self, window: int = 1000):
        self._lock = threading.Lock()
        self._samples: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=window)
        )

    def record(self, stage: str, duration_ms: float) -> None:
        with self._lock:
            self._samples[stage].append(duration_ms)

    def snapshot(self) -> dict:
        with self._lock:
            data = {k: list(v) for k, v in self._samples.items()}
        out = {}
        for stage, samples in sorted(data.items()):
            if not samples:
                continue
            out[stage] = {
                "count": len(samples),
                "mean_ms": round(sum(samples) / len(samples), 3),
                "p50_ms": round(percentile(samples, 50), 3),
                "p95_ms": round(percentile(samples, 95), 3),
                "p99_ms": round(percentile(samples, 99), 3),
                "max_ms": round(max(samples), 3),
            }
        return out
