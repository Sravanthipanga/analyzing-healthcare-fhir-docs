"""Exact cosine-similarity vector index over numpy embeddings.

The corpus is small (tens of chunks), so brute-force exact search is both
correct and deterministic — no ANN approximation error. The interface
(`add`/`search`) is the same one a FAISS IndexFlatIP wrapper would expose,
so swapping at scale is a drop-in change.
"""

from __future__ import annotations

import numpy as np


class VectorIndex:
    def __init__(self, embeddings: np.ndarray):
        emb = np.asarray(embeddings, dtype=np.float32)
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        self._emb = emb / norms

    def __len__(self) -> int:
        return int(self._emb.shape[0])

    def search(self, query_vec: np.ndarray, k: int) -> list[tuple[int, float]]:
        """Return top-k (chunk_position, cosine_score), best first.

        Ties break toward the lower chunk position for determinism.
        """
        q = np.asarray(query_vec, dtype=np.float32).reshape(-1)
        norm = np.linalg.norm(q)
        if norm > 0:
            q = q / norm
        scores = self._emb @ q
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
        return [(i, float(scores[i])) for i in order[:k]]
