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

FM abbreviations for reference:
{_ABBREV_REFERENCE}

Given the user's query, return ONLY a valid JSON object with these fields:
- "type": one of "incident_triage" | "vendor_decision" | "vendor" | "factual" | "comparison" | "draft" | "checklist" | "general"
  * incident_triage — reporting a facilities problem or breakdown that needs triage
                 (e.g. "AC down floor 3 for 2 hours", "water leak in basement",
                 "elevator stuck with people inside"). Requires classifying the
                 incident, finding the responsible vendor, checking SLA, drafting
                 escalation.
  * vendor_decision — asking whether to RENEW, SWITCH, or NEGOTIATE with a vendor,
                 or whether current terms are competitive (e.g. "should we renew with
                 X", "is this a good deal", "should we switch vendors"). Requires
                 researching BOTH the current contract AND competitor benchmarks.
  * vendor     — asking about a specific vendor's contract terms, agreement details,
                 SLA, pricing, or performance (needs header + table + terse caveat)
  * factual    — asking for a specific fact, procedure, or explanation
  * comparison — comparing multiple vendors, contracts, or options (needs a table)
  * draft      — requesting a document (email, memo, report, template)
  * checklist  — requesting an inspection list, steps, or schedule
  * general    — best-practices, overview, or open-ended FM question
- "rewritten": the query rewritten as a clear, complete English question with
  all abbreviations expanded. Keep it concise (≤ 2 sentences). Do not add
  information not implied by the original query.
- "entities": list of key FM entities mentioned (vendor names, system types,
  document types, sites). Empty list if none.

Respond with ONLY the JSON object. No other text.

User query: {{query}}"""


@dataclass
class ProcessedQuery:
    original: str
    rewritten: str
    query_type: str = "general"
    entities: list[str] = field(default_factory=list)
    preprocessed: bool = False


def preprocess(query: str, api_key: str, model: str) -> ProcessedQuery:
    """Rewrite and classify the query. Returns a ProcessedQuery with the
    rewritten text and metadata. On any failure returns the original query."""
    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": _PREPROCESS_PROMPT.format(query=query[:800]),
                }
            ],
            max_tokens=200,
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
        valid_types = ("incident_triage", "vendor_decision", "vendor", "factual", "comparison", "draft", "checklist", "general")
        if query_type not in valid_types:
            query_type = "general"
        entities = [str(e) for e in data.get("entities", []) if e]

        logger.info("query preprocessed: type=%s entities=%s", query_type, entities)
        return ProcessedQuery(
            original=query,
            rewritten=rewritten,
            query_type=query_type,
            entities=entities,
            preprocessed=True,
        )

    except Exception as exc:
        logger.warning("query preprocessor failed (%s) — using raw query", exc)
        return ProcessedQuery(original=query, rewritten=query, preprocessed=False)
