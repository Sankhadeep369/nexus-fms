"""Contract Timeline Agent — grounded renewal / expiry / "days until" questions.

Computes each current contract's renewal date (effective_date + term) and the
days-from-today entirely in Python from the corpus index, then lets Groq answer
the user's specific temporal question from that deterministic timeline:
  - "how many days until the HVAC contract renewal"
  - "when does our fire safety contract expire"
  - "which contracts are up for renewal in the next 60 days"

Every date and day-count is COMPUTED — never guessed by the model. Groq only
interprets which contract(s) the question is about and phrases the answer, so the
numbers are always grounded. Falls back to a deterministic table if Groq fails.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date

from app.core.agents._common import provenance_chunks

logger = logging.getLogger("nexus.agent.contract_timeline")

_SYNTH_PROMPT = """\
You are an FM contract analyst. Today's date is {today}. Answer the user's question
using ONLY the contract timeline data below. Every renewal date and days_until value
is already computed and correct — do NOT recompute or invent any date or number.

USER QUESTION: {query}

CONTRACT TIMELINE (JSON; days_until is days from today to renewal, negative = overdue):
{rows}

Rules:
- If the question is about ONE system/vendor, answer in a single direct sentence,
  stating the number of days (and the renewal date). Example: "The HVAC contract with
  Apex renews on 08 May 2027 — 300 days from today."
- If the question asks which contracts renew within a period (e.g. next 60 days),
  list only the matching ones as "System — Vendor — renews DD Mon YYYY (N days)".
- If it asks for the whole schedule, give a compact Markdown table:
  | System | Vendor | Renews | Days from today |
- Use "Not specified" where a renewal date is missing. English only, concise, no
  preamble, no invented figures."""


@dataclass
class ContractTimelineResult:
    answer: str
    chunks_used: list[dict]
    rows: list[dict] = field(default_factory=list)
    succeeded: bool = True


def run_contract_timeline(
    query: str,
    retriever,
    api_key: str,
    model: str,
) -> ContractTimelineResult:
    """Build the renewal timeline from indexed facts, then synthesise the answer."""
    from app.core.corpus_index import get_corpus_index

    ci = get_corpus_index()
    today = date.today()
    rows: list[dict] = []
    for m in ci.current_docs:
        rd = m.renewal_date()
        rows.append({
            "system": m.system or m.category or "Not specified",
            "vendor": m.vendor or "Not specified",
            "site": m.site or "Not specified",
            "effective_date": m.effective_date or "Not specified",
            "term": m.term or (f"{m.term_months} months" if m.term_months else "Not specified"),
            "renewal_date": rd.strftime("%d %b %Y") if rd else "Not specified",
            "days_until": (rd - today).days if rd else None,
            "source_doc": m.source_doc,
        })

    if not any(r["days_until"] is not None for r in rows):
        return ContractTimelineResult(
            answer="Contract renewal dates are not available on file (missing effective "
                   "date or term).",
            chunks_used=[], rows=rows, succeeded=False,
        )

    chunks_used = provenance_chunks(retriever, {r["source_doc"] for r in rows})

    # Groq interprets the question over the deterministic timeline (dates grounded).
    try:
        from groq import Groq

        # Trim the payload the model sees (drop source_doc/site noise).
        slim = [{k: r[k] for k in ("system", "vendor", "renewal_date", "days_until")} for r in rows]
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _SYNTH_PROMPT.format(
                today=today.strftime("%d %B %Y"),
                query=query[:400],
                rows=json.dumps(slim, indent=2),
            )}],
            max_tokens=600,
            temperature=0.0,
        )
        answer = resp.choices[0].message.content.strip()
        if not answer:
            raise ValueError("empty synthesis")
    except Exception as exc:
        logger.warning("timeline synthesis failed (%s) — using deterministic table", exc)
        answer = _format_table(rows)

    logger.info("contract_timeline: %d contracts, %d with renewal dates",
                len(rows), sum(1 for r in rows if r["days_until"] is not None))
    return ContractTimelineResult(answer=answer, chunks_used=chunks_used, rows=rows, succeeded=True)


def _format_table(rows: list[dict]) -> str:
    ordered = sorted(
        rows, key=lambda r: (r["days_until"] if r["days_until"] is not None else 10**9)
    )
    out = ["| System | Vendor | Renews | Days from today |", "| --- | --- | --- | --- |"]
    for r in ordered:
        days = r["days_until"] if r["days_until"] is not None else "Not specified"
        out.append(f"| {r['system']} | {r['vendor']} | {r['renewal_date']} | {days} |")
    return "\n".join(out)


