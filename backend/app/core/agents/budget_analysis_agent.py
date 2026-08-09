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

from app.core.agents._common import provenance_chunks

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
    """Compute the annual budget across all current contracts from indexed facts,
    then answer the SPECIFIC question asked (site-wise / system-wise / vendor-wise
    breakdown, next-year projection, multi-part, …). Every figure is pre-computed
    in Python and handed to the LLM, which only selects/formats — it never does
    arithmetic — so numbers always reconcile. Falls back to the deterministic
    system-wise table if the LLM is unavailable."""
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

    # Answer the actual question over pre-computed aggregations (grounded, flexible);
    # deterministic system-wise table is the fallback when the LLM is unavailable.
    answer = None
    if api_key:
        answer = _synthesize_budget(query, _grounded_facts(line_items, year), api_key, model)
    if not answer:
        answer = _format_budget(line_items, year)

    chunks_used = provenance_chunks(retriever, {li["source_doc"] for li in priced})
    logger.info(
        "budget_analysis: %d contracts priced (of %d), currencies=%s, synthesised=%s",
        len(priced), len(current), sorted({li["currency"] for li in priced}), bool(api_key),
    )
    return BudgetAnalysisResult(
        answer=answer, chunks_used=chunks_used, line_items=line_items, succeeded=True,
    )


def _aggregate(items: list[dict]) -> dict[str, dict]:
    """Per-currency grand total + breakdowns by system/site/vendor. All summed in
    Python so the LLM never has to (and never mis-)compute a figure."""
    aggs: dict[str, dict] = {}
    for li in items:
        if li["annual"] is None or not li["currency"]:
            continue
        cur = li["currency"]
        a = aggs.setdefault(cur, {"total": 0.0, "count": 0, "by_system": {}, "by_site": {}, "by_vendor": {}})
        a["total"] += li["annual"]
        a["count"] += 1
        for dim, key in (("by_system", li["system"]), ("by_site", li["site"]), ("by_vendor", li["vendor"])):
            a[dim][key] = a[dim].get(key, 0.0) + li["annual"]
    return aggs


def _grounded_facts(items: list[dict], year: int) -> str:
    aggs = _aggregate(items)
    lines = [
        "CONTRACT COST FACTS — every figure below is pre-computed and final. "
        "Use these exact numbers; do NOT add, subtract, average, re-compute, or invent any figure.\n"
    ]
    for cur in sorted(aggs):
        a = aggs[cur]

        def _kv(d: dict) -> str:
            return "; ".join(f"{k}: {_fmt(v, cur)}" for k, v in sorted(d.items(), key=lambda x: -x[1]))

        lines.append(f"Currency: {cur}")
        lines.append(f"- Grand total (annual, {year}): {_fmt(a['total'], cur)} across {a['count']} contracts")
        lines.append(
            f"- Projected next year ({year + 1}), assuming renewal at current rates "
            f"(no escalation clause on file): {_fmt(a['total'], cur)}"
        )
        lines.append(f"- By site: {_kv(a['by_site'])}")
        lines.append(f"- By system: {_kv(a['by_system'])}")
        lines.append(f"- By vendor: {_kv(a['by_vendor'])}")
        lines.append("- Per contract (system | vendor | site | annual):")
        for li in sorted((x for x in items if x["currency"] == cur and x["annual"] is not None),
                         key=lambda x: (x["system"].lower(), x["vendor"].lower())):
            lines.append(f"    {li['system']} | {li['vendor']} | {li['site']} | {_fmt(li['annual'], cur)}")
        lines.append("")

    unpriced = [li for li in items if li["annual"] is None]
    if unpriced:
        lines.append(f"Excluded (no recurring fee on file): {', '.join(sorted({li['vendor'] for li in unpriced}))}.")
    return "\n".join(lines).strip()


_SYNTH_PROMPT = """\
You are a facilities budget assistant. Answer the user's question using ONLY the \
pre-computed figures below.

Rules:
- Every total and breakdown is already computed and final — use these exact numbers. \
Do NOT add, subtract, average, re-compute, or invent ANY figure.
- Present exactly the breakdown asked for: site-wise = one row per site; system-wise = \
one row per system; vendor-wise = one row per vendor. Use a Markdown table with a clear total row.
- If the question is about next year / a projection / forecast, use the projected figure \
and note it assumes renewal at current rates.
- If the question has multiple parts, answer EACH part.
- Never mix or sum across different currencies; show each currency separately.
- If a requested breakdown or figure is not in the facts, say so briefly and give the \
closest available — do not compute it yourself.
- Be concise, no preamble.

{facts}

User question: {query}"""


def _synthesize_budget(query: str, facts: str, api_key: str, model: str) -> str | None:
    try:
        from groq import Groq

        client = Groq(api_key=api_key, max_retries=1)
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _SYNTH_PROMPT.format(facts=facts, query=query[:400])}],
            max_tokens=700,
            temperature=0.0,
        )
        return (r.choices[0].message.content or "").strip() or None
    except Exception as exc:
        logger.warning("budget synthesis failed (%s) — using deterministic table", exc)
        return None


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


