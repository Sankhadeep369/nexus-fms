"""Grounded answer recovery (orchestration safety net).

When the fine-tuned SLM's answer is unusable — a hard rule-check failure
(non-English/garbled), an empty answer, the model being busy, or a detected
hallucination (ungrounded figures that survived the rewriter) — the pipeline
must NOT surface an error to the user. Instead it recovers here: a fast Groq
synthesis that answers the user's (rephrased) question grounded ONLY in the
already-retrieved context, formatted for the query type.

This keeps the SLM as the primary generator on the happy path while guaranteeing
that the only thing a user ever sees on failure is an answer — never a "quality
check failed" message. The single case that still surfaces a message is a genuine
network/Groq outage (recover_answer returns None), which the caller frames as a
connectivity issue, not a model error.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("nexus.recovery")

_FORMAT_HINTS = {
    "comparison": "a Markdown table (one row per attribute, one column per option), then a one-line takeaway",
    "vendor": "a short header line then a Markdown table of the contract's terms",
    "vendor_decision": "a Markdown table (Term | Current | Alternative) then a bold Recommendation line",
    "budget_analysis": "a Markdown table with a Total row",
    "checklist": "a numbered or bulleted list, one item per line",
    "draft": "a complete document (Subject / Greeting / Body / Sign-off for an email)",
    "factual": "a direct, concise answer",
    "general": "a concise structured answer with bold key terms",
}

_RECOVERY_PROMPT = """\
You are NEXUS, a facilities-management assistant. Answer the user's question below.

USER QUESTION: {query}

CONTEXT (the only source of specific facts you may use):
{context}

Rules:
- Use ONLY facts present in the CONTEXT above. If the context lacks a specific value,
  write "Not specified" — never invent amounts, dates, section/appendix references,
  vendor names, or addresses.
- If the context is empty, answer from general facilities-management best practice
  WITHOUT inventing any specific figures, names, or clauses.
- Format the answer as {format_hint}.
- English only. Be concise. No preamble, no meta-commentary, no mention of "context".

Answer:"""


def recover_answer(
    query: str,
    query_type: str,
    chunks: list[dict],
    api_key: str | None,
    model: str,
) -> str | None:
    """Fast grounded Groq synthesis from the already-retrieved context.

    Returns the answer text, or None only when Groq is unreachable (network) — the
    caller treats None, and nothing else, as a reason to show the user a message.
    """
    if not api_key:
        return None
    try:
        from groq import Groq

        context = ""
        if chunks:
            context = "\n\n---\n\n".join(
                f"[{c.get('section', '')}]\n{c.get('text', '')}" for c in chunks
            )[:5000]
        else:
            context = "(no specific documents retrieved — answer from general FM knowledge only)"

        prompt = _RECOVERY_PROMPT.format(
            query=query[:600],
            context=context,
            format_hint=_FORMAT_HINTS.get(query_type, _FORMAT_HINTS["factual"]),
        )
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.1,
        )
        answer = resp.choices[0].message.content.strip()
        if answer:
            logger.info("recovery synthesis produced %d chars (type=%s)", len(answer), query_type)
            return answer
        return None
    except Exception as exc:
        # Network / API outage — the caller frames this as a connectivity issue.
        logger.warning("recovery synthesis unavailable (network?): %s", exc)
        return None
