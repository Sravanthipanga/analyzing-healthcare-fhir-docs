import numpy as np

from askfhir.chunking import load_corpus
from askfhir.embeddings import FakeEmbedder
from askfhir.reranker import FakeReranker
from askfhir.service import AskFHIRService

from conftest import CORPUS_DIR


class ZeroReranker:
    name = "fake:zero"

    def score(self, query, texts):
        return np.zeros(len(texts), dtype=np.float32)


def _service(reranker=None, threshold=None):
    chunks = load_corpus(CORPUS_DIR)
    embedder = FakeEmbedder()
    emb = embedder.embed([c.index_text() for c in chunks])
    return AskFHIRService(
        chunks,
        emb,
        embedder,
        reranker or FakeReranker(),
        abstain_threshold=threshold if threshold is not None else 0.15,
        fake_models=True,
    )


def test_answerable_question_returns_cited_answer():
    svc = _service()
    result = svc.ask("Which element of the Patient resource holds the medical record number identifier?")
    assert result["abstained"] is False
    assert result["citations"]
    source_ids = {s["chunk_id"] for s in result["sources"]}
    assert set(result["citations"]) <= source_ids
    assert any(s["doc_id"] == "patient-resource" for s in result["sources"][:3])


def test_low_rerank_scores_force_abstention():
    svc = _service(reranker=ZeroReranker(), threshold=0.5)
    result = svc.ask("Which element of the Patient resource holds identifiers?")
    assert result["abstained"] is True
    assert result["citations"] == []
    assert "couldn't find that in the FHIR docs" in result["answer"]


def test_empty_question_abstains():
    svc = _service()
    assert svc.ask("   ")["abstained"] is True


def test_sources_carry_stage_scores():
    svc = _service()
    result = svc.ask("How does FHIR search paging work with _count and links?")
    for s in result["sources"]:
        assert set(s) >= {
            "chunk_id", "doc_id", "doc_title", "section", "snippet",
            "bm25_rank", "vector_rank", "fused_score", "rerank_score",
        }
