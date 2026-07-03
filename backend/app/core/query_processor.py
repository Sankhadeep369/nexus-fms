"""Groq-based query pre-processor.

Runs before retrieval on every non-cached user query to:
1. Classify the query type (factual | comparison | draft | checklist | general)
2. Rewrite abbreviated / informal FM queries into clear, full English questions
3. Extract key entities (vendor name, system type, document type) to anchor retrieval

The rewritten query is used for both BM25 and dense retrieval, improving chunk
recall on abbreviated inputs like "compare HVAC AMC renewal clauses" or "SLA
breach plumbing".

Disabled gracefully (returns the raw query as-is) when:
- GROQ_API_KEY is not set
- query_preprocessor_enabled is False
- The Groq call fails for any reason (network error, rate limit, parse error)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date

logger = logging.getLogger("nexus.query_processor")

_ABBREV_REFERENCE = """\
AMC=Annual Maintenance Contract | PPM=Planned Preventive Maintenance |
SLA=Service Level Agreement | NOC=No Objection Certificate |
BMS=Building Management System | ANPR=Automatic Number Plate Recognition |
HSE=Health Safety Environment | UPS=Uninterruptible Power Supply |
DG=Diesel Generator | STP=Sewage Treatment Plant | ETP=Effluent Treatment Plant |
CCTV=Closed-Circuit Television | DDC=Direct Digital Controller |
PPE=Personal Protective Equipment | LOTO=Lockout-Tagout |
NVR=Network Video Recorder | DVR=Digital Video Recorder |
CapEx=Capital Expenditure | OpEx=Operational Expenditure"""

_PREPROCESS_PROMPT = f"""\
You are a facilities-management (FM) query pre-processor.
Today's date: {{today}}.

FM abbreviations for reference:
{_ABBREV_REFERENCE}

Given the user's query, return ONLY a valid JSON object with these fields:
- "type": one of "incident_triage" | "vendor_decision" | "budget_analysis" | "vendor" | "factual" | "comparison" | "draft" | "checklist" | "general"
  * incident_triage — reporting a facilities problem or breakdown that needs triage
                 (e.g. "AC down floor 3 for 2 hours", "water leak in basement",
                 "elevator stuck with people inside"). Requires classifying the
                 incident, finding the responsible vendor, checking SLA, drafting
                 escalation.
  * vendor_decision — asking whether to RENEW, SWITCH, or NEGOTIATE with a vendor,
                 or whether current terms are competitive (e.g. "should we renew with
                 X", "is this a good deal", "should we switch vendors"). Requires
                 researching BOTH the current contract AND competitor benchmarks.
  * budget_analysis — requesting a cost breakdown, total spend, or budget summary
                 ACROSS MULTIPLE systems or the entire portfolio (e.g. "total budget
                 per system", "all AMC costs for 2026", "complete facilities spend
                 breakdown", "how much are we spending on all contracts"). Requires
                 retrieving financial data from ALL vendor contracts and computing
                 annual totals. Use this — NOT factual — when the query asks for
                 multi-system or portfolio-wide cost aggregation.
  * vendor     — asking about a specific vendor's contract terms, agreement details,
                 SLA, pricing, or performance (needs header + table + terse caveat)
  * factual    — asking for a specific fact, procedure, or explanation
  * comparison — comparing multiple vendors, contracts, or options (needs a table)
  * draft      — requesting a document (email, memo, report, template)
  * checklist  — requesting an inspection list, steps, or schedule
  * general    — best-practices, overview, or open-ended FM question
- "rewritten": the query rewritten as a clear, complete English question with
  all abbreviations expanded. IMPORTANT temporal rules for "rewritten":
  * Replace "current year" / "this year" with the actual year from today's date.
  * Replace "this month" with the current month and year (e.g. "July 2026").
  * Replace "YTD" / "year to date" with "January to <current month> <year>".
  * Replace "last year" with the previous calendar year.
  Keep it concise (≤ 2 sentences). Do not add information not implied by the
  original query beyond resolving temporal references.
- "entities": list of key FM entities mentioned (vendor names, system types,
  document types, sites). Empty list if none.
- "needs_clarification": true ONLY when the query asks for aggregated or comparative
  data across multiple unspecified items (e.g. "per system", "all vendors", "total
  budget", "each contract") without naming them, AND a single clarifying question
  would yield a dramatically more accurate answer. false for:
  * queries that name a specific vendor or system
  * incident_triage or vendor_decision queries (they have their own handling)
  * queries with one clear reasonable interpretation
  * purely conversational or definitional questions
- "clarification_question": if needs_clarification is true, one focused question
  to ask (e.g. "Which systems should I include in the budget breakdown?").
  Empty string if needs_clarification is false.
- "clarification_options": if needs_clarification is true, 3–4 specific FM-relevant
  options the user can tap to answer (e.g. ["All active AMC contracts",
  "HVAC & MEP systems only", "Fire & Safety only", "Specify a system"]). These must
  be actionable — not generic "yes/no/maybe". Empty array if needs_clarification is false.

Respond with ONLY the JSON object. No other text.

User query: {{query}}"""


@dataclass
class ProcessedQuery:
    original: str
    rewritten: str
    query_type: str = "general"
    entities: list[str] = field(default_factory=list)
    preprocessed: bool = False
    needs_clarification: bool = False
    clarification_question: str = ""
    clarification_options: list[str] = field(default_factory=list)


def preprocess(query: str, api_key: str, model: str) -> ProcessedQuery:
    """Rewrite and classify the query. Returns a ProcessedQuery with the
    rewritten text and metadata. On any failure returns the original query."""
    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        today_str = date.today().strftime("%d %B %Y")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": _PREPROCESS_PROMPT.format(query=query[:800], today=today_str),
                }
            ],
            max_tokens=350,
            temperature=0.0,
        )

        raw = response.choices[0].message.content.strip()
        json_match = re.search(r"\{[^{}]+\}", raw, re.DOTALL)
        if not json_match:
            raise ValueError(f"no JSON in response: {raw[:100]}")

        clean_json = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", json_match.group())
        data = json.loads(clean_json, strict=False)
        rewritten = str(data.get("rewritten", query)).strip() or query
        query_type = str(data.get("type", "general"))
        valid_types = ("incident_triage", "vendor_decision", "budget_analysis", "vendor", "factual", "comparison", "draft", "checklist", "general")
        if query_type not in valid_types:
            query_type = "general"
        entities = [str(e) for e in data.get("entities", []) if e]

        needs_clarification = bool(data.get("needs_clarification", False))
        clarification_question = str(data.get("clarification_question", "")).strip()
        clarification_options = [str(o) for o in data.get("clarification_options", []) if o]
        # Agent-routed types handle their own scope resolution — never gate them.
        if query_type in ("incident_triage", "vendor_decision", "budget_analysis", "draft"):
            needs_clarification = False
            clarification_question = ""
            clarification_options = []
        # Require both question and options for clarification to be considered valid.
        if not clarification_question or not clarification_options:
            needs_clarification = False

        logger.info(
            "query preprocessed: type=%s entities=%s clarify=%s",
            query_type, entities, needs_clarification,
        )
        return ProcessedQuery(
            original=query,
            rewritten=rewritten,
            query_type=query_type,
            entities=entities,
            preprocessed=True,
            needs_clarification=needs_clarification,
            clarification_question=clarification_question,
            clarification_options=clarification_options,
        )

    except Exception as exc:
        logger.warning("query preprocessor failed (%s) — using raw query", exc)
        return ProcessedQuery(original=query, rewritten=query, preprocessed=False)
