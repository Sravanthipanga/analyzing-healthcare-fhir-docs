from askfhir.chunking import chunk_markdown, load_corpus

from conftest import CORPUS_DIR

SAMPLE = """# My Doc

Intro paragraph about patients and identifiers.

## First Section

The identifier element holds external ids. Each identifier has a system and a value.
Patients may have several identifiers, such as a medical record number.

## Second Section

Searching uses parameters like name and birthdate. Results come back in a Bundle.
"""


def test_chunk_ids_and_sections():
    chunks = chunk_markdown(SAMPLE, "my-doc")
    assert chunks, "expected chunks"
    assert [c.chunk_id for c in chunks] == [f"my-doc#{i}" for i in range(len(chunks))]
    assert all(c.doc_id == "my-doc" for c in chunks)
    assert all(c.title == "My Doc" for c in chunks)
    sections = {c.section for c in chunks}
    assert "First Section" in sections and "Second Section" in sections


def test_chunking_is_deterministic():
    a = load_corpus(CORPUS_DIR)
    b = load_corpus(CORPUS_DIR)
    assert [c.to_dict() for c in a] == [c.to_dict() for c in b]


def test_corpus_shape():
    chunks = load_corpus(CORPUS_DIR)
    doc_ids = {c.doc_id for c in chunks}
    assert len(doc_ids) == 12
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "chunk ids must be unique"
    for c in chunks:
        prefix, _, num = c.chunk_id.rpartition("#")
        assert prefix == c.doc_id and num.isdigit()
        assert 0 < len(c.text) <= 900
