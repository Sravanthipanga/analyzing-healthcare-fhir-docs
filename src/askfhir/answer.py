"""Answer composition with enforced citations.

The default generator is an ExtractiveComposer: it builds the answer ONLY
from sentences of the top reranked chunks, and every sentence carries a
citation marker ``[doc-slug#n]`` naming the exact chunk it came from.
`validate_citations` then checks the composed answer: every sentence must
cite at least one chunk, and every cited chunk must be inside the retrieved
set. An answer that fails validation is never returned — the service falls
back or abstains.

An LLM-backed generator can replace the composer behind the AnswerGenerator
protocol without changing retrieval, validation, or the API.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .chunking import Chunk
from .embeddings import tokenize

CITATION_RE = re.compile(r"\[([A-Za-z0-9_\-]+#\d+)\]")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

ABSTAIN_MESSAGE = (
    "I couldn't find that in the FHIR docs provided, so I don't have a "
    "sourced answer for it. Try rephrasing the question, or ask about a "
    "specific topic the corpus covers: FHIR resources (Patient, Encounter, "
    "Observation, Condition, MedicationRequest), search, Bundles and "
    "transactions, SMART on FHIR, HL7 v2, terminology, or profiles and "
    "validation."
)


@dataclass
class Passage:
    chunk: Chunk
    rerank_score: float


@runtime_checkable
class AnswerGenerator(Protocol):
    def generate(
        self,
        question: str,
        passages: list[Passage],
        token_weights: dict[str, float] | None = None,
    ) -> str:
        ...


def split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_SPLIT.split(" ".join(text.split()))
    return [p.strip() for p in parts if p.strip()]


def _sentences_with_citations(answer: str) -> list[str]:
    """Split into sentences, re-attaching citation markers that follow the
    sentence's terminating punctuation to the sentence they belong to."""
    sentences: list[str] = []
    for frag in split_sentences(answer):
        rest = frag
        leading: list[str] = []
        while True:
            m = re.match(r"\s*(\[[A-Za-z0-9_\-]+#\d+\])\s*", rest)
            if not m:
                break
            leading.append(m.group(1))
            rest = rest[m.end():]
            if not rest:
                break
        if leading and sentences:
            sentences[-1] = sentences[-1] + " " + " ".join(leading)
            if not rest:
                continue
        elif leading and not sentences:
            sentences.append(" ".join(leading) + (" " + rest if rest else ""))
            continue
        if rest:
            sentences.append(rest)
    return sentences


def validate_citations(answer: str, allowed_chunk_ids: set[str]) -> list[str]:
    """Return a list of problems; empty list means the answer is valid."""
    problems: list[str] = []
    cited = CITATION_RE.findall(answer)
    if not cited:
        problems.append("answer contains no citations")
    for cid in cited:
        if cid not in allowed_chunk_ids:
            problems.append(f"citation [{cid}] is not in the retrieved set")
    for sentence in _sentences_with_citations(answer):
        if not CITATION_RE.search(sentence):
            problems.append(f"sentence without citation: {sentence[:60]}...")
    return problems


def _sentence_score(
    sentence: str, q_tokens: set[str], token_weights: dict[str, float] | None = None
) -> float:
    """IDF-weighted overlap: rare question terms (rank, _has, refuted) count
    far more than corpus-common ones (resource, patient, fhir), which keeps
    generic document-intro sentences from winning on word salad alone."""
    toks = tokenize(sentence)
    if not toks:
        return 0.0
    if token_weights:
        denom = sum(token_weights.get(t, 0.0) for t in q_tokens) or 1.0
        numer = sum(token_weights.get(t, 0.0) for t in set(toks) & q_tokens)
        return numer / denom
    overlap = sum(1 for t in toks if t in q_tokens)
    return overlap / max(len(q_tokens), 1)


class ExtractiveComposer:
    """Compose an answer from the most question-relevant sentences of the
    top passages, each sentence tagged with its source chunk citation."""

    def __init__(self, max_sentences: int = 4, per_chunk: int = 2, floor_ratio: float = 0.3):
        self.max_sentences = max_sentences
        self.per_chunk = per_chunk
        self.floor_ratio = floor_ratio

    def generate(
        self,
        question: str,
        passages: list[Passage],
        token_weights: dict[str, float] | None = None,
    ) -> str:
        q_tokens = set(tokenize(question))
        # Collect candidate sentences across passages, weighting each by its
        # passage's rerank position: a sentence from a lower-ranked passage
        # must be proportionally more relevant to displace one from the top
        # passage. This keeps answers (and their citations) concentrated on
        # the best evidence instead of drifting across neighbouring docs.
        candidates: list[tuple[float, int, str, str]] = []  # (score, p_idx, sentence, chunk_id)
        for p_idx, passage in enumerate(passages):
            weight = 1.0 / (1.0 + p_idx)
            for sent in split_sentences(passage.chunk.text):
                if len(sent) < 40 or sent.startswith(("```", "{", '"', "|")):
                    continue
                raw = _sentence_score(sent, q_tokens, token_weights)
                if raw > 0:
                    candidates.append((raw * weight, p_idx, sent, passage.chunk.chunk_id))
        if not candidates:
            return ""
        candidates.sort(key=lambda c: -c[0])
        floor = self.floor_ratio * candidates[0][0]

        picked: list[tuple[int, str, str]] = []
        per_chunk_count: dict[str, int] = {}
        seen: set[str] = set()
        picked_token_sets: list[set[str]] = []
        for score, p_idx, sent, cid in candidates:
            if len(picked) >= self.max_sentences or score < floor:
                break
            if per_chunk_count.get(cid, 0) >= self.per_chunk or sent in seen:
                continue
            toks = set(tokenize(sent))
            # Overlapping chunks repeat near-identical sentences; suppress a
            # candidate that mostly duplicates one already picked.
            if any(
                len(toks & prev) / max(len(toks | prev), 1) > 0.7
                for prev in picked_token_sets
            ):
                continue
            per_chunk_count[cid] = per_chunk_count.get(cid, 0) + 1
            seen.add(sent)
            picked_token_sets.append(toks)
            picked.append((p_idx, sent, cid))
        picked.sort(key=lambda p: p[0])  # reading order: best passage first
        return " ".join(f"{sent} [{cid}]" for _, sent, cid in picked)
