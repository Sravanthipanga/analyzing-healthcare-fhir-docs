"""Regression gate: fail CI when quality, latency, or cost regress.

The threshold gate in ``run_eval.py`` asks "is the system good enough?"
This gate asks the production question: "is it *worse than the last
known-good build*?" It compares ``eval/report.json`` against the frozen
baseline in ``eval/baseline.json``:

- **Quality** — each metric must stay within its tolerance of baseline
  (a 1.00 hit@5 baseline with 0.02 tolerance fails at 0.97).
- **Latency** — end-to-end p95 must stay within the headroom factor of
  baseline p95 (default +25%) so a slow reranker can't sneak in.
- **Cost** — mean cost per request must stay within the headroom factor
  of baseline, so a pricier model swap shows up as a red build, not a
  surprise invoice.

Usage:  python eval/regression_gate.py [--report PATH] [--baseline PATH]
Exit code 1 on any regression. Update the baseline deliberately, in its
own commit, when a change is *intended* to move these numbers.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

DEFAULT_TOLERANCES = {
    "hit@5": 0.02,
    "mrr@5": 0.02,
    "citation_precision": 0.05,
    "abstention_accuracy": 0.02,
    "keyword_recall": 0.03,
}


def check(report: dict, baseline: dict) -> list[str]:
    failures: list[str] = []
    metrics = report.get("metrics", {})
    base_metrics = baseline.get("metrics", {})
    tolerances = {**DEFAULT_TOLERANCES, **baseline.get("tolerances", {})}
    for name, base_value in base_metrics.items():
        if name not in metrics:
            failures.append(f"quality: {name} missing from report")
            continue
        floor = base_value - tolerances.get(name, 0.02)
        if metrics[name] < floor:
            failures.append(
                f"quality: {name} {metrics[name]:.4f} < baseline floor "
                f"{floor:.4f} (baseline {base_value:.4f} - tol "
                f"{tolerances.get(name, 0.02)})"
            )

    headroom = float(baseline.get("headroom_factor", 1.25))
    obs = report.get("observability", {})
    base_obs = baseline.get("observability", {})

    rep_p95 = obs.get("latency", {}).get("ask", {}).get("p95_ms")
    base_p95 = base_obs.get("latency", {}).get("ask", {}).get("p95_ms")
    if base_p95 is not None:
        if rep_p95 is None:
            failures.append("latency: report has no ask p95 (observability missing)")
        elif rep_p95 > base_p95 * headroom:
            failures.append(
                f"latency: ask p95 {rep_p95:.1f} ms > baseline "
                f"{base_p95:.1f} ms x {headroom}"
            )

    rep_cost = obs.get("cost", {}).get("mean_usd")
    base_cost = base_obs.get("cost", {}).get("mean_usd")
    if base_cost:
        if rep_cost is None:
            failures.append("cost: report has no mean cost per request")
        elif rep_cost > base_cost * headroom:
            failures.append(
                f"cost: mean ${rep_cost:.6f}/request > baseline "
                f"${base_cost:.6f} x {headroom}"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=str(BASE / "eval" / "report.json"))
    parser.add_argument("--baseline", default=str(BASE / "eval" / "baseline.json"))
    args = parser.parse_args()

    report = json.loads(Path(args.report).read_text())
    baseline = json.loads(Path(args.baseline).read_text())
    failures = check(report, baseline)
    if failures:
        print("REGRESSION GATE FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("REGRESSION GATE PASSED: quality, latency, and cost within "
          "baseline tolerances.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
