"""Two-layer output validation for generated answers.

Layer 1 — rule-based (instant, no API call):
  - Detects non-Latin script contamination (Hindi, Bengali, Arabic, etc.)
  - Rejects answers that are too short to be useful

Layer 2 — Groq LLM judge (~1-2s, uses free Groq API tier):
  - Sends {query, retrieved context, generated answer} to llama-3.1-8b-instant
  - Checks: English only, factually grounded in context, no hallucinated specifics
  - Returns a 0-10 score; below validation_min_score triggers a fallback

If the Groq API key is not configured or the judge call fails, Layer 2 is
skipped and the answer is passed through (fail-open so a config issue never
silently breaks the chat endpoint).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

# Unicode ranges for non-Latin scripts commonly seen as contamination artifacts
# from multilingual training data: Devanagari (Hindi), Bengali, Arabic, CJK, etc.
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

_JUDGE_PROMPT = """\
You are a strict quality-control reviewer for an AI assistant that answers \
facilities-management questions.

ORIGINAL QUERY:
{query}

RETRIEVED CONTEXT (what the assistant was given to work with):
{context}

GENERATED ANSWER:
{answer}

Evaluate the answer against these three criteria:
1. english_only   — Is every word in English? No other language or script?
2. grounded       — Does the answer use ONLY facts present in the context or \
universally-known FM standards? No invented names, locations, addresses, or amounts?
3. coherent       — Is the answer coherent, on-topic, and free of garbled/repeated text?

Reply with ONLY a valid JSON object, no other text:
{{"english_only": true/false, "grounded": true/false, "coherent": true/false, "score": <int 0-10>}}

Score guide: 10 = perfect, 7-9 = minor issues, 4-6 = significant problems, 0-3 = reject."""


@dataclass
class ValidationResult:
    passed: bool
    reason: str
    score: int | None = None
    layer: str = "none"
    details: dict = field(default_factory=dict)


def _rule_check(answer: str) -> ValidationResult:
    match = _NON_LATIN_SCRIPTS.search(answer)
    if match:
        snippet = answer[max(0, match.start() - 10): match.end() + 10]
        return ValidationResult(
            passed=False,
            reason="non-Latin script detected",
            layer="rule",
            details={"snippet": snippet},
        )
    if len(answer.strip()) < _MIN_ANSWER_LENGTH:
        return ValidationResult(
            passed=False,
            reason="answer too short",
            layer="rule",
            details={"length": len(answer.strip())},
        )
    return ValidationResult(passed=True, reason="ok", layer="rule")


def _groq_judge(
    query: str,
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
                    "content": _JUDGE_PROMPT.format(
                        query=query[:500],
                        context=context_text,
                        answer=answer[:2000],
                    ),
                }
            ],
            max_tokens=120,
            temperature=0.0,
        )

        raw = response.choices[0].message.content.strip()
        # Extract the JSON object even if the model wraps it in markdown fences
        json_match = re.search(r"\{[^{}]+\}", raw, re.DOTALL)
        if not json_match:
            return ValidationResult(passed=True, reason="judge parse error (pass-through)", layer="groq")

        result = json.loads(json_match.group())
        score = int(result.get("score", 10))

        if not result.get("english_only", True):
            return ValidationResult(
                passed=False, reason="non-English content confirmed by judge",
                score=score, layer="groq", details=result,
            )
        if not result.get("grounded", True) and score < min_score:
            return ValidationResult(
                passed=False, reason=f"hallucination detected (score {score}/{min_score})",
                score=score, layer="groq", details=result,
            )
        if score < min_score:
            return ValidationResult(
                passed=False, reason=f"low quality score {score} < {min_score}",
                score=score, layer="groq", details=result,
            )

        return ValidationResult(passed=True, reason="ok", score=score, layer="groq", details=result)

    except Exception as exc:
        # Fail-open: a network error or bad response must not break the chat endpoint
        return ValidationResult(
            passed=True,
            reason=f"judge unavailable ({type(exc).__name__}) — pass-through",
            layer="groq",
        )


def validate(
    query: str,
    context_chunks: list[dict],
    answer: str,
    api_key: str | None,
    model: str,
    min_score: int,
) -> ValidationResult:
    """Run both validation layers. Returns the first failure or a passing result."""
    rule_result = _rule_check(answer)
    if not rule_result.passed:
        return rule_result

    if not api_key:
        return ValidationResult(passed=True, reason="judge disabled (no API key)", layer="none")

    return _groq_judge(query, context_chunks, answer, api_key, model, min_score)
