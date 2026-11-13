"""Run the golden-set evaluation and gate on thresholds.

Usage:  PYTHONPATH=src .venv/bin/python eval/run_eval.py [--fake]

Metrics (answerable questions):
  hit@5               fraction with an expected doc in the reranked top-5
  mrr@5               mean reciprocal rank of the first expected doc in top-5
  citation_precision  of citations emitted, fraction pointing at expected docs
  keyword_recall      fraction of answer_keywords present in the answer (info)
Abstention:
  abstention_accuracy unanswerable correctly abstained AND answerable not abstained

Writes eval/report.json; exit code 1 if any gated metric is below its
threshold in eval/thresholds.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))

from askfhir.answer import CITATION_RE  # noqa: E402
from askfhir.service import AskFHIRService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fake", action="store_true", help="use fake models")
    args = parser.parse_args()

    golden = [
        json.loads(line)
        for line in (BASE / "eval" / "golden.jsonl").read_text().splitlines()
        if line.strip()
    ]
    thresholds = json.loads((BASE / "eval" / "thresholds.json").read_text())

    svc = AskFHIRService.load(
        corpus_dir=BASE / "corpus", index_dir=BASE / "data" / "index", fake=args.fake
    )
    print(f"embedder={svc.embedder.name}  reranker={svc.reranker.name}  "
          f"abstain_threshold={svc.abstain_threshold}")

    rows = []
    hits, rr_sum, answered = 0, 0.0, 0
    cite_total, cite_good = 0, 0
    kw_total, kw_found = 0, 0
    abstain_correct, abstain_total = 0, 0

    for entry in golden:
        result = svc.ask(entry["question"])
        expected = set(entry["expected_doc_ids"])
        if not expected:  # unanswerable
            abstain_total += 1
            ok = result["abstained"]
            abstain_correct += int(ok)
            rows.append((entry, None, ok, result))
            continue
        abstain_total += 1
        abstain_correct += int(not result["abstained"])
        top_docs = [s["doc_id"] for s in result["sources"][:5]]
        rank = next((i + 1 for i, d in enumerate(top_docs) if d in expected), None)
        if rank:
            hits += 1
            rr_sum += 1.0 / rank
        answered += 1
        cited_docs = {
            svc.chunks_by_id[cid].doc_id
            for cid in CITATION_RE.findall(result["answer"])
            if cid in svc.chunks_by_id
        }
        cite_total += len(cited_docs)
        cite_good += sum(1 for d in cited_docs if d in expected)
        answer_low = result["answer"].lower()
        for kw in entry["answer_keywords"]:
            kw_total += 1
            kw_found += int(kw.lower() in answer_low)
        rows.append((entry, rank, not result["abstained"], result))

    metrics = {
        "questions": len(golden),
        "answerable": answered,
        "hit@5": round(hits / answered, 4) if answered else 0.0,
        "mrr@5": round(rr_sum / answered, 4) if answered else 0.0,
        "citation_precision": round(cite_good / cite_total, 4) if cite_total else 0.0,
        "keyword_recall": round(kw_found / kw_total, 4) if kw_total else 0.0,
        "abstention_accuracy": round(abstain_correct / abstain_total, 4) if abstain_total else 0.0,
    }

    print(f"\n{'question':<72} {'rank':>4}  ok")
    print("-" * 84)
    for entry, rank, ok, _ in rows:
        q = entry["question"][:70]
        print(f"{q:<72} {str(rank) if rank else '-':>4}  {'yes' if ok else 'NO'}")

    print("\nmetrics vs gate thresholds:")
    failed = []
    for name, value in metrics.items():
        if name in thresholds:
            gate = thresholds[name]
            status = "PASS" if value >= gate else "FAIL"
            if status == "FAIL":
                failed.append(name)
            print(f"  {name:<22} {value:.4f}  >= {gate:<6} {status}")
        else:
            print(f"  {name:<22} {value}  (info)")

    report = {
        "metrics": metrics,
        "thresholds": thresholds,
        "embedder": svc.embedder.name,
        "reranker": svc.reranker.name,
        "abstain_threshold": svc.abstain_threshold,
        "fake_models": args.fake,
        "per_question": [
            {
                "question": e["question"],
                "category": e["category"],
                "expected_doc_ids": e["expected_doc_ids"],
                "first_expected_rank": r,
                "behaved": ok,
                "abstained": res["abstained"],
                "citations": res["citations"],
                "top_rerank_score": res["sources"][0]["rerank_score"] if res["sources"] else None,
            }
            for e, r, ok, res in rows
        ],
    }
    (BASE / "eval" / "report.json").write_text(json.dumps(report, indent=1))
    print(f"\nwrote eval/report.json")
    if failed:
        print(f"GATE FAILED: {', '.join(failed)}")
        return 1
    print("GATE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
