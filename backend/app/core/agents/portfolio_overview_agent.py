"""Portfolio Overview Agent.

Retrieves contract header/parties sections from ALL current vendor contracts,
extracts structured records via Groq, and synthesises a clean Markdown table
of all active agreements.

Unlike budget_analysis (financial terms focus), this agent targets parties,
category, agreement-number, and scope-of-services headers so the user can
see who their vendors are and what systems are covered — without cost data.

Two-pass Groq flow:
  1. extract  — [{system, vendor, category, agreement_no, term, site}]
  2. synthesise — clean table sorted by system, with total count
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger("nexus.agent.portfolio_overview")

# Targets the "Section 1: Parties", header tables, and scope-of-services sections
# that every current contract document has.  "current contracts" helps BM25 rank
# internal documents over competitor-benchmark comparisons.
_HEADER_BM25_QUERY = (
    "vendor client agreement number category effective date term service scope parties"
)

_EXTRACT_PROMPT = """\
You are an FM contract analyst. Extract the active contract portfolio from the sections below.

USER QUERY: {query}

CONTRACT SECTIONS:
{chunks}

Return ONLY a valid JSON array (no other text). Each element:
{{
  "system": "<FM system type: HVAC, Electrical, Fire Safety, Plumbing, Security & CCTV, \
Lifts & Escalators, BMS, Housekeeping & Pest Control, Civil & Structural, Parking & ANPR, \
Access Control, Landscaping, Generator & UPS, or Other>",
  "vendor": "<exact vendor/company name from document header>",
  "category": "<service category as stated in the document, e.g. 'Lift Modernization', \
'HVAC AMC', 'Guarding & CCTV', 'Access Control'>",
  "agreement_no": "<agreement or contract number if present, else null>",
  "term": "<contract term string if present, e.g. '12 months from 08 May 2026', else null>",
  "source_doc": "<source document filename>"
}}

Rules:
- ONE element per distinct vendor contract document
- Include ONLY current/active contracts — skip competitor or market-benchmark documents
  (those have titles like "Comparison" or "Market Alternative")
- Use the exact vendor legal name from the document header or parties section
- For system type, choose the best-matching FM category from the list above
- If a field is absent, use null — do not invent values

Return ONLY the JSON array."""

_SYNTHESIS_PROMPT = """\
You are an FM contract analyst. Produce a clean contract registry from the data below.

USER QUERY: {query}

EXTRACTED CONTRACT RECORDS:
{data}

Produce exactly:
1. A Markdown table with columns: | System | Vendor | Category | Agreement No. | Term |
2. One line below the table: "**Total active agreements: N**" (N = number of table rows)
3. One short note ONLY if more than 2 records have missing agreement numbers.

Rules:
- Sort rows alphabetically by System
- Use **Not specified** for any null field
- No recommendations, no analysis, no caveats beyond the missing-number note
- Do not add information not in the extracted data"""


@dataclass
class PortfolioOverviewResult:
    answer: str
    chunks_used: list[dict]
    contracts: list[dict] = field(default_factory=list)
    succeeded: bool = True


def _direct_contract_headers(retriever) -> list[dict]:
    """Walk retriever.chunks directly and take the FIRST section chunk from each
    current_contracts document.

    This bypasses top-k retrieval entirely — for a portfolio listing we want ALL
    documents, not just the best-matching ones, and the first section of each
    contract (typically "Parties and Site Details") already contains the vendor
    name, category, agreement number, and term that Groq needs to extract.

    Every chunk has the document header block prepended (see retrieval.py), so
    even non-header sections carry the identity info, but the first section is the
    cleanest and shortest input to the extraction prompt.
    """
    if not hasattr(retriever, "chunks") or not retriever.chunks:
        return []

    # Chunks are loaded in sorted(path) order, sections in document order —
    # so the first chunk seen for each source_doc is the first section.
    seen: dict[str, dict] = {}
    for chunk in retriever.chunks:
        if "current_contracts" not in chunk.source_doc:
            continue
        if chunk.source_doc not in seen:
            seen[chunk.source_doc] = {
                "source_doc": chunk.source_doc,
                "section": chunk.section,
                "text": chunk.text,
                "score": 0.0,
            }

    return list(seen.values())


def run_portfolio_overview(
    query: str,
    retriever,
    api_key: str,
    model: str,
) -> PortfolioOverviewResult:
    """Read contract headers from ALL current_contracts docs, extract, synthesise."""

    # Direct enumeration — guaranteed 100% coverage of every current_contracts file.
    # Falls back to BM25 retrieve() only if the chunk store isn't accessible.
    chunks = _direct_contract_headers(retriever)

    if not chunks:
        logger.warning("portfolio_overview: chunk store unavailable, falling back to retrieve()")
        raw = retriever.retrieve(_HEADER_BM25_QUERY, k=40)
        chunks = [c for c in raw if "current_contracts" in c.get("source_doc", "")]
        # One chunk per doc from the fallback set
        seen: dict[str, dict] = {}
        for c in chunks:
            if c["source_doc"] not in seen:
                seen[c["source_doc"]] = c
        chunks = list(seen.values())

    if not chunks:
        return PortfolioOverviewResult(
            answer="No contract data could be retrieved from the corpus.",
            chunks_used=[],
            succeeded=False,
        )

    logger.info("portfolio_overview: %d unique current_contracts docs found", len(chunks))

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
            max_tokens=1000,
            temperature=0.0,
        )
        raw_extract = extract_resp.choices[0].message.content.strip()

        json_match = re.search(r"\[[\s\S]+\]", raw_extract)
        if not json_match:
            raise ValueError(f"No JSON array in response: {raw_extract[:200]}")
        contracts: list[dict] = json.loads(json_match.group())

    except Exception as exc:
        logger.warning("portfolio extraction Groq call failed (%s) — falling back to SLM", exc)
        return PortfolioOverviewResult(answer="", chunks_used=chunks, succeeded=False)

    if not contracts:
        return PortfolioOverviewResult(
            answer="No contract records could be extracted from the retrieved sections.",
            chunks_used=chunks,
            succeeded=False,
        )

    logger.info("portfolio_overview: extracted %d contract records", len(contracts))

    try:
        synth_resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _SYNTHESIS_PROMPT.format(
                query=query[:400],
                data=json.dumps(contracts, indent=2),
            )}],
            max_tokens=800,
            temperature=0.0,
        )
        answer = synth_resp.choices[0].message.content.strip()

    except Exception as exc:
        logger.warning("portfolio synthesis Groq call failed (%s) — using fallback", exc)
        answer = _format_fallback_table(contracts)

    return PortfolioOverviewResult(
        answer=answer,
        chunks_used=chunks,
        contracts=contracts,
        succeeded=True,
    )


def _format_fallback_table(contracts: list[dict]) -> str:
    sorted_c = sorted(contracts, key=lambda c: (c.get("system") or "").lower())
    rows = []
    for c in sorted_c:
        system = c.get("system") or "Not specified"
        vendor = c.get("vendor") or "Not specified"
        category = c.get("category") or "Not specified"
        agno = c.get("agreement_no") or "Not specified"
        term = c.get("term") or "Not specified"
        rows.append(f"| {system} | {vendor} | {category} | {agno} | {term} |")

    header = "| System | Vendor | Category | Agreement No. | Term |\n| --- | --- | --- | --- | --- |"
    total = f"\n\n**Total active agreements: {len(contracts)}**"
    return f"{header}\n" + "\n".join(rows) + total
