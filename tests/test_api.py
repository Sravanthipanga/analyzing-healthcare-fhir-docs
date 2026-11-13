import json
from pathlib import Path

from fastapi.testclient import TestClient

from askfhir.api import create_app
from askfhir.chunking import load_corpus
from askfhir.embeddings import FakeEmbedder
from askfhir.reranker import FakeReranker
from askfhir.service import AskFHIRService

from conftest import BASE, CORPUS_DIR


def _client() -> TestClient:
    chunks = load_corpus(CORPUS_DIR)
    embedder = FakeEmbedder()
    emb = embedder.embed([c.index_text() for c in chunks])
    svc = AskFHIRService(chunks, emb, embedder, FakeReranker(), fake_models=True)
    return TestClient(create_app(service=svc))


def test_healthz():
    assert _client().get("/healthz").json() == {"status": "ok"}


def test_docs_lists_corpus():
    docs = _client().get("/docs").json()
    assert len(docs) == 12
    assert all(d["chunks"] > 0 for d in docs)


def test_ask_shape():
    resp = _client().post(
        "/ask", json={"question": "What is a transaction Bundle in FHIR?"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert set(data) >= {"question", "answer", "abstained", "citations", "sources"}
    assert isinstance(data["abstained"], bool)
    assert isinstance(data["citations"], list)


def test_index_page_served():
    resp = _client().get("/")
    assert resp.status_code == 200
    assert "AskFHIR" in resp.text


def test_golden_set_sanity():
    golden_path = BASE / "eval" / "golden.jsonl"
    entries = [json.loads(line) for line in golden_path.read_text().splitlines() if line.strip()]
    assert len(entries) >= 25
    corpus_docs = {p.stem for p in Path(CORPUS_DIR).glob("*.md")}
    categories = set()
    for e in entries:
        categories.add(e["category"])
        assert set(e["expected_doc_ids"]) <= corpus_docs, e
        if e["category"] == "unanswerable":
            assert e["expected_doc_ids"] == []
    assert {"factual", "terminology", "comparison", "unanswerable"} <= categories
