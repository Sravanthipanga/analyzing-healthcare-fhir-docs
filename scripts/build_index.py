#!/usr/bin/env python3
"""Build the persisted index artifacts: data/index/chunks.json + embeddings.npy.

Usage:  PYTHONPATH=src .venv/bin/python scripts/build_index.py [--fake]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))

from askfhir.chunking import load_corpus  # noqa: E402
from askfhir.embeddings import get_embedder  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fake", action="store_true", help="use the fake embedder")
    args = parser.parse_args()

    chunks = load_corpus(BASE / "corpus")
    embedder = get_embedder(fake=args.fake)
    print(f"embedder: {embedder.name}")
    print(f"chunks: {len(chunks)} from {len(set(c.doc_id for c in chunks))} docs")
    embeddings = embedder.embed([c.index_text() for c in chunks])
    out_dir = BASE / "data" / "index"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "chunks.json").write_text(
        json.dumps([asdict(c) for c in chunks], indent=1), encoding="utf-8"
    )
    np.save(out_dir / "embeddings.npy", embeddings)
    print(f"wrote {out_dir}/chunks.json and embeddings.npy {embeddings.shape}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
