"""Deterministic markdown chunking.

Docs are split first by markdown headings (``##`` sections), then each section
is windowed into chunks of roughly ``CHUNK_CHARS`` characters with
``OVERLAP_CHARS`` of overlap, preferring to break on sentence boundaries.

Chunk ids are stable: ``"<doc-slug>#<n>"`` where ``n`` is the chunk's index
within its document, assigned in reading order. Given the same corpus files,
chunking always produces byte-identical output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from pathlib import Path

CHUNK_CHARS = 600
OVERLAP_CHARS = 100

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str  # "<doc-slug>#<n>"
    doc_id: str  # doc slug, e.g. "patient-resource"
    title: str  # document title (first H1)
    section: str  # nearest enclosing H2 (or title)
    text: str  # chunk body text

    def index_text(self) -> str:
        """Text fed to BM25 / embeddings: title + section give context."""
        return f"{self.title}. {self.section}. {self.text}"

    def to_dict(self) -> dict:
        return asdict(self)


def _split_long_text(text: str, size: int = CHUNK_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    """Window `text` into ~`size`-char pieces, breaking near sentence ends."""
    text = " ".join(text.split())
    if len(text) <= size:
        return [text] if text else []
    pieces: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            # Prefer a sentence boundary in the last 40% of the window.
            window = text[start:end]
            cut = -1
            for m in _SENTENCE_END.finditer(window):
                if m.start() > size * 0.6:
                    cut = m.start() + 1
            if cut > 0:
                end = start + cut
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return pieces


def chunk_markdown(md_text: str, doc_slug: str) -> list[Chunk]:
    title = doc_slug
    section = ""
    # sections: list of (section_name, [paragraph lines])
    sections: list[tuple[str, list[str]]] = []
    current_name: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_name, current_lines
        if current_name is not None:
            sections.append((current_name, current_lines))
        current_lines = []

    in_code = False
    for line in md_text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        m = _HEADING.match(line)
        if m and not in_code:
            level = len(m.group(1))
            heading_text = m.group(2).strip()
            if level == 1 and title == doc_slug:
                title = heading_text
                continue
            if level == 2:
                flush()
                current_name = heading_text
                continue
            # Deeper headings become bold inline markers inside the section.
            current_lines.append(heading_text)
            continue
        if current_name is None:
            current_name = title
        current_lines.append(line)
    flush()

    chunks: list[Chunk] = []
    counter = 0
    for section_name, lines in sections:
        body = "\n".join(lines).strip()
        if not body:
            continue
        for piece in _split_long_text(body):
            chunks.append(
                Chunk(
                    chunk_id=f"{doc_slug}#{counter}",
                    doc_id=doc_slug,
                    title=title,
                    section=section_name,
                    text=piece,
                )
            )
            counter += 1
    return chunks


def load_corpus(corpus_dir: str | Path) -> list[Chunk]:
    """Chunk every ``*.md`` file in `corpus_dir`, in filename order."""
    corpus_dir = Path(corpus_dir)
    all_chunks: list[Chunk] = []
    for path in sorted(corpus_dir.glob("*.md")):
        all_chunks.extend(chunk_markdown(path.read_text(encoding="utf-8"), path.stem))
    return all_chunks
