"""Quick standalone check: for each v1 test-set record, does hybrid retrieval surface
the record's gold `source_doc` in its top-k results?

Usage (from 08_rag_app/backend, with the venv active):
    python -m scripts.smoke_test_retrieval [--k 4]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import settings
from app.core.retrieval import get_retriever

ROOT = Path(__file__).resolve().parents[3]  # d:/NEXUS
TEST_PATH = ROOT / "04_datasets" / "v1" / "test.jsonl"


def user_turn_for(rec: dict) -> str:
    return rec["instruction"] if not rec["input"] else f"{rec['instruction']}\n\n{rec['input']}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=settings.retrieval_top_k)
    args = parser.parse_args()

    records = [json.loads(line) for line in TEST_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    retriever = get_retriever()

    hits_top1 = 0
    hits_topk = 0
    gated_out = 0
    misses: list[dict] = []

    for rec in records:
        query = user_turn_for(rec)
        results = retriever.retrieve(query, k=args.k)
        gold = rec["source_doc"]

        top1 = results[0]["source_doc"] if results else None
        topk_docs = {r["source_doc"] for r in results}
        relevant = [
            r
            for r in results
            if r["dense_score"] >= settings.retrieval_min_dense_score
            or r["bm25_score"] >= settings.retrieval_min_bm25_score
        ]
        relevant_docs = {r["source_doc"] for r in relevant}

        if top1 == gold:
            hits_top1 += 1
        if gold in topk_docs:
            hits_topk += 1
        if gold not in relevant_docs:
            gated_out += 1
            misses.append(
                {
                    "id": rec["id"],
                    "gold": gold,
                    "top": [
                        (r["source_doc"], r["section"], round(r["score"], 3), round(r["dense_score"], 3), round(r["bm25_score"], 1))
                        for r in results[:3]
                    ],
                }
            )

    n = len(records)
    print(f"n={n}  top1_hit={hits_top1}/{n} ({hits_top1/n:.1%})  "
          f"top{args.k}_hit={hits_topk}/{n} ({hits_topk/n:.1%})  "
          f"gold_not_in_gated_context={gated_out}/{n} ({gated_out/n:.1%})")

    print("\n--- sample misses (gold not retrieved/gated in) ---")
    for m in misses[:10]:
        print(f"\n{m['id']}\n  gold: {m['gold']}\n  top: {m['top']}")


if __name__ == "__main__":
    main()
