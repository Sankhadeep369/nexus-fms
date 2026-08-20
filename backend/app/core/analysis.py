"""Issue / root-cause analysis engine.

Given an issue and a methodology (5 Whys, Ishikawa, FTA, RCA) the model returns a
structured, JSON analysis the frontend renders and the user refines. Optionally
grounds the candidate causes in the corpus + the user's uploaded docs (owner-scoped
retrieval). A separate CAPA step turns the refined root causes into corrective +
preventive actions.

All model work is Groq (fast) and entirely off the chat path — it never affects
chat response timing.
"""

from __future__ import annotations

import json
import logging
import re

from app.core.config import settings

logger = logging.getLogger("nexus.analysis")

METHODS = ("5whys", "ishikawa", "fta", "rca")
ISHIKAWA_CATEGORIES = ("Manpower", "Method", "Machine", "Material", "Measurement", "Environment")

_PROMPTS: dict[str, str] = {
    "5whys": """\
You are a facilities-management root-cause analyst. Perform a 5 Whys analysis.
{context}Problem: {issue}

Ask "why" iteratively (3 to 5 levels), each answer explaining the previous one, until
you reach an actionable root cause. Return ONLY valid JSON:
{{"problem": "<restated problem>", "whys": [{{"why": "Why did ... happen?", "cause": "Because ..."}}, ...], "root_cause": "<the underlying root cause>"}}""",
    "ishikawa": """\
You are a facilities-management analyst. Perform an Ishikawa (fishbone) cause analysis.
Use these six categories: Manpower, Method, Machine, Material, Measurement, Environment.
{context}Problem: {issue}

For EACH category list 2 to 5 plausible candidate causes that are specific to THIS problem
(not generic). Return ONLY valid JSON:
{{"problem": "<restated problem>", "categories": {{"Manpower": ["..."], "Method": ["..."], "Machine": ["..."], "Material": ["..."], "Measurement": ["..."], "Environment": ["..."]}}}}""",
    "fta": """\
You are a facilities-management reliability analyst. Perform a Fault Tree Analysis.
The top event is the failure below. Decompose it through logic gates into intermediate
and basic (leaf) events. Use gate "AND" (all children required) or "OR" (any child suffices).
{context}Top event: {issue}

Return ONLY valid JSON, a tree at most 3 levels deep. Every node has "label"; branch nodes
have "gate" and "children"; basic/leaf events have "gate": null and no "children":
{{"top_event": "<the failure>", "tree": {{"label": "<the failure>", "gate": "OR", "children": [{{"label": "...", "gate": "AND", "children": [{{"label": "...", "gate": null}}]}}]}}}}""",
    "rca": """\
You are a facilities-management analyst. Write a structured Root Cause Analysis.
{context}Problem: {issue}

Return ONLY valid JSON:
{{"problem": "<restated problem>", "impact": "<who/what is affected>", "timeline": ["<event>", ...], "contributing_factors": ["...", ...], "root_causes": ["...", ...]}}""",
}

_CAPA_PROMPT = """\
For the facilities problem and its confirmed root cause(s) below, propose:
- corrective actions: fix the current problem now.
- preventive actions: stop it recurring.
Be specific and practical. Return ONLY valid JSON:
{{"corrective": ["...", ...], "preventive": ["...", ...]}}

Problem: {issue}
Root cause(s): {root_causes}"""


def _context_block(issue: str, grounded: bool, owner: str | None) -> str:
    if not grounded:
        return ""
    try:
        from app.core.retrieval import get_retriever

        chunks = get_retriever().retrieve(issue, k=5, owner=owner)
    except Exception as exc:  # noqa: BLE001
        logger.warning("analysis grounding retrieval failed (%s)", exc)
        return ""
    if not chunks:
        return ""
    body = "\n\n".join(c["text"][:600] for c in chunks[:5])
    return (
        "Relevant internal facilities documents (use where they apply; do not invent):\n"
        f"{body}\n\n"
    )


def _repair_json(frag: str) -> str:
    """Best-effort fixes for the two ways model JSON breaks: trailing commas and a
    reply truncated mid-structure (close any still-open brackets/braces)."""
    frag = re.sub(r",\s*([}\]])", r"\1", frag)  # drop trailing commas
    # Balance brackets, ignoring those inside strings.
    stack, in_str, esc = [], False, False
    for ch in frag:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]" and stack:
            stack.pop()
    if in_str:
        frag += '"'
    frag += "".join("}" if c == "{" else "]" for c in reversed(stack))
    return frag


def _groq_json(prompt: str, max_tokens: int) -> dict:
    from groq import Groq

    client = Groq(api_key=settings.groq_api_key, max_retries=1)
    r = client.chat.completions.create(
        model=settings.groq_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.2,
        # Constrain the model to emit strictly valid JSON — this is what stops the
        # intermittent "Expecting ',' delimiter" failures (unescaped quotes etc.).
        response_format={"type": "json_object"},
    )
    raw = (r.choices[0].message.content or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]+\}", raw)
    frag = m.group() if m else raw
    try:
        return json.loads(frag)
    except json.JSONDecodeError:
        return json.loads(_repair_json(frag))  # last resort; may still raise


def generate_analysis(method: str, issue: str, grounded: bool = False, owner: str | None = None) -> dict:
    if method not in METHODS:
        return {"error": f"Unknown method '{method}'."}
    if not settings.groq_api_key:
        return {"error": "Analysis is not configured (missing GROQ_API_KEY)."}
    ctx = _context_block(issue, grounded, owner)
    prompt = _PROMPTS[method].format(context=ctx, issue=issue[:1200])
    try:
        data = _groq_json(prompt, 1500)
        if not isinstance(data, dict) or not data:
            return {"error": "The analyzer returned no usable result — please try again."}
        data["method"] = method
        data["grounded"] = bool(ctx)
        return data
    except Exception as exc:  # noqa: BLE001
        logger.warning("analysis generate failed (%s)", exc)
        return {"error": f"Analysis failed: {str(exc)[:140]}"}


def generate_capa(issue: str, root_causes: list[str]) -> dict:
    if not settings.groq_api_key:
        return {"error": "Not configured."}
    causes = "; ".join(rc for rc in root_causes if rc)[:800] or "the identified root cause"
    try:
        data = _groq_json(_CAPA_PROMPT.format(issue=issue[:800], root_causes=causes), 500)
        return {
            "corrective": [str(x) for x in (data.get("corrective") or [])][:8],
            "preventive": [str(x) for x in (data.get("preventive") or [])][:8],
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("CAPA generate failed (%s)", exc)
        return {"error": f"CAPA failed: {str(exc)[:140]}"}
