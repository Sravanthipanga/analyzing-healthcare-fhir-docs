"""Online quality signals: the proxies watched between eval runs.

The golden-set eval (``eval/run_eval.py``) measures quality offline.
These counters measure it *live*, on real traffic, so a bad deploy is
caught by the dashboard before the next CI run:

- **abstention rate** — spiking means retrieval or the threshold broke;
  collapsing to zero can mean the threshold stopped protecting you.
- **citation density** — citations per answered question; the product
  promise is "every claim cited", so density drifting down is a smell.
- **fallback rate** — how often citation validation rejected the first
  composed answer and forced the single-passage fallback.
- **empty rate** — questions that returned no sources at all.
"""

from __future__ import annotations

import threading


class QualityTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests = 0
        self._abstained = 0
        self._empty = 0
        self._fallbacks = 0
        self._citations = 0
        self._answered = 0

    def record(self, *, abstained: bool, citations: int, sources: int,
               fallback_used: bool) -> None:
        with self._lock:
            self._requests += 1
            self._abstained += int(abstained)
            self._empty += int(sources == 0)
            self._fallbacks += int(fallback_used)
            if not abstained:
                self._answered += 1
                self._citations += citations

    def snapshot(self) -> dict:
        with self._lock:
            r, a, ab = self._requests, self._answered, self._abstained
            e, f, c = self._empty, self._fallbacks, self._citations
        if r == 0:
            return {"requests": 0}
        return {
            "requests": r,
            "answered": a,
            "abstention_rate": round(ab / r, 4),
            "empty_rate": round(e / r, 4),
            "fallback_rate": round(f / r, 4),
            "citations_per_answer": round(c / a, 3) if a else 0.0,
        }
