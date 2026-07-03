"""Budget Analysis Agent.

Retrieves financial/commercial-terms chunks from ALL vendor contracts in the
corpus, extracts cost data via a single Groq extraction call, then synthesises
a per-system annual budget table with a grand total.

Unlike single-shot retrieval (which returns the best-matching chunk), this
agent uses a broad financial query to maximise recall across contracts, then
deduplicates by source document so every vendor is represented exactly once
before passing the full set to Groq.

Two-pass Groq flow (both on the fast llama-3.1-8b-instant path):
  1. extract  — structured JSON: [{vendor, system, monthly_fee, annual_fee, ...}]
  2. synthesise — final Markdown table with Indian-comma notation + grand total
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger("nexus.agent.budget_analysis")

# Broad lexical query that BM25 scores highly for commercial-terms sections
# across FM contracts.  Sent to the retriever instead of the user's query so
# that fee/pricing sections from all vendors rank near the top regardless of
# how the user phrased their question.
_FINANCIAL_BM25_QUERY = (
    "commercial terms monthly service fee AMC cost rate pricing payment contract value"
)

_EXTRACT_PROMPT = """\
You are an FM budget analyst. Extract cost data from the contract sections below.

USER QUERY: {query}

CONTRACT SECTIONS:
{chunks}

Return ONLY a valid JSON array (no other text). Each element:
{{
  "vendor": "<vendor name, exact from document>",
  "system": "<FM system type: one of HVAC, Electrical, Fire Safety, Plumbing, \
Security & Surveillance, Lifts & Escalators, BMS, Housekeeping, Civil & Structural, \
Parking & ANPR, Landscaping, or Other>",
  "monthly_fee_inr": <integer or null>,
  "annual_fee_inr": <integer or null>,
  "scope": "<e.g. Comprehensive AMC, Non-comprehensive, Guarding, STP/ETP>",
  "source_doc": "<source document filename>"
}}

Rules:
- If monthly fee is given and annual is null: set annual_fee_inr = monthly_fee_inr * 12
- If annual fee is given and monthly is null: set monthly_fee_inr = round(annual_fee_inr / 12)
- Include ALL distinct cost lines — one element per fee line, even from the same vendor
- Skip sections with no extractable fee figures
- Vendor name: use the exact name as it appears in the header or document title
- Do not invent figures; use null if a value is genuinely absent

Return ONLY the JSON array."""

_SYNTHESIS_PROMPT = """\
You are an FM budget analyst. Using the extracted cost data, produce a budget report.

USER QUERY: {query}
REPORT YEAR: {year}

EXTRACTED DATA:
{data}

Produce exactly:
1. A Markdown table with columns: System | Vendor | Scope | Monthly (INR) | Annual {year} (INR)
2. A **Total** row at the bottom with the sum of all annual costs (leave System/Vendor/Scope blank)
3. One summary line: "**Total {year} facilities management spend: INR X,XX,XXX**"
4. Only if some systems have missing data: one short note starting "Note:"

Formatting rules:
- Use Indian comma notation: 1,00,000 not 100,000
- Bold the Total row amounts
- If a vendor has both comprehensive and non-comprehensive rates show them as separate rows
- Do not add any information not in the extracted data above
- No explanatory paragraphs, no caveats beyond the one "Note:" line"""


@dataclass
class BudgetAnalysisResult:
    answer: str
    chunks_used: list[dict]
    line_items: list[dict] = field(default_factory=list)
    succeeded: bool = True


def run_budget_analysis(
    query: str,
    year: int,
    retriever,
    api_key: str,
    model: str,
) -> BudgetAnalysisResult:
    """Retrieve cost chunks across all contracts, extract, synthesise, return table."""

    # ── Step 1: Retrieve financial sections from the full corpus ─────────────
    # Use a broad BM25-optimised financial query instead of the user's query.
    # Fetch 20 candidates so we get coverage across multiple vendor contracts.
    from app.core.config import settings

    raw_chunks = retriever.retrieve(
        _FINANCIAL_BM25_QUERY,
        k=settings.retrieval_reranker_candidates,  # 20 — full candidate pool
    )

    if not raw_chunks:
        return BudgetAnalysisResult(
            answer="No financial data could be retrieved from the corpus.",
            chunks_used=[],
            succeeded=False,
        )

    # Deduplicate: keep the highest-scoring chunk per source document so every
    # vendor contract is represented once before extraction.
    best_per_doc: dict[str, dict] = {}
    for chunk in raw_chunks:
        doc = chunk["source_doc"]
        if doc not in best_per_doc or chunk["score"] > best_per_doc[doc]["score"]:
            best_per_doc[doc] = chunk
    chunks = list(best_per_doc.values())

    logger.info(
        "budget_analysis: retrieved %d raw chunks → %d unique docs",
        len(raw_chunks), len(chunks),
    )

    # ── Step 2: Extract cost data (Groq, structured JSON) ────────────────────
    chunk_texts = "\n\n---CONTRACT SECTION---\n\n".join(
        f"[Source: {c['source_doc']}]\n{c['text'][:900]}"
        for c in chunks
    )

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        extract_resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _EXTRACT_PROMPT.format(
                query=query[:400],
                chunks=chunk_texts,
            )}],
            max_tokens=900,
            temperature=0.0,
        )
        raw_extract = extract_resp.choices[0].message.content.strip()

        json_match = re.search(r"\[[\s\S]+\]", raw_extract)
        if not json_match:
            raise ValueError(f"No JSON array in extraction response: {raw_extract[:200]}")
        line_items: list[dict] = json.loads(json_match.group())

    except Exception as exc:
        logger.warning("budget extraction Groq call failed (%s) — falling back to SLM", exc)
        return BudgetAnalysisResult(
            answer="",
            chunks_used=chunks,
            succeeded=False,
        )

    if not line_items:
        logger.warning("budget extraction returned no line items")
        return BudgetAnalysisResult(
            answer="No cost figures could be extracted from the retrieved contract sections.",
            chunks_used=chunks,
            succeeded=False,
        )

    logger.info("budget_analysis: extracted %d cost line items", len(line_items))

    # ── Step 3: Synthesise formatted table (Groq) ─────────────────────────────
    try:
        synth_resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _SYNTHESIS_PROMPT.format(
                query=query[:400],
                year=year,
                data=json.dumps(line_items, indent=2),
            )}],
            max_tokens=700,
            temperature=0.0,
        )
        answer = synth_resp.choices[0].message.content.strip()

    except Exception as exc:
        logger.warning("budget synthesis Groq call failed (%s) — using fallback formatter", exc)
        answer = _format_fallback_table(line_items, year)

    return BudgetAnalysisResult(
        answer=answer,
        chunks_used=chunks,
        line_items=line_items,
        succeeded=True,
    )


def _format_fallback_table(line_items: list[dict], year: int) -> str:
    """Plain Python fallback if the synthesis Groq call fails."""
    rows: list[str] = []
    total_annual = 0

    for item in line_items:
        system = item.get("system", "Unknown")
        vendor = item.get("vendor", "Unknown")
        scope = item.get("scope", "")
        monthly = item.get("monthly_fee_inr")
        annual = item.get("annual_fee_inr")

        if monthly is not None and annual is None:
            annual = int(monthly) * 12
        if annual is not None:
            total_annual += int(annual)

        monthly_str = f"{int(monthly):,}" if monthly is not None else "Not specified"
        annual_str = f"{int(annual):,}" if annual is not None else "Not specified"
        rows.append(f"| {system} | {vendor} | {scope} | {monthly_str} | {annual_str} |")

    header = (
        f"| System | Vendor | Scope | Monthly (INR) | Annual {year} (INR) |\n"
        f"| --- | --- | --- | --- | --- |"
    )
    total_row = f"| **Total** | | | | **{total_annual:,}** |"
    summary = f"\n**Total {year} facilities management spend: INR {total_annual:,}**"

    return f"{header}\n" + "\n".join(rows) + f"\n{total_row}{summary}"
