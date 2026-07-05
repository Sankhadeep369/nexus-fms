"""Budget Analysis Agent (orchestration layer — grounded computation).

Reads the recurring-fee facts for every CURRENT contract straight from the
self-describing corpus index (currency, monthly/annual fee, extracted once at
ingest), then computes the annual budget deterministically in Python and formats
the table without any LLM synthesis.

This replaces the previous top-k-retrieval + two-pass-Groq approach, which
suffered three failures: incomplete coverage (top-k returned only a handful of
the 20 contracts), ungrounded totals (the synthesis LLM invented a grand total),
and currency confusion (fields were hardcoded as INR while the contracts are in
USD).  Every number here is computed, so it always reconciles.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("nexus.agent.budget_analysis")


@dataclass
class BudgetAnalysisResult:
    answer: str
    chunks_used: list[dict]
    line_items: list[dict] = field(default_factory=list)
    succeeded: bool = True


def _fmt(amount: float, currency: str) -> str:
    """Currency-aware amount, thousands-grouped, no trailing .0 for whole numbers."""
    n = int(round(amount)) if abs(amount - round(amount)) < 0.005 else amount
    body = f"{n:,}" if isinstance(n, int) else f"{n:,.2f}"
    symbol = {"USD": "$", "INR": "₹"}.get(currency, "")
    return f"{symbol}{body}" if symbol else f"{body} {currency}".strip()


def run_budget_analysis(
    query: str,
    year: int,
    retriever,
    api_key: str,
    model: str,
) -> BudgetAnalysisResult:
    """Compute the annual budget across all current contracts from indexed facts."""
    from app.core.corpus_index import get_corpus_index

    ci = get_corpus_index()
    current = ci.current_docs
    if not current:
        return BudgetAnalysisResult(
            answer="No current contracts are present in the corpus.",
            chunks_used=[], succeeded=False,
        )

    # Build one grounded line item per contract, grouped by currency so mixed-
    # currency portfolios are summed correctly (never added across currencies).
    line_items: list[dict] = []
    for m in current:
        line_items.append({
            "system": m.system or m.category or "Not specified",
            "vendor": m.vendor or "Not specified",
            "site": m.site or "Not specified",
            "currency": m.currency,
            "monthly": m.monthly_value(),
            "annual": m.annual_value(),
            "source_doc": m.source_doc,
        })

    priced = [li for li in line_items if li["annual"] is not None and li["currency"]]
    if not priced:
        return BudgetAnalysisResult(
            answer="No recurring-fee data is available for the current contracts.",
            chunks_used=[], line_items=line_items, succeeded=False,
        )

    answer = _format_budget(line_items, year)
    chunks_used = _provenance(retriever, {li["source_doc"] for li in priced})
    logger.info(
        "budget_analysis: %d contracts priced (of %d), currencies=%s",
        len(priced), len(current), sorted({li["currency"] for li in priced}),
    )
    return BudgetAnalysisResult(
        answer=answer, chunks_used=chunks_used, line_items=line_items, succeeded=True,
    )


def _format_budget(items: list[dict], year: int) -> str:
    """Deterministic Markdown: per-currency table + totals. No LLM, so the numbers
    always reconcile with the rows."""
    by_currency: dict[str, list[dict]] = {}
    for li in items:
        if li["annual"] is None or not li["currency"]:
            continue
        by_currency.setdefault(li["currency"], []).append(li)

    out: list[str] = []
    for currency in sorted(by_currency):
        rows = sorted(by_currency[currency], key=lambda x: (x["system"].lower(), x["vendor"].lower()))
        out.append(f"| System | Vendor | Site | Monthly ({currency}) | Annual {year} ({currency}) |")
        out.append("| --- | --- | --- | --- | --- |")
        total = 0.0
        for li in rows:
            total += li["annual"]
            out.append(
                f"| {li['system']} | {li['vendor']} | {li['site']} | "
                f"{_fmt(li['monthly'], currency)} | {_fmt(li['annual'], currency)} |"
            )
        out.append(f"| **Total** | | | | **{_fmt(total, currency)}** |")
        out.append("")
        out.append(f"**Total {year} facilities spend ({currency}): {_fmt(total, currency)}** "
                   f"across {len(rows)} contracts.")
        out.append("")

    # Flag any contracts with no recurring fee so the reader knows the total's scope.
    unpriced = [li for li in items if li["annual"] is None]
    if unpriced:
        names = ", ".join(sorted({li["vendor"] for li in unpriced}))
        out.append(f"*Excluded (no recurring fee on file): {names}.*")

    return "\n".join(out).strip()


def _provenance(retriever, source_docs: set[str]) -> list[dict]:
    """First indexed chunk per contributing contract, for source attribution /
    G-Eval — the figures come from the index, this is just where they live."""
    chunks: list[dict] = []
    seen: set[str] = set()
    if retriever is not None and hasattr(retriever, "chunks"):
        for c in retriever.chunks:
            if c.source_doc in source_docs and c.source_doc not in seen:
                seen.add(c.source_doc)
                chunks.append({"source_doc": c.source_doc, "section": c.section, "text": c.text})
    return chunks
