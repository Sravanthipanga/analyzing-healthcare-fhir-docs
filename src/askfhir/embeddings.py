"""Embedding backends behind a swappable protocol.

Default: fastembed (ONNX) with BAAI/bge-small-en-v1.5 — light, no torch.
Fallback: sentence-transformers all-MiniLM-L6-v2 (used only if fastembed is
unavailable). Tests use FakeEmbedder: a deterministic hashing bag-of-words
embedder that needs no downloads and gives sane lexical similarity.
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Protocol, runtime_checkable

import numpy as np

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _normalize(mat: np.ndarray) -> np.ndarray:
    mat = np.asarray(mat, dtype=np.float32)
    if mat.ndim == 1:
        mat = mat.reshape(1, -1)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return mat / norms


@runtime_checkable
class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an (len(texts), dim) float32 array of L2-normalized vectors."""
        ...


class FastEmbedEmbedder:
    name = "fastembed:BAAI/bge-small-en-v1.5"

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", cache_dir: str | None = None):
        from fastembed import TextEmbedding

        cache_dir = cache_dir or os.environ.get("ASKFHIR_MODEL_CACHE") or None
        self._model = TextEmbedding(model_name=model_name, cache_dir=cache_dir)

    def embed(self, texts: list[str]) -> np.ndarray:
        vecs = list(self._model.embed(texts))
        return _normalize(np.array(vecs, dtype=np.float32))


class SentenceTransformersEmbedder:
    name = "sentence-transformers:all-MiniLM-L6-v2"

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> np.ndarray:
        vecs = self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return _normalize(vecs)


class FakeEmbedder:
    """Deterministic hashing embedder for tests / offline smoke runs."""

    name = "fake:hashing-bow-256"

    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for tok in tokenize(text):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                out[i, h % self.dim] += 1.0
        return _normalize(out)


def get_embedder(fake: bool = False) -> Embedder:
    if fake or os.environ.get("ASKFHIR_FAKE_MODELS") == "1":
        return FakeEmbedder()
    try:
        return FastEmbedEmbedder()
    except Exception:
        return SentenceTransformersEmbedder()
