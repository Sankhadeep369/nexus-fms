"""Portfolio Overview Agent (orchestration layer — grounded, deterministic).

Produces the registry of every CURRENT contract directly from the self-describing
corpus index (vendor / system / category / agreement / term / site, extracted once
at ingest). The table is formatted in Python — no LLM synthesis — so it always has
100% coverage of the 20 contracts, a Site column to disambiguate a vendor's two
sites, and no hallucinated footnotes (the previous Groq synthesis invented a
"missing agreement numbers" note and mis-placed an agreement title in the Term
column).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("nexus.agent.portfolio_overview")


@dataclass
class PortfolioOverviewResult:
    answer: str
    chunks_used: list[dict]
    contracts: list[dict] = field(default_factory=list)
    succeeded: bool = True


def run_portfolio_overview(
    query: str,
    retriever,
    api_key: str,
    model: str,
) -> PortfolioOverviewResult:
    """Build the active-contract registry from indexed facts and format it."""
    from app.core.corpus_index import get_corpus_index

    current = get_corpus_index().current_docs
    if not current:
        return PortfolioOverviewResult(
            answer="No current contracts are present in the corpus.",
            chunks_used=[], succeeded=False,
        )

    contracts = [
        {
            "system": m.system or m.category or "Not specified",
            "vendor": m.vendor or "Not specified",
            "site": m.site or "Not specified",
            "category": m.category or "Not specified",
            "agreement_no": m.agreement_no or "Not specified",
            "term": m.term or "Not specified",
            "source_doc": m.source_doc,
        }
        for m in current
    ]

    answer = _format_registry(contracts)
    chunks_used = _provenance(retriever, {c["source_doc"] for c in contracts})
    logger.info("portfolio_overview: %d current contracts (deterministic)", len(contracts))
    return PortfolioOverviewResult(
        answer=answer, chunks_used=chunks_used, contracts=contracts, succeeded=True,
    )


def _format_registry(contracts: list[dict]) -> str:
    rows = sorted(contracts, key=lambda c: (c["system"].lower(), c["vendor"].lower(), c["site"].lower()))
    out = [
        "| System | Vendor | Site | Agreement No. | Term |",
        "| --- | --- | --- | --- | --- |",
    ]
    for c in rows:
        out.append(
            f"| {c['system']} | {c['vendor']} | {c['site']} | {c['agreement_no']} | {c['term']} |"
        )
    out.append("")
    out.append(f"**Total active agreements: {len(contracts)}**")
    return "\n".join(out)


def _provenance(retriever, source_docs: set[str]) -> list[dict]:
    """First indexed chunk per contract, for source attribution / G-Eval."""
    chunks: list[dict] = []
    seen: set[str] = set()
    if retriever is not None and hasattr(retriever, "chunks"):
        for c in retriever.chunks:
            if c.source_doc in source_docs and c.source_doc not in seen:
                seen.add(c.source_doc)
                chunks.append({"source_doc": c.source_doc, "section": c.section, "text": c.text})
    return chunks
