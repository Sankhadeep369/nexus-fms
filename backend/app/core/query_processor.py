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

from app.core.capabilities import (
    capability_names,
    classifier_type_block,
    classifier_type_enum,
    is_temporal_query,
    never_clarify_names,
)

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
- "type": one of {classifier_type_enum()}

  TYPE SELECTION — apply the FIRST type whose criteria match, in this order:

{classifier_type_block()}

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
- "in_scope": true if the question can be answered from facilities-management
  CONTRACT data (vendors, contracts, costs, fees, SLAs, renewals/expiry, systems,
  FM procedures/SOPs). false ONLY for clearly unrelated topics (weather, sports,
  news, general trivia, coding, personal chat, cooking). When unsure, use true.
- "action_request": true ONLY if the user asks NEXUS to PERFORM an action it cannot
  do — book/schedule a service, send/email/call a vendor, actually renew, sign,
  cancel, or pay for a contract. Writing/drafting a document is NOT an action
  (that is the draft type). false otherwise.
- "missing_data": if the question depends on data NOT held in FM contracts (e.g.
  compliance certificates, warranties, square footage / area, headcount, live
  energy/meter readings, real-time sensor status), name that data type in 2-4
  words; otherwise empty string "".
- "suggested_question": ONLY when in_scope is false, action_request is true, or
  missing_data is set — the single closest question NEXUS CAN answer from contract
  data, phrased the way the user would ask it. Otherwise empty string "".

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
    # Layer B honesty signals.
    in_scope: bool = True
    action_request: bool = False
    missing_data: str = ""
    suggested_question: str = ""


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
            max_tokens=480,
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
        if query_type not in capability_names():
            query_type = "general"
        # Deterministic temporal override: renewal/expiry TIMING questions route to
        # the contract_timeline agent regardless of the classifier, which tends to
        # mislabel them (e.g. as budget_analysis) on the "contract" keyword.
        if is_temporal_query(query):
            query_type = "contract_timeline"
        entities = [str(e) for e in data.get("entities", []) if e]

        needs_clarification = bool(data.get("needs_clarification", False))
        clarification_question = str(data.get("clarification_question", "")).strip()
        clarification_options = [str(o) for o in data.get("clarification_options", []) if o]
        # Never gate these types — either an agent handles them, or standard
        # retrieval can answer them without narrowing scope first. Driven by the
        # capability registry (never_clarify flag), not a hardcoded list.
        if query_type in never_clarify_names():
            needs_clarification = False
            clarification_question = ""
            clarification_options = []
        # Require both question and options for clarification to be considered valid.
        if not clarification_question or not clarification_options:
            needs_clarification = False

        # Layer B honesty signals. Default to permissive (in_scope=True) so a
        # classifier hiccup never wrongly declines a real FM question.
        in_scope = bool(data.get("in_scope", True))
        action_request = bool(data.get("action_request", False))
        missing_data = str(data.get("missing_data", "")).strip()
        suggested_question = str(data.get("suggested_question", "")).strip()
        # A recognised structured/agent intent is definitionally in scope — don't let
        # a stray in_scope=false decline it.
        if query_type != "general":
            in_scope = True

        logger.info(
            "query preprocessed: type=%s entities=%s clarify=%s in_scope=%s action=%s",
            query_type, entities, needs_clarification, in_scope, action_request,
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
            in_scope=in_scope,
            action_request=action_request,
            missing_data=missing_data,
            suggested_question=suggested_question,
        )

    except Exception as exc:
        logger.warning("query preprocessor failed (%s) — using raw query", exc)
        # The temporal override is deterministic and must still apply even when the
        # Groq classifier is unavailable (e.g. rate-limited), so renewal/expiry
        # timing questions still reach the contract_timeline agent.
        qtype = "contract_timeline" if is_temporal_query(query) else "general"
        return ProcessedQuery(
            original=query, rewritten=query, query_type=qtype, preprocessed=False,
        )
