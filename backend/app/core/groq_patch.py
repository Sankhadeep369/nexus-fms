"""Global Groq patch: default ``reasoning_effort='low'`` on all chat completions.

Groq's current general-purpose models (``openai/gpt-oss-*``) are REASONING models:
by default they spend the output-token budget on hidden reasoning, which makes calls
slow (~8s) and can return EMPTY content when ``max_tokens`` is tight. Setting
``reasoning_effort='low'`` restores fast, direct, instruct-style output (~0.6s)
across every Groq call site — without editing each one.

Idempotent and defensive: a failure here never breaks the app, it just leaves calls
unpatched. Callers can still override by passing their own ``extra_body``.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("nexus.groq_patch")
_applied = False


def apply() -> None:
    global _applied
    if _applied:
        return
    try:
        from groq.resources.chat.completions import Completions

        original = Completions.create
        if getattr(original, "_nexus_patched", False):
            _applied = True
            return

        def create(self, *args, **kwargs):
            eb = kwargs.get("extra_body") or {}
            eb.setdefault("reasoning_effort", "low")
            kwargs["extra_body"] = eb
            return original(self, *args, **kwargs)

        create._nexus_patched = True  # type: ignore[attr-defined]
        Completions.create = create
        _applied = True
        logger.info("Groq patch applied: default reasoning_effort=low.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Groq patch not applied (%s)", exc)


apply()
