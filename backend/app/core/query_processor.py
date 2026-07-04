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
- "type": one of "incident_triage" | "vendor_decision" | "portfolio_overview" | "budget_analysis" | "vendor" | "factual" | "comparison" | "draft" | "checklist" | "general"

  TYPE SELECTION — apply the FIRST type whose criteria match, in this order:

  * incident_triage — user is REPORTING a live facilities problem right now
                 (e.g. "AC down floor 3", "water leak in basement",
                 "elevator stuck"). Use ONLY for in-progress incidents needing
                 triage and escalation — NOT for historical queries.

  * vendor_decision — user is asking whether THEY should RENEW, SWITCH, or
                 NEGOTIATE their OWN ACTIVE contract with a named vendor.
                 MUST contain first-person language: "should we renew", "should
                 I switch us from", "is our current deal competitive", "do we
                 want to continue with". The vendor referenced must be one we
                 currently have an active contract with.
                 DO NOT use for: market-benchmark comparisons, analysing
                 competitor alternatives, evaluating third-party options that
                 are not our live contracts, or any query that lacks an explicit
                 first-person renewal/switch/negotiate decision framing.

  * portfolio_overview — user wants a LIST or REGISTRY of all current vendors,
                 modules, or active contracts without asking for costs or a spend
                 summary (e.g. "what vendors do we have", "list all modules under
                 contract", "show all active AMC agreements", "who are our FM
                 vendors", "what systems are covered by contracts", "give me an
                 overview of all our agreements"). Covers the entire portfolio.
                 DO NOT use for: cost/budget questions (use budget_analysis),
                 single-vendor lookups (use vendor), comparisons (use comparison).

  * budget_analysis — user wants an AGGREGATED spend summary across the ENTIRE
                 PORTFOLIO of contracts (e.g. "total AMC spend across all vendors",
                 "complete 2026 facilities budget breakdown", "how much are we
                 spending on all systems combined"). The query MUST ask for totals
                 or breakdowns that span multiple separate vendor contracts.
                 DO NOT use for: single-vendor cost queries, individual contract
                 arithmetic, budget variance on one contract, or any query where
                 the key figures are already provided in the user's message.

  * vendor     — asking about the details of ONE specific named vendor's contract
                 (terms, SLA, scope, fees, expiry). Use when the answer comes from
                 reading that one contract. NOT for comparisons or decisions.

  * comparison — comparing two or more vendors, contract options, or market
                 alternatives side by side (e.g. "compare ArcticAir vs Climate
                 Prime Care", "how do these three options stack up", "which
                 alternative is best value", "evaluate these competitor options").
                 Use this for ALL multi-vendor analysis that does NOT have an
                 explicit first-person renewal/switch/negotiate decision framing.
                 Also use for single-vendor budget-variance arithmetic (e.g.
                 "if we switched to X, how much more would we pay").

  * draft      — requesting a document (email, memo, report, alert, template).

  * checklist  — requesting an inspection checklist, step-by-step procedure,
                 maintenance schedule, or ordered task list.

  * factual    — asking for a specific fact, SOP, procedure, explanation, or
                 lookup. Default for single-vendor questions that don't fit the
                 vendor type format.

  * general    — broad best-practices, FM standards, or open-ended knowledge
                 question without a specific document or vendor to look up.

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
- "needs_clarification": true ONLY when the query is SO underspecified that any
  retrieval attempt would return documents completely unrelated to the user's
  intent — e.g. "compare the two" (which two?), "what about this one?" (what?).
  Set false for ALL of the following (this covers almost all FM queries):
  * Any query that names a specific vendor, system, site, or document
  * Any query asking for "all", "every", "total", "each" — the corpus is bounded
  * Budget, cost, or financial queries — budget_analysis agent handles these
  * Comparison queries — retrieve and compare even if scope is broad
  * Checklists, SOPs, procedures, memos — generate from domain knowledge
  * Any query with a clear FM domain (HVAC, electrical, fire, plumbing, etc.)
  In practice, needs_clarification should be true for FEWER THAN 2% of FM queries.
- "clarification_question": if needs_clarification is true, one focused question.
  Empty string if needs_clarification is false.
- "clarification_options": if needs_clarification is true, 3–4 specific options.
  Empty array if needs_clarification is false.

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
        valid_types = ("incident_triage", "vendor_decision", "portfolio_overview", "budget_analysis", "vendor", "factual", "comparison", "draft", "checklist", "general")
        if query_type not in valid_types:
            query_type = "general"
        entities = [str(e) for e in data.get("entities", []) if e]

        needs_clarification = bool(data.get("needs_clarification", False))
        clarification_question = str(data.get("clarification_question", "")).strip()
        clarification_options = [str(o) for o in data.get("clarification_options", []) if o]
        # Never gate these types — either an agent handles them, or standard
        # retrieval can answer them without narrowing scope first.
        if query_type in ("incident_triage", "vendor_decision", "portfolio_overview", "budget_analysis", "draft", "comparison", "vendor", "checklist"):
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
