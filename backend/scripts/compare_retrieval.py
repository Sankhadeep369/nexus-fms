"""Retrieval comparison: Conventional BM25+dense vs Entity-Aware (Graph-style).

Runs a set of test queries through both retrievers, compares:
- Which source documents were retrieved
- Whether the top result is from the correct document (precision@1)
- Whether the correct document appears in top-k (recall@k)
- How much cross-contamination exists (competitor docs for vendor queries)

Usage (from 08_rag_app/backend, with venv active):
    python -m scripts.compare_retrieval
"""

from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.core.entity_registry import get_entity_registry
from app.core.retrieval import Retriever, EntityAwareRetriever

# ---------------------------------------------------------------------------
# Test cases: (query, expected_doc_substring, description)
# ---------------------------------------------------------------------------
TEST_CASES = [
    (
        "Tell me about the Summit Lift Services contract terms",
        "current_contracts/05_Summit_Lift_Services",
        "Vendor-specific: Summit Lift current contract",
    ),
    (
        "What are the HVAC AMC terms for Apex Climate Systems?",
        "current_contracts/01_Apex_Climate_Systems",
        "Vendor-specific: Apex Climate HVAC contract",
    ),
    (
        "What does the ClearFlow plumbing contract cover?",
        "current_contracts/11_ClearFlow_Plumbing",
        "Vendor-specific: ClearFlow plumbing contract",
    ),
    (
        "What are the CCTV maintenance terms with Vertex SecureVision?",
        "current_contracts/03_Vertex_SecureVision",
        "Vendor-specific: Vertex CCTV contract",
    ),
    (
        "What are the fire safety agreement terms with BlueShield?",
        "current_contracts/09_BlueShield_Fire",
        "Vendor-specific: BlueShield fire safety",
    ),
    (
        "What is included in the IronGate access control contract?",
        "current_contracts/07_IronGate_Access",
        "Vendor-specific: IronGate access control",
    ),
    (
        "What does NML-FS-2026-005 cover?",
        "current_contracts/05_Summit_Lift",
        "Agreement number lookup",
    ),
    (
        "What PPE is required for electrical maintenance?",
        "domain_docs",
        "General domain query (no specific vendor)",
    ),
    (
        "Compare lift AMC vendors",
        "competitor_contracts",
        "Comparison query — competitor docs are appropriate here",
    ),
    (
        "What is the monthly preventive maintenance checklist for HVAC?",
        "domain_docs",
        "General procedural query",
    ),
]


def _fmt_docs(results: list[dict]) -> str:
    return " | ".join(
        f"{r['source_doc'].split('/')[0][:8]}::{r['source_doc'].split('/')[-1][:25]}"
        for r in results
    )


def _precision_at_1(results: list[dict], expected: str) -> bool:
    return bool(results) and expected in results[0]["source_doc"]


def _recall_at_k(results: list[dict], expected: str) -> bool:
    return any(expected in r["source_doc"] for r in results)


def _contamination(results: list[dict], query_expects_current: bool) -> int:
    """Count competitor comparison docs in results when current contract expected."""
    if not query_expects_current:
        return 0
    return sum(1 for r in results if "competitor_contracts" in r["source_doc"])


def main() -> None:
    print("\nLoading retrievers...")
    conv = Retriever()
    entity = EntityAwareRetriever()
    registry = get_entity_registry()

    print(f"Entity registry: {len(registry._entity_to_docs)} entities indexed")
    print(f"\n{'Query':<50} {'P@1 Conv':>8} {'P@1 Ent':>8} {'Contam Conv':>12} {'Contam Ent':>11}")
    print("-" * 100)

    conv_p1 = entity_p1 = conv_recall = entity_recall = 0
    conv_contam = entity_contam = 0

    for query, expected, desc in TEST_CASES:
        conv_results = conv.retrieve(query)
        entity_results = entity.retrieve(query)
        expects_current = "current_contracts" in expected

        cp1 = _precision_at_1(conv_results, expected)
        ep1 = _precision_at_1(entity_results, expected)
        cr = _recall_at_k(conv_results, expected)
        er = _recall_at_k(entity_results, expected)
        cc = _contamination(conv_results, expects_current)
        ec = _contamination(entity_results, expects_current)

        conv_p1 += cp1; entity_p1 += ep1
        conv_recall += cr; entity_recall += er
        conv_contam += cc; entity_contam += ec

        p1_flag = "" if cp1 == ep1 else (" [ent wins]" if ep1 and not cp1 else " [conv wins]")
        print(f"{query[:50]:<50} {'YES' if cp1 else 'NO':>8} {'YES' if ep1 else 'NO':>8} {cc:>12} {ec:>11}{p1_flag}")

        # Detail: show top-2 docs per retriever
        print(f"  Conv  : {_fmt_docs(conv_results[:3])}")
        print(f"  Entity: {_fmt_docs(entity_results[:3])}")

        if ep1 and not cp1:
            print(f"  *** Entity retrieval correctly anchored to: {entity_results[0]['source_doc']}")
        print()

    n = len(TEST_CASES)
    print("=" * 100)
    print(f"{'METRIC':<40} {'CONVENTIONAL':>15} {'ENTITY-AWARE':>15} {'DELTA':>10}")
    print(f"{'Precision@1':<40} {conv_p1}/{n:>14} {entity_p1}/{n:>14} {entity_p1-conv_p1:>+10}")
    print(f"{'Recall@k':<40} {conv_recall}/{n:>14} {entity_recall}/{n:>14} {entity_recall-conv_recall:>+10}")
    print(f"{'Competitor contamination (vendor queries)':<40} {conv_contam:>15} {entity_contam:>15} {entity_contam-conv_contam:>+10}")
    print("=" * 100)

    if entity_p1 > conv_p1 or entity_contam < conv_contam:
        print("\nVERDICT: Entity-Aware retrieval wins -- deploy to production.")
    elif entity_p1 == conv_p1 and entity_contam == conv_contam:
        print("\nVERDICT: Tie on these queries -- conventional is simpler, keep it.")
    else:
        print("\nVERDICT: Conventional retrieval wins on this query set.")


if __name__ == "__main__":
    main()
