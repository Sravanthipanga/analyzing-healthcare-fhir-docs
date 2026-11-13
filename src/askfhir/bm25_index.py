"""BM25 keyword index (rank_bm25 BM25Okapi) over chunk text."""

from __future__ import annotations

from rank_bm25 import BM25Okapi

from .embeddings import tokenize


class BM25Index:
    def __init__(self, texts: list[str]):
        self._corpus_tokens = [tokenize(t) for t in texts]
        self._bm25 = BM25Okapi(self._corpus_tokens)

    def __len__(self) -> int:
        return len(self._corpus_tokens)

    def search(self, query: str, k: int) -> list[tuple[int, float]]:
        """Return top-k (chunk_position, bm25_score), best first, ties by position."""
        scores = self._bm25.get_scores(tokenize(query))
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
        return [(i, float(scores[i])) for i in order[:k]]
