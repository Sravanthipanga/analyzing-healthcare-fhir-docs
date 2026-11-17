"""Regression gate: quality / latency / cost vs the frozen baseline."""

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "eval"))

from regression_gate import check  # noqa: E402

BASELINE = {
    "metrics": {"hit@5": 1.0, "mrr@5": 0.9655, "citation_precision": 0.70,
                "abstention_accuracy": 1.0},
    "observability": {
        "latency": {"ask": {"p95_ms": 100.0}},
        "cost": {"mean_usd": 0.001},
    },
    "headroom_factor": 1.25,
}


def _report(metrics=None, p95=100.0, cost=0.001):
    return {
        "metrics": metrics or dict(BASELINE["metrics"]),
        "observability": {
            "latency": {"ask": {"p95_ms": p95}},
            "cost": {"mean_usd": cost},
        },
    }


def test_gate_passes_at_baseline():
    assert check(_report(), BASELINE) == []


def test_gate_fails_on_quality_regression():
    metrics = dict(BASELINE["metrics"])
    metrics["hit@5"] = 0.90  # tolerance 0.02 -> floor 0.98
    failures = check(_report(metrics=metrics), BASELINE)
    assert any("hit@5" in f for f in failures)


def test_gate_allows_small_quality_dip_within_tolerance():
    metrics = dict(BASELINE["metrics"])
    metrics["citation_precision"] = 0.66  # tolerance 0.05 -> floor 0.65
    assert check(_report(metrics=metrics), BASELINE) == []


def test_gate_fails_on_latency_regression():
    failures = check(_report(p95=200.0), BASELINE)  # cap is 125 ms
    assert any("latency" in f for f in failures)


def test_gate_fails_on_cost_regression():
    failures = check(_report(cost=0.002), BASELINE)  # cap is 0.00125
    assert any("cost" in f for f in failures)


def test_gate_fails_when_observability_missing():
    report = {"metrics": dict(BASELINE["metrics"])}
    failures = check(report, BASELINE)
    assert any("latency" in f for f in failures)
    assert any("cost" in f for f in failures)
