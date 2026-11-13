# Analyzing Healthcare — FHIR Docs

**AskFHIR** — an "Ask My Docs" system for FHIR / HL7.

A production-pattern **retrieval-augmented generation (RAG)** application over
healthcare interoperability documentation. Ask a question about FHIR; the
system retrieves evidence with **hybrid search**, reranks it with a
**cross-encoder**, and answers with **enforced citations** — or **abstains**
when the docs don't support an answer. No citation, no claim.

Quality is not vibes: a **golden-set evaluation runs as a CI gate**. Every
push and pull request must clear retrieval and citation thresholds or the
build fails (see [Evaluation](#evaluation-the-ci-gate)).

- **Corpus:** 12 curated documents (128 chunks) on FHIR R4 resources, search,
  Bundles, SMART on FHIR, HL7 v2, terminology, and profiles — written for
  this project from public HL7 FHIR R4 concepts. No real patient data
  anywhere; examples use obviously synthetic people ("Jane Example").
- **Models run 100% locally** (ONNX via fastembed). No API key, no LLM bill.
  An LLM generator can be dropped in behind the `AnswerGenerator` protocol.

## Architecture

```
                        ┌────────────────────── offline ──────────────────────┐
 corpus/*.md ──► chunking (by heading, ~600 chars, stable ids "doc#n")
                        │            ├─► BM25 index (rank_bm25)
                        │            └─► embeddings (bge-small-en-v1.5) ──► exact cosine index
                        └──────────────────────────────────────────────────────┘
 question
    │
    ├─► BM25 top-20 ──────────────┐
    ├─► vector top-20 ────────────┤  Reciprocal Rank Fusion (k=60)
    │                             ▼
    │                        fused top-20
    │                             ▼
    │                  cross-encoder rerank (ms-marco MiniLM)
    │                             ▼
    │                         top-5 passages
    │                             ▼
    │            top rerank score < threshold? ──► ABSTAIN ("not in the docs")
    │                             ▼
    │        extractive composition: sentences ONLY from the top passages,
    │        each sentence tagged [doc#n]; IDF-weighted sentence selection
    │                             ▼
    │        citation validation: every sentence cited, every citation in
    │        the retrieved set — otherwise regenerate restricted, or abstain
    ▼
 answer + citations + sources with per-stage scores (BM25 rank, vector rank,
 RRF fused score, rerank score) — the pipeline is visible in the UI.
```

## How the retrieval works

**Hybrid retrieval.** BM25 is superb at exact terminology (`_include`,
`8867-4`, `clinicalStatus`) and weak at paraphrase; vector search is the
opposite. AskFHIR runs both and fuses the rankings.

**Reciprocal Rank Fusion.** Each chunk scores `Σ 1 / (60 + rank)` across the
two rankers. RRF needs no score normalization — important because BM25 scores
and cosine similarities are on incomparable scales — and it rewards chunks
both rankers agree on.

**Cross-encoder reranking.** The fused top-20 is rescored by a cross-encoder
(`Xenova/ms-marco-MiniLM-L-6-v2`) that reads question and passage *together*,
which is far more accurate than the bi-encoder first stage. The top 5
survive.

**Citation enforcement.** The composer (`ExtractiveComposer`) may only use
sentences from the top-5 passages, weights them by corpus IDF (so rare terms
like `refuted` or `_has` outrank generic "FHIR resource patient" word salad),
suppresses near-duplicates from overlapping chunks, and tags every sentence
with its chunk id. `validate_citations()` then rejects any answer with an
uncited sentence or a citation outside the retrieved set.

**Abstention.** If the best rerank score is below the threshold, the system
refuses rather than improvise. The threshold (−5.5) was calibrated on the
golden set: the weakest answerable question scored −1.15 and the strongest
unanswerable one −10.05, so the threshold sits mid-gap with wide margins.

## Evaluation (the CI gate)

`eval/golden.jsonl` holds 35 questions — 29 answerable (factual, terminology,
comparison) with the docs that should answer them, and 6 deliberately
unanswerable ones (stock prices, cake recipes, …). `eval/run_eval.py` runs
the full pipeline and gates on `eval/thresholds.json`:

| Metric | Meaning | **Baseline (measured)** | Gate threshold |
|---|---|---:|---:|
| hit@5 | expected doc appears in reranked top-5 | **1.0000** | 0.85 |
| MRR@5 | mean reciprocal rank of first expected doc | **0.9655** | 0.82 |
| citation_precision | emitted citations pointing at expected docs | **0.7000** | 0.60 |
| abstention_accuracy | unanswerable abstained **and** answerable answered | **1.0000** | 0.85 |
| keyword_recall (info) | expected answer keywords present in the answer | 0.9057 | — |

Measured locally with the real models (fastembed `BAAI/bge-small-en-v1.5` +
`Xenova/ms-marco-MiniLM-L-6-v2`); thresholds are set ~10–15% below the
measured baseline so the gate is meaningful but not flaky. The same command
runs in GitHub Actions (`.github/workflows/ci.yml`) after `pytest`:

```bash
PYTHONPATH=src .venv/bin/python eval/run_eval.py   # exit 1 if any gate fails
```

A note on citation precision: the metric is strict — it counts a citation as
wrong if it points anywhere other than the single expected doc. Most
"misses" are genuinely relevant neighbour docs (e.g. the terminology doc
cited for a LOINC question, since it lists the codes too). The number is
reported honestly rather than gamed.

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .

# Build the index (first run downloads the embedding model, ~130 MB)
PYTHONPATH=src .venv/bin/python scripts/build_index.py

# Run the API + chat UI (first /ask downloads the reranker, ~90 MB)
PYTHONPATH=src .venv/bin/uvicorn askfhir.api:app --port 8000
# open http://localhost:8000/
```

Docker: `docker build -t askfhir . && docker run -p 8000:8000 askfhir`
(models and index are baked in at image build).

Offline/smoke mode with deterministic fake models (no downloads, lexical
quality only): prefix commands with `ASKFHIR_FAKE_MODELS=1`.

## Example (real captured output)

**Q: Which LOINC code identifies a heart rate observation?**

> Observation codes are usually LOINC: glucose is 2339-0, heart rate is 8867-4, systolic blood pressure is 8480-6. [terminology#1] - **LOINC** (system `http://loinc.org`) — Logical Observation Identifiers Names and Codes: names for laboratory tests, vital signs, and clinical measurements. [terminology#1] The FHIR specification defines a vital signs profile that constrains Observation for common measurements: body temperature, heart rate, respiratory rate, blood pressure, oxygen saturation, body weight, height, and BMI. [observation-resource#8] Code search is token-based, so `GET /Observation?patient=example&code=http://loinc.org|8867-4` returns heart rate readings. [observation-resource#9]

**Q: What is the capital of France?**

> `abstained: true` — "I couldn't find that in the FHIR docs provided, so I don't have a sourced answer for it. …" (top rerank score for this question: −11.03, far below the −5.5 threshold)

Answers are extractive — sentences are quoted verbatim from the corpus,
markdown artifacts and all. That is a deliberate trade-off (see below).

## Project structure

```
corpus/                  12 curated FHIR/HL7 markdown docs (the knowledge base)
src/askfhir/
  chunking.py            heading-aware chunking, stable ids
  embeddings.py          Embedder protocol: fastembed (bge-small) / ST fallback / fake
  bm25_index.py          BM25Okapi keyword index
  vector_index.py        exact cosine search (FAISS-swappable interface)
  hybrid.py              Reciprocal Rank Fusion
  reranker.py            Reranker protocol: fastembed cross-encoder / ST fallback / fake
  answer.py              ExtractiveComposer + citation validation + abstention text
  service.py             retrieve → fuse → rerank → compose → validate
  api.py                 FastAPI: POST /ask, GET /docs, GET /healthz, GET / (UI)
static/index.html        single-file chat UI; shows per-stage scores per source
scripts/build_index.py   writes data/index/{chunks.json, embeddings.npy}
eval/
  golden.jsonl           35-question golden set
  thresholds.json        CI gate thresholds
  run_eval.py            evaluation runner (writes eval/report.json)
tests/                   pytest: unit + API + golden sanity (+ opt-in real-model test)
.github/workflows/ci.yml pytest, index build, and the eval gate on every push/PR
Dockerfile               slim image, index + models baked in
```

## Design trade-offs

- **Exact vs ANN vector search.** With 128 chunks, brute-force cosine is
  exact, deterministic, and microseconds-fast — strictly better than an
  approximate index. `VectorIndex` exposes the same interface a FAISS
  `IndexFlatIP` wrapper would, so the swap at ~1M chunks is drop-in.
- **Extractive vs LLM generation.** Extractive composition cannot hallucinate
  a sentence — every claim is a verbatim quote with a citation — at the cost
  of prose polish. The `AnswerGenerator` protocol is the seam: an LLM
  generator can be added behind it and remains subject to the same
  `validate_citations` gate and the same eval.
- **Local models vs APIs.** fastembed/ONNX models keep the whole system
  self-contained and free to run in CI. bge-small + ms-marco-MiniLM are
  small; a larger embedder is a one-line change behind the protocol.
- **Single-label citation precision.** Golden expectations name one doc per
  question even where two docs legitimately cover a topic; the metric is
  reported as-is (0.70) instead of quietly redefining it.

## Future work

- LLM-backed `AnswerGenerator` with the same citation validation, compared
  against the extractive baseline in the eval.
- Query rewriting / HyDE for vague questions; per-category eval breakdowns.
- FAISS ANN index + incremental corpus updates; a terminology-aware
  tokenizer that keeps codes like `85354-9` atomic.
- Streaming answers in the UI; feedback capture (👍/👎) feeding new golden
  questions.
