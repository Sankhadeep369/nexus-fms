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

# --- Deterministic numeric grounding check ---
# Catches hallucinated currency figures that an LLM judge unreliably misses,
# including Indian lakh/crore digit-grouping misreads (e.g. "INR 14,40,000"
# = 1,440,000 being restated by the model as "INR 14.4 million" = 14,400,000,
# a 10x error from misreading the grouping convention).
_CURRENCY_RE = re.compile(
    r"(\$|INR|Rs\.?|USD)\s?([\d,]+(?:\.\d+)?)\s?(million|mn|thousand|lakh|crore|k|m)?",
    re.IGNORECASE,
)
_UNIT_MULTIPLIERS = {
    "million": 1_000_000, "mn": 1_000_000, "m": 1_000_000,
    "thousand": 1_000, "k": 1_000,
    "lakh": 100_000,
    "crore": 10_000_000,
}
_GROUNDING_TOLERANCE = 0.02  # 2% relative tolerance for rounding in restated figures


def _extract_amounts(text: str) -> list[float]:
    amounts = []
    for _symbol, number, unit in _CURRENCY_RE.findall(text):
        try:
            value = float(number.replace(",", ""))
        except ValueError:
            continue
        if unit:
            value *= _UNIT_MULTIPLIERS.get(unit.lower(), 1)
        amounts.append(value)
    return amounts


def _numeric_grounding_check(answer: str, context_chunks: list[dict]) -> ValidationResult | None:
    """Returns a failure ValidationResult if the answer states a currency amount
    that doesn't match (within tolerance) any amount found in the retrieved
    context. Returns None if all amounts are grounded or the answer has none."""
    answer_amounts = _extract_amounts(answer)
    if not answer_amounts:
        return None

    context_text = "\n".join(c.get("text", "") for c in context_chunks)
    context_amounts = _extract_amounts(context_text)
    if not context_amounts:
        # Answer cites figures but context has none at all — definitely ungrounded.
        return ValidationResult(
            passed=False, answer="",
            reason=f"answer cites currency amount(s) {answer_amounts} but context has none",
            layer="rule",
        )

    for amt in answer_amounts:
        matched = any(
            abs(amt - ctx_amt) / max(amt, ctx_amt, 1.0) < _GROUNDING_TOLERANCE
            for ctx_amt in context_amounts
        )
        if not matched:
            return ValidationResult(
                passed=False, answer="",
                reason=f"unverifiable amount {amt} not found in retrieved context {context_amounts}",
                layer="rule",
            )
    return None

_REWRITE_PROMPT = """\
You are a quality-control rewriter for NEXUS, an AI facilities-management assistant.

ORIGINAL QUERY: {query}
QUERY TYPE: {query_type}
(vendor_decision=renew/switch recommendation with current-vs-alternatives table,
vendor=contract/agreement details, factual=fact/procedure, comparison=multi-vendor table,
draft=email/memo/document, checklist=inspection/steps, general=best-practices/overview)

RETRIEVED CONTEXT (what the assistant had access to):
{context}

GENERATED ANSWER (raw output from the assistant):
{answer}

Your task — do BOTH in one pass:

STEP 1 — VALIDATE. Check all four:
  a) Is the entire answer in English? No other language or script?
  b) Does it contain only facts from the context or general FM knowledge?
     Reject if it contains specific street addresses, building names, company
     registration details, or dollar amounts that do not appear verbatim in
     the retrieved context shown above.
  c) Does it contain implausible data? Reject if it has: years before 2000 or
     after 2050, amounts over $5 million for a single AMC, incorrect country/state
     pairings (e.g. "Dallas IL"), or section references that don't exist in context.
  d) Does it contain meta-commentary quoting rules or instructions? e.g. phrases
     like "This response follows all four mandatory rules" or "no invented facts"
     copied from the system instructions. Reject if yes.

If ANY check fails → respond with ONLY: {{"valid": false, "answer": ""}}

STEP 2 — REWRITE (only if all checks passed):
  Rewrite the answer to be:
  - Complete but concise: remove repetition, padding, trailing disclaimers, and
    meta-commentary, but KEEP all substantive points. Do NOT reduce a checklist
    answer to fewer than 5 items, and do NOT produce fewer than 80 words for any
    procedural or factual query. The rewritten answer must be useful, not just short.
  - Correctly formatted for the query type:
    * vendor_decision → Two-part structure: (1) Markdown table comparing current
      terms vs. competitor/market alternatives (Term | Current | Alternative),
      (2) a bolded one-line **Recommendation:** sentence at the end with reasoning.
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
    # Two failure categories, handled differently:
    # 1. Groq unreachable (network/API error before any response) — we have NO
    #    information either way, so fail-open (pass the original answer through)
    #    is reasonable; a config/connectivity issue must not break the endpoint.
    # 2. Groq responded but the judgment is unparseable/truncated — we know
    #    *something* but can't read it. This correlates strongly with the
    #    longest, messiest answers (exactly the most hallucination-prone ones),
    #    so fail CLOSED here: show the safe fallback rather than risk surfacing
    #    raw, unvalidated SLM output.
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
            max_tokens=2048,
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("Groq API call failed (%s) — pass-through (no response received)", exc)
        return ValidationResult(passed=True, answer=answer, reason=f"groq unreachable: {exc}", layer="groq")

    try:
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("` \n")
        json_match = re.search(r"\{[\s\S]+\}", raw)
        if not json_match:
            logger.warning("rewriter response unparseable (likely truncated): %s", raw[:120])
            return ValidationResult(passed=False, answer="", reason="rewriter response truncated/unparseable", layer="groq")

        # strict=False allows literal \n/\t inside JSON string values — Groq's
        # multi-paragraph answers routinely contain raw newlines that strict
        # JSON parsing would otherwise reject.
        clean_json = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", json_match.group())
        data = json.loads(clean_json, strict=False)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("rewriter JSON malformed (%s): %s", exc, raw[:160])
        return ValidationResult(passed=False, answer="", reason=f"rewriter JSON malformed: {exc}", layer="groq")

    if not data.get("valid", True):
        return ValidationResult(passed=False, answer="", reason="failed Groq validation", layer="groq")

    rewritten = str(data.get("answer", "")).strip()
    if not rewritten or len(rewritten) < _MIN_ANSWER_LENGTH:
        logger.warning("rewriter returned empty answer — keeping original")
        return ValidationResult(passed=True, answer=answer, reason="empty rewrite — kept original", layer="groq")

    logger.info("answer rewritten by Groq (%d→%d chars)", len(answer), len(rewritten))
    return ValidationResult(passed=True, answer=rewritten, reason="ok", layer="groq")


def validate_and_rewrite(
    query: str,
    query_type: str,
    context_chunks: list[dict],
    answer: str,
    api_key: str | None,
    model: str,
    min_score: int,
    strict: bool = False,
) -> ValidationResult:
    """Run rule check, then Groq rewrite+validate, then a deterministic numeric
    grounding pass on the final text. Returns the answer to cache/show.

    strict=False (default, for SLM-generated answers):
        Groq is an optional ENHANCER — if it fails or marks the answer invalid,
        the raw (artifact-stripped) SLM answer is returned rather than withholding.
        Only the instant rule check (non-Latin script, length) is a hard gate.

    strict=True (for agent-synthesized answers like vendor_decision):
        Groq validation IS the content gate — if it rejects, the answer is withheld.
        Used when Groq is the primary generator, not just a post-processor.
    """
    rule_failure = _rule_check(answer)
    if rule_failure is not None:
        return rule_failure

    if not api_key:
        result = ValidationResult(passed=True, answer=answer, reason="rewriter disabled (no API key)", layer="none")
    else:
        result = _groq_rewrite(query, query_type, context_chunks, answer, api_key, model, min_score)

    # In non-strict mode (SLM path), Groq failures fall through to the original
    # answer rather than withholding — Groq is an enhancer here, not a gatekeeper.
    if not result.passed:
        if strict:
            return result
        else:
            logger.info("groq rewrite did not pass (%s) — returning raw SLM answer (non-strict mode)", result.reason)
            result = ValidationResult(passed=True, answer=answer, reason=f"groq-fallback: {result.reason}", layer="none")

    # Deterministic numeric grounding check — only enforced in strict mode.
    # In non-strict mode (SLM path for general FM queries) the SLM might
    # legitimately mention benchmark figures from training knowledge that don't
    # appear verbatim in the retrieved chunks. The strict check is reserved for
    # agent-synthesized answers where every figure SHOULD come from context.
    if strict:
        numeric_failure = _numeric_grounding_check(result.answer, context_chunks)
        if numeric_failure is not None:
            logger.warning("numeric grounding check failed: %s", numeric_failure.reason)
            return numeric_failure

    return result


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
