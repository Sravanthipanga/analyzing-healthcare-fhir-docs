"""Cross-encoder reranking behind a swappable protocol.

Default: fastembed TextCrossEncoder with Xenova/ms-marco-MiniLM-L-6-v2
(ONNX, no torch). Fallback: sentence-transformers CrossEncoder with the
equivalent model. Tests use FakeReranker, a deterministic lexical scorer.
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

import numpy as np

from .embeddings import tokenize


@runtime_checkable
class Reranker(Protocol):
    name: str

    def score(self, query: str, texts: list[str]) -> np.ndarray:
        """Return one relevance score per text (higher = more relevant)."""
        ...


class FastEmbedReranker:
    name = "fastembed:Xenova/ms-marco-MiniLM-L-6-v2"

    def __init__(self, model_name: str = "Xenova/ms-marco-MiniLM-L-6-v2", cache_dir: str | None = None):
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        cache_dir = cache_dir or os.environ.get("ASKFHIR_MODEL_CACHE") or None
        self._model = TextCrossEncoder(model_name=model_name, cache_dir=cache_dir)

    def score(self, query: str, texts: list[str]) -> np.ndarray:
        scores = list(self._model.rerank(query, texts))
        return np.asarray(scores, dtype=np.float32)


class SentenceTransformersReranker:
    name = "sentence-transformers:cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(model_name)

    def score(self, query: str, texts: list[str]) -> np.ndarray:
        pairs = [[query, t] for t in texts]
        return np.asarray(self._model.predict(pairs, show_progress_bar=False), dtype=np.float32)


class FakeReranker:
    """Deterministic lexical reranker: fraction of distinct query tokens
    present in the text, with a small bonus for repeated matches."""

    name = "fake:lexical-overlap"

    def score(self, query: str, texts: list[str]) -> np.ndarray:
        q_tokens = set(tokenize(query))
        out = np.zeros(len(texts), dtype=np.float32)
        if not q_tokens:
            return out
        for i, text in enumerate(texts):
            toks = tokenize(text)
            present = q_tokens.intersection(toks)
            out[i] = len(present) / len(q_tokens) + 0.01 * sum(
                min(toks.count(t), 3) for t in present
            )
        return out


def get_reranker(fake: bool = False) -> Reranker:
    if fake or os.environ.get("ASKFHIR_FAKE_MODELS") == "1":
        return FakeReranker()
    try:
        return FastEmbedReranker()
    except Exception:
        return SentenceTransformersReranker()
