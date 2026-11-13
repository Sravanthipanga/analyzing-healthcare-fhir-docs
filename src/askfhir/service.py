"""Service layer: retrieve -> fuse -> rerank -> compose -> validate."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .answer import ABSTAIN_MESSAGE, ExtractiveComposer, Passage, validate_citations
from .bm25_index import BM25Index
from .chunking import Chunk, load_corpus
from .embeddings import Embedder, get_embedder
from .hybrid import reciprocal_rank_fusion
from .reranker import Reranker, get_reranker
from .vector_index import VectorIndex

# Cross-encoder (ms-marco MiniLM) scores are logits; passages below this are
# treated as "not supported by the docs". Calibrated on the golden eval set:
# the weakest answerable question's top score was -1.15 and the strongest
# unanswerable question's top score was -10.05, so -5.5 sits mid-gap with
# wide margins on both sides. Override with ASKFHIR_ABSTAIN_THRESHOLD.
DEFAULT_ABSTAIN_THRESHOLD = -5.5

TOP_EACH = 20  # candidates per first-stage ranker
FUSED_N = 20  # candidates into the reranker
FINAL_N = 5  # passages used for the answer


@dataclass
class Source:
    chunk: Chunk
    bm25_rank: int | None
    vector_rank: int | None
    fused_score: float
    rerank_score: float

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk.chunk_id,
            "doc_id": self.chunk.doc_id,
            "doc_title": self.chunk.title,
            "section": self.chunk.section,
            "snippet": self.chunk.text,
            "bm25_rank": self.bm25_rank,
            "vector_rank": self.vector_rank,
            "fused_score": round(self.fused_score, 6),
            "rerank_score": round(self.rerank_score, 4),
        }


class AskFHIRService:
    def __init__(
        self,
        chunks: list[Chunk],
        embeddings: np.ndarray,
        embedder: Embedder,
        reranker: Reranker,
        abstain_threshold: float | None = None,
        fake_models: bool = False,
    ):
        self.chunks = chunks
        self.chunks_by_id = {c.chunk_id: c for c in chunks}
        self.embedder = embedder
        self.reranker = reranker
        self.fake_models = fake_models
        if abstain_threshold is None:
            env = os.environ.get("ASKFHIR_ABSTAIN_THRESHOLD")
            abstain_threshold = float(env) if env else DEFAULT_ABSTAIN_THRESHOLD
        # The fake lexical reranker scores in [0, ~1.3]; give it a sane
        # default threshold when running in fake mode.
        if fake_models and os.environ.get("ASKFHIR_ABSTAIN_THRESHOLD") is None:
            abstain_threshold = 0.15
        self.abstain_threshold = abstain_threshold
        self._bm25 = BM25Index([c.index_text() for c in chunks])
        self._vectors = VectorIndex(embeddings)
        self._composer = ExtractiveComposer()
        self._token_weights = self._compute_idf(chunks)

    @staticmethod
    def _compute_idf(chunks: list[Chunk]) -> dict[str, float]:
        """BM25-style inverse document frequency over chunk tokens."""
        import math

        from .embeddings import tokenize

        n = len(chunks)
        df: dict[str, int] = {}
        for c in chunks:
            for tok in set(tokenize(c.index_text())):
                df[tok] = df.get(tok, 0) + 1
        return {
            tok: math.log((n - d + 0.5) / (d + 0.5) + 1.0) for tok, d in df.items()
        }

    # ------------------------------------------------------------------ load
    @classmethod
    def load(
        cls,
        corpus_dir: str | Path = "corpus",
        index_dir: str | Path = "data/index",
        fake: bool = False,
    ) -> "AskFHIRService":
        index_dir = Path(index_dir)
        chunks_file = index_dir / "chunks.json"
        emb_file = index_dir / "embeddings.npy"
        embedder = get_embedder(fake=fake)
        if chunks_file.exists():
            raw = json.loads(chunks_file.read_text(encoding="utf-8"))
            chunks = [Chunk(**r) for r in raw]
        else:
            chunks = load_corpus(corpus_dir)
        if emb_file.exists():
            embeddings = np.load(emb_file)
            probe_dim = embedder.embed(["dimension probe"]).shape[1]
            if embeddings.shape[0] != len(chunks) or embeddings.shape[1] != probe_dim:
                embeddings = embedder.embed([c.index_text() for c in chunks])
        else:
            embeddings = embedder.embed([c.index_text() for c in chunks])
        reranker = get_reranker(fake=fake)
        return cls(chunks, embeddings, embedder, reranker, fake_models=fake)

    # ------------------------------------------------------------------- ask
    def ask(self, question: str) -> dict:
        question = (question or "").strip()
        if not question:
            return self._abstain(question, [])

        bm25_results = self._bm25.search(question, TOP_EACH)
        q_vec = self.embedder.embed([question])[0]
        vector_results = self._vectors.search(q_vec, TOP_EACH)

        bm25_rank = {pos: i + 1 for i, (pos, _) in enumerate(bm25_results)}
        vector_rank = {pos: i + 1 for i, (pos, _) in enumerate(vector_results)}
        fused = reciprocal_rank_fusion(
            [[p for p, _ in bm25_results], [p for p, _ in vector_results]],
            top_n=FUSED_N,
        )
        fused_score = dict(fused)
        candidates = [pos for pos, _ in fused]
        rerank_scores = self.reranker.score(
            question, [self.chunks[p].text for p in candidates]
        )
        order = sorted(
            range(len(candidates)),
            key=lambda i: (-float(rerank_scores[i]), i),
        )
        sources: list[Source] = []
        for i in order[:FINAL_N]:
            pos = candidates[i]
            sources.append(
                Source(
                    chunk=self.chunks[pos],
                    bm25_rank=bm25_rank.get(pos),
                    vector_rank=vector_rank.get(pos),
                    fused_score=fused_score[pos],
                    rerank_score=float(rerank_scores[i]),
                )
            )

        if not sources or sources[0].rerank_score < self.abstain_threshold:
            return self._abstain(question, sources)

        passages = [Passage(s.chunk, s.rerank_score) for s in sources]
        allowed = {s.chunk.chunk_id for s in sources}
        answer = self._composer.generate(question, passages, self._token_weights)
        if validate_citations(answer, allowed):
            # Fallback: compose from the single best passage only.
            answer = self._composer.generate(question, passages[:1], self._token_weights)
            if validate_citations(answer, {passages[0].chunk.chunk_id}):
                return self._abstain(question, sources)

        from .answer import CITATION_RE

        return {
            "question": question,
            "answer": answer,
            "abstained": False,
            "citations": sorted(set(CITATION_RE.findall(answer))),
            "sources": [s.to_dict() for s in sources],
        }

    def _abstain(self, question: str, sources: list[Source]) -> dict:
        return {
            "question": question,
            "answer": ABSTAIN_MESSAGE,
            "abstained": True,
            "citations": [],
            "sources": [s.to_dict() for s in sources],
        }

    # ------------------------------------------------------------------ docs
    def docs(self) -> list[dict]:
        counts: dict[str, dict] = {}
        for c in self.chunks:
            entry = counts.setdefault(
                c.doc_id, {"doc_id": c.doc_id, "title": c.title, "chunks": 0}
            )
            entry["chunks"] += 1
        return [counts[k] for k in sorted(counts)]
