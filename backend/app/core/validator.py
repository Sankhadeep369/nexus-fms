"""Two-layer output pipeline: rule-based filter → Groq rewriter/validator.

Layer 1 — rule-based (instant, no API call):
  Detects non-Latin script contamination and rejects trivially short answers.

Layer 2 — Groq rewriter+validator (1-2s, single API call):
  In one call, Groq both validates AND rewrites the answer:
  - Validates: English only, grounded in context, coherent
  - Rewrites: condenses verbosity, removes padding, enforces correct format
    for the query type (table for comparisons, numbered list for checklists, etc.)
  - If fundamentally wrong: returns invalid signal → fallback shown to user

Single-call design keeps latency low (one round-trip instead of two).
Fail-open: any Groq error passes the answer through unchanged so a config
issue never silently breaks the chat endpoint.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger("nexus.validator")

_NON_LATIN_SCRIPTS = re.compile(
    r"["
    r"؀-ۿ"   # Arabic
    r"ऀ-ॿ"   # Devanagari (Hindi)
    r"ঀ-৿"   # Bengali
    r"฀-๿"   # Thai
    r"一-鿿"   # CJK Unified Ideographs
    r"぀-ヿ"   # Hiragana / Katakana
    r"가-힯"   # Hangul
    r"]"
)

_MIN_ANSWER_LENGTH = 40

_REWRITE_PROMPT = """\
You are a quality-control rewriter for NEXUS, an AI facilities-management assistant.

ORIGINAL QUERY: {query}
QUERY TYPE: {query_type}
(vendor=contract/agreement details, factual=fact/procedure, comparison=multi-vendor table,
draft=email/memo/document, checklist=inspection/steps, general=best-practices/overview)

RETRIEVED CONTEXT (what the assistant had access to):
{context}

GENERATED ANSWER (raw output from the assistant):
{answer}

Your task — do BOTH in one pass:

STEP 1 — VALIDATE. Check all three:
  a) Is the entire answer in English? No other language or script?
  b) Does it contain only facts from the context or general FM knowledge?
     No invented vendor names, locations, addresses, or specific numbers
     not present in the context or the user's own query?
  c) Is it coherent and on-topic for the query?

If ANY check fails → respond with ONLY: {{"valid": false, "answer": ""}}

STEP 2 — REWRITE (only if all checks passed):
  Rewrite the answer to be:
  - Complete but concise: remove repetition, padding, trailing disclaimers, and
    meta-commentary, but KEEP all substantive points. Do NOT reduce a checklist
    answer to fewer than 5 items, and do NOT produce fewer than 80 words for any
    procedural or factual query. The rewritten answer must be useful, not just short.
  - Correctly formatted for the query type:
    * vendor/contract → Header line (Vendor — Category — Agreement No.) + Markdown
      table of terms (Term | Detail). Missing values = "Not specified". ONE optional
      terse caveat line at the very end. No inline hedging whatsoever.
    * comparison  → Markdown table (| col | col | with | --- | separator)
    * checklist   → numbered or bulleted list with all relevant items
    * draft       → full document (Subject / Greeting / Body / Sign-off for emails)
    * factual     → direct answer; ## headings only if genuinely multi-section
    * general     → structured answer with bold **key terms**
  - Uncertainty handling: if the original answer contains multiple caveats or
    hedging phrases ("as not explicitly stated", "per our records this may vary",
    "recommend retrieving from"), consolidate ALL of them into ONE terse sentence
    at the very end. Remove all inline hedging from the body of the answer.
  - English only: translate or silently remove any non-English fragments
  - Grounded: remove specific details not in the context (replace with "Not specified"
    rather than inventing values)
  - Do NOT add any facts not in the original answer or context

Respond with ONLY valid JSON, no markdown fences, no other text:
{{"valid": true, "answer": "...rewritten answer..."}}"""


@dataclass
class ValidationResult:
    passed: bool
    answer: str          # rewritten answer (if passed) or empty string (if failed)
    reason: str = "ok"
    layer: str = "none"
    details: dict = field(default_factory=dict)


def _rule_check(answer: str) -> ValidationResult | None:
    """Returns a failure ValidationResult if the answer fails a rule, else None."""
    match = _NON_LATIN_SCRIPTS.search(answer)
    if match:
        snippet = answer[max(0, match.start() - 10): match.end() + 10]
        return ValidationResult(
            passed=False, answer="",
            reason="non-Latin script detected",
            layer="rule",
            details={"snippet": snippet},
        )
    if len(answer.strip()) < _MIN_ANSWER_LENGTH:
        return ValidationResult(
            passed=False, answer="",
            reason="answer too short",
            layer="rule",
            details={"length": len(answer.strip())},
        )
    return None


def _groq_rewrite(
    query: str,
    query_type: str,
    context_chunks: list[dict],
    answer: str,
    api_key: str,
    model: str,
    min_score: int,
) -> ValidationResult:
    try:
        from groq import Groq

        context_text = "\n\n---\n\n".join(
            f"[Section: {c['section']}]\n{c['text']}" for c in context_chunks
        )[:3000]

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": _REWRITE_PROMPT.format(
                        query=query[:500],
                        query_type=query_type,
                        context=context_text,
                        answer=answer[:2500],
                    ),
                }
            ],
            max_tokens=1200,
            temperature=0.1,
        )

        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("` \n")
        json_match = re.search(r"\{[\s\S]+\}", raw)
        if not json_match:
            logger.warning("rewriter returned no JSON: %s", raw[:120])
            return ValidationResult(passed=True, answer=answer, reason="parse error — pass-through", layer="groq")

        # Strip control characters (U+0000–U+001F except \t \n \r) that Groq
        # occasionally embeds in its output and that cause json.loads to fail.
        clean_json = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", json_match.group())
        data = json.loads(clean_json)

        if not data.get("valid", True):
            return ValidationResult(passed=False, answer="", reason="failed Groq validation", layer="groq")

        rewritten = str(data.get("answer", "")).strip()
        if not rewritten or len(rewritten) < _MIN_ANSWER_LENGTH:
            logger.warning("rewriter returned empty answer — keeping original")
            return ValidationResult(passed=True, answer=answer, reason="empty rewrite — kept original", layer="groq")

        logger.info("answer rewritten by Groq (%d→%d chars)", len(answer), len(rewritten))
        return ValidationResult(passed=True, answer=rewritten, reason="ok", layer="groq")

    except Exception as exc:
        logger.warning("Groq rewriter failed (%s) — pass-through", exc)
        return ValidationResult(passed=True, answer=answer, reason=f"groq error: {exc}", layer="groq")


def validate_and_rewrite(
    query: str,
    query_type: str,
    context_chunks: list[dict],
    answer: str,
    api_key: str | None,
    model: str,
    min_score: int,
) -> ValidationResult:
    """Run rule check then Groq rewrite+validate. Returns the final answer to cache/show."""
    rule_failure = _rule_check(answer)
    if rule_failure is not None:
        return rule_failure

    if not api_key:
        return ValidationResult(passed=True, answer=answer, reason="rewriter disabled (no API key)", layer="none")

    return _groq_rewrite(query, query_type, context_chunks, answer, api_key, model, min_score)


# Keep the old name importable for any code that still references it
def validate(query, context_chunks, answer, api_key, model, min_score):
    return validate_and_rewrite(
        query=query,
        query_type="general",
        context_chunks=context_chunks,
        answer=answer,
        api_key=api_key,
        model=model,
        min_score=min_score,
    )
