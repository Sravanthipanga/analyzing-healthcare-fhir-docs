"""Cost per request: a priced ledger for every pipeline stage.

"You can't manage what you don't meter." Each request is billed from a
price table with two kinds of rates:

- **compute** — local ONNX stages (embedding, reranking) billed per
  CPU-second, the honest way to price self-hosted inference;
- **tokens** — API-shaped stages billed per 1K tokens, so swapping the
  extractive composer for a hosted LLM (or the local embedder for a
  hosted embedding API) prices itself correctly with no code change.

Rates are overridable with the ``ASKFHIR_PRICE_TABLE`` env var (JSON),
because prices change faster than code should.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field

# Rough token estimate for English text (~4 chars/token). The composer is
# extractive, so token counts measure *processed* text: what an LLM would
# have been billed for with the same prompts and context.
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


@dataclass
class PriceTable:
    # USD per CPU-second for local model stages.
    compute_per_second: float = 0.0004  # ~ a $1.44/hr core, cloud list price
    # USD per 1K tokens for API-shaped stages, keyed by stage name.
    tokens_per_1k: dict = field(
        default_factory=lambda: {
            "embed_query": 0.00002,  # hosted embedding API territory
            "compose": 0.005,  # hosted LLM output territory
        }
    )

    @classmethod
    def from_env(cls) -> "PriceTable":
        raw = os.environ.get("ASKFHIR_PRICE_TABLE")
        if not raw:
            return cls()
        try:
            data = json.loads(raw)
            table = cls()
            if "compute_per_second" in data:
                table.compute_per_second = float(data["compute_per_second"])
            if "tokens_per_1k" in data:
                table.tokens_per_1k.update(
                    {k: float(v) for k, v in data["tokens_per_1k"].items()}
                )
            return table
        except (ValueError, TypeError):
            return cls()


@dataclass
class CostRecord:
    trace_id: str
    total_usd: float
    stages: dict  # stage -> {"usd": float, "basis": str, "units": float}

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "total_usd": round(self.total_usd, 8),
            "stages": {
                k: {"usd": round(v["usd"], 8), "basis": v["basis"],
                    "units": round(v["units"], 3)}
                for k, v in self.stages.items()
            },
        }


class CostLedger:
    """Bills spans as they finish and aggregates cost per request."""

    # Stages billed on compute time vs. tokens.
    COMPUTE_STAGES = {"embed_query", "rerank", "bm25_search", "vector_search"}

    def __init__(self, prices: PriceTable | None = None, keep: int = 1000):
        self.prices = prices or PriceTable.from_env()
        self._lock = threading.Lock()
        self._records: list[CostRecord] = []
        self._keep = keep
        self._pending: dict[str, dict] = {}  # trace_id -> stage bills

    def bill_span(self, trace_id: str, stage: str, duration_ms: float,
                  tokens: int = 0) -> None:
        """Bill one finished span. Token-priced stages need ``tokens``."""
        if stage in self.prices.tokens_per_1k and tokens:
            usd = tokens / 1000.0 * self.prices.tokens_per_1k[stage]
            bill = {"usd": usd, "basis": "tokens", "units": float(tokens)}
        elif stage in self.COMPUTE_STAGES or stage in self.prices.tokens_per_1k:
            usd = duration_ms / 1000.0 * self.prices.compute_per_second
            bill = {"usd": usd, "basis": "compute_seconds",
                    "units": duration_ms / 1000.0}
        else:
            return  # unpriced stage (fusion, validation): negligible, skip
        with self._lock:
            self._pending.setdefault(trace_id, {})[stage] = bill

    def settle(self, trace_id: str) -> CostRecord:
        """Close the bill for a finished request and store the record."""
        with self._lock:
            stages = self._pending.pop(trace_id, {})
            record = CostRecord(
                trace_id=trace_id,
                total_usd=sum(b["usd"] for b in stages.values()),
                stages=stages,
            )
            self._records.append(record)
            if len(self._records) > self._keep:
                del self._records[: len(self._records) - self._keep]
            return record

    def snapshot(self) -> dict:
        with self._lock:
            records = list(self._records)
        if not records:
            return {"requests": 0, "total_usd": 0.0, "mean_usd": 0.0,
                    "p95_usd": 0.0, "per_1k_requests_usd": 0.0, "by_stage": {}}
        from .latency import percentile

        totals = [r.total_usd for r in records]
        by_stage: dict[str, float] = {}
        for r in records:
            for stage, bill in r.stages.items():
                by_stage[stage] = by_stage.get(stage, 0.0) + bill["usd"]
        mean = sum(totals) / len(totals)
        return {
            "requests": len(records),
            "total_usd": round(sum(totals), 6),
            "mean_usd": round(mean, 8),
            "p95_usd": round(percentile(totals, 95), 8),
            "per_1k_requests_usd": round(mean * 1000, 4),
            "by_stage": {k: round(v, 8) for k, v in sorted(by_stage.items())},
        }
