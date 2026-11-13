from askfhir.answer import ExtractiveComposer, Passage, validate_citations
from askfhir.chunking import Chunk

CHUNK = Chunk(
    chunk_id="patient-resource#2",
    doc_id="patient-resource",
    title="The Patient Resource",
    section="Key Elements",
    text=(
        "The identifier element holds identifiers that belong to the patient in the "
        "real world. Each Identifier has a system naming the issuing authority and "
        "a value, such as a medical record number."
    ),
)


def test_validate_accepts_valid():
    answer = "Identifiers belong to the patient in the real world. [patient-resource#2]"
    assert validate_citations(answer, {"patient-resource#2"}) == []


def test_validate_rejects_missing_citation():
    answer = "Identifiers belong to the patient. This sentence has no source."
    problems = validate_citations(answer, {"patient-resource#2"})
    assert problems


def test_validate_rejects_foreign_citation():
    answer = "Identifiers belong to the patient in the real world. [observation-resource#9]"
    problems = validate_citations(answer, {"patient-resource#2"})
    assert any("not in the retrieved set" in p for p in problems)


def test_composer_output_always_valid():
    composer = ExtractiveComposer()
    answer = composer.generate(
        "What is the identifier element of Patient?",
        [Passage(CHUNK, 5.0)],
    )
    assert answer
    assert validate_citations(answer, {"patient-resource#2"}) == []
