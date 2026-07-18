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
You are a silent quality-control rewriter for NEXUS, an FM assistant. You clean up
the assistant's draft answer and return ONLY the finished answer the user will read.

CRITICAL OUTPUT RULE: your entire reply is EITHER the rewritten answer OR the single
word REJECT — nothing else. Do NOT narrate your process. Never output words like
"STEP 1", "STEP 2", "VALIDATION", "REWRITE", "Here is the rewritten answer", or any
heading/label describing what you did. The user must see only the final answer.

Reply with exactly REJECT (and nothing else) only if the draft is not in English, or
is pure meta-commentary quoting rules/instructions (e.g. "This response follows all
mandatory rules"). Ungrounded figures are NOT a reason to reject — you fix those below.

Otherwise, return the answer rewritten to satisfy ALL of these:
- Concise, no repetition/padding/preamble ("Certainly! Here is…"), no trailing
  disclaimers, no self-dialogue (never ask the user a question and then answer it
  yourself). Keep every substantive point. Target length by query type:
  factual 80–150w · vendor 150–220w · comparison 150–200w · checklist 150–250w ·
  vendor_decision 200–280w · draft 200–350w · general 120–200w.
- Formatted for the query type:
  vendor_decision → Markdown table (Term | Current | Alternative) + one bold
  **Recommendation:** line. vendor → header line + Markdown terms table (Term |
  Detail), missing = "Not specified". comparison → Markdown table only. checklist →
  numbered/bulleted list. draft → full document (Subject/Greeting/Body/Sign-off).
  factual → direct answer, ## headings only if multi-section. general → structured,
  bold **key terms**.
- Consolidate any hedging into ONE terse sentence at the end; remove inline hedging.
- English only: translate or drop non-English fragments.
- GROUNDING (most important): remove or correct EVERY specific claim NOT present
  verbatim in the Context. This applies to BOTH numbers and words:
  * Figures — amounts, rates, dates, section/appendix/exhibit refs, addresses,
    building names, registration numbers.
  * Qualitative claims — vendor capabilities, service-scope items, SLA tiers / breach
    thresholds / response-time guarantees, certifications, penalty/escalation clauses,
    service frequencies, exclusions. If the Context does not state it, do NOT assert
    it (the SLM tends to invent these from training knowledge).
  * Named sections ("Appendix A", "Clause 4.2", "Exhibit 3") not found in the
    Context — drop the reference entirely; never guess its content.
  Replace an unsupported specific with "Not specified" or drop the clause. Fix
  implausible data (years <2000 or >2050, a single AMC over $5M, wrong city/state).
  A vaguer TRUE statement always beats a precise INVENTED one. Add no facts not in
  the draft or Context.

ORIGINAL QUERY: {query}
QUERY TYPE: {query_type}
RETRIEVED CONTEXT: {context}
DRAFT ANSWER TO CLEAN UP: {answer}

Remember: output ONLY the finished answer (or REJECT). No labels, no explanation."""


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


_STEP2_RE = re.compile(r"^\s*(?:#+\s*)?STEP\s*2\b.*$", re.IGNORECASE | re.MULTILINE)
_STEP_HEADER_RE = re.compile(
    r"^\s*(?:#+\s*)?(?:STEP\s*\d\b.*|VALIDATION|REWRITE|OUTPUT)\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _strip_rewriter_scaffolding(text: str) -> str:
    """Remove any rewriter step-narration that leaked into the answer.

    The rewrite prompt is instructed to output only the finished answer, but a
    smaller model sometimes echoes its process ("STEP 1 VALIDATION … STEP 2
    REWRITE … <answer>"). If that happens, keep only what follows the last STEP 2
    marker and drop any residual step/validation header lines, so the user never
    sees the internal scaffolding.
    """
    matches = list(_STEP2_RE.finditer(text))
    if matches:
        text = text[matches[-1].end():]
    text = _STEP_HEADER_RE.sub("", text)
    return text.strip()


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
            f"[Section: {c.get('section', '')}]\n{c.get('text', '')}" for c in context_chunks
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
            temperature=0.0,
        )
        raw = response.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("Groq API call failed (%s) — pass-through (no response received)", exc)
        return ValidationResult(passed=True, answer=answer, reason=f"groq unreachable: {exc}", layer="groq")

    # Plain-text protocol (robust to Markdown tables / newlines that broke the old
    # JSON-wrapped answer): the model returns either "REJECT" or the corrected answer
    # directly. Strip any stray code fences the model may add.
    rewritten = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("` \n").strip()
    # Safety net: if the model still narrated its process (e.g. "STEP 1
    # VALIDATION … STEP 2 REWRITE …"), keep only the real answer.
    rewritten = _strip_rewriter_scaffolding(rewritten)

    if not rewritten or rewritten.upper().startswith("REJECT"):
        return ValidationResult(passed=False, answer="", reason="rewriter rejected (non-English/meta)", layer="groq")

    if len(rewritten) < _MIN_ANSWER_LENGTH:
        logger.warning("rewriter returned too-short answer — keeping original")
        return ValidationResult(passed=True, answer=answer, reason="rewrite too short — kept original", layer="groq")

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
