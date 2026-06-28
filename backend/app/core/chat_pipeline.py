"""NEXUS chat pipeline.

Request flow for a non-cached query:
  1. cache_lookup        — SHA-256 keyed exact match
  2. query_analysis      — Groq rewrites + classifies the query (if enabled)
  3. retrieval           — hybrid BM25-bigram + dense cosine over 57 corpus docs
  4. generation          — fine-tuned Gemma 3 4B GGUF, streams tokens
  5. refinement          — Groq validates + rewrites the answer (if enabled)
  6. done                — final_answer returned; valid answers cached

Cached answers skip steps 2-5 entirely.

SSE event shapes emitted by run():
  {"type": "step",  "name": <str>, "status": "start"|"done", "detail": {...}?}
  {"type": "token", "text": <str>}
  {"type": "done",  "latency_ms": {...}, "cache_hit": <str|None>,
                    "retrieved_sources": [...], "valid": <bool>,
                    "final_answer": <str>?}
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from app.core.cache import ResponseCache, get_response_cache
from app.core.config import settings
from app.core.llm import ChatModel, get_llm, load_system_prompt
from app.core.query_processor import ProcessedQuery, preprocess
from app.core.retrieval import Retriever, get_retriever
from app.core.validator import validate_and_rewrite

# ---------------------------------------------------------------------------
# Artifact stripping — training-data template leakage patterns
# ---------------------------------------------------------------------------

_ARTIFACT_PATTERNS = [
    re.compile(r"\n*This response was assembled from[\s\S]*", re.IGNORECASE),
    re.compile(r"\n*End of template[\s\S]*", re.IGNORECASE),
    re.compile(r"\n*Do not reuse this formatted text[\s\S]*", re.IGNORECASE),
    re.compile(r"\n*Note:\s*This (?:response|answer|output) (?:was|is)[\s\S]{0,300}template[\s\S]*", re.IGNORECASE),
    re.compile(r"\n*\[End of (?:response|answer|template)\][\s\S]*", re.IGNORECASE),
]


def _strip_artifacts(text: str) -> str:
    for pattern in _ARTIFACT_PATTERNS:
        text = pattern.sub("", text)
    return text.rstrip()


# ---------------------------------------------------------------------------
# Prompt construction helpers
# ---------------------------------------------------------------------------

def _build_history_messages(history: list[dict], max_turns: int) -> list[dict]:
    """Convert frontend history (list of {role, content}) into a trimmed
    list of chat messages to inject between the system prompt and the current query.
    Keeps the last `max_turns` user+assistant pairs."""
    if not history or max_turns <= 0:
        return []
    # Ensure we only keep complete user/assistant pairs
    pairs: list[tuple[dict, dict]] = []
    i = 0
    while i < len(history) - 1:
        if history[i]["role"] == "user" and history[i + 1]["role"] == "assistant":
            pairs.append((history[i], history[i + 1]))
            i += 2
        else:
            i += 1
    # Take the last max_turns pairs and flatten
    recent = pairs[-max_turns:]
    return [msg for pair in recent for msg in pair]


def _build_user_content(query: str, retrieved: list[dict]) -> str:
    if not retrieved:
        return query
    context_block = "\n\n---\n\n".join(
        f"[Section: {r['section']}]\n{r['text']}" for r in retrieved
    )
    return (
        "Context (retrieved from internal facilities documents — use as the "
        "authoritative source for vendor names, agreement numbers, sites, dates, "
        "amounts, and section references; state clearly if something needed is "
        "not present rather than inventing details):\n"
        f"{context_block}\n\n---\n\nRequest:\n{query}"
    )


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

_FALLBACK_MESSAGE = (
    "NEXUS wasn't able to produce a reliable answer for this query.\n\n"
    "This can happen with complex multi-vendor comparisons or queries that "
    "require very specific contract details not present in the retrieved context.\n\n"
    "**Try:**\n"
    "- Rephrasing the question more specifically\n"
    "- Asking about one vendor or system at a time\n"
    "- Using the suggestion chips for instant verified answers"
)


class ChatPipeline:
    def __init__(self, cache: ResponseCache, llm: ChatModel, retriever: Retriever):
        self.cache = cache
        self.llm = llm
        self.retriever = retriever
        self.system_prompt = load_system_prompt()

    def run(
        self,
        query: str,
        mode: str = "simple",
        history: list[dict] | None = None,
    ) -> Iterator[dict[str, Any]]:
        t_start = time.time()
        history = history or []
        temperature = (
            settings.temperature_thinking if mode == "thinking"
            else settings.temperature_simple
        )

        # ── 1. Cache lookup ─────────────────────────────────────────────────
        yield {"type": "step", "name": "cache_lookup", "status": "start"}
        cached = self.cache.get(query, mode)
        if cached is not None:
            yield {"type": "step", "name": "cache_lookup", "status": "done", "detail": {"hit": True}}
            yield {"type": "token", "text": cached["answer"]}
            yield {
                "type": "done",
                "latency_ms": {"total": int((time.time() - t_start) * 1000)},
                "cache_hit": "exact",
                "retrieved_sources": cached.get("retrieved_sources", []),
                "valid": True,
                "final_answer": cached["answer"],
            }
            return
        yield {"type": "step", "name": "cache_lookup", "status": "done", "detail": {"hit": False}}

        # ── 2. Query analysis (Groq pre-processor) ───────────────────────────
        processed: ProcessedQuery
        if settings.query_preprocessor_enabled and settings.groq_api_key:
            yield {"type": "step", "name": "query_analysis", "status": "start"}
            processed = preprocess(query, settings.groq_api_key, settings.groq_model)
            yield {
                "type": "step",
                "name": "query_analysis",
                "status": "done",
                "detail": {
                    "type": processed.query_type,
                    "rewritten": processed.rewritten,
                    "entities": processed.entities,
                },
            }
        else:
            processed = ProcessedQuery(original=query, rewritten=query)

        retrieval_query = processed.rewritten

        # ── 3. Retrieval ─────────────────────────────────────────────────────
        yield {"type": "step", "name": "retrieval", "status": "start"}
        candidates = self.retriever.retrieve(retrieval_query)
        retrieved = [
            c for c in candidates
            if c["dense_score"] >= settings.retrieval_min_dense_score
            or c["bm25_score"] >= settings.retrieval_min_bm25_score
        ]
        yield {
            "type": "step",
            "name": "retrieval",
            "status": "done",
            "detail": {
                "sources": [
                    {"source_doc": r["source_doc"], "section": r["section"], "score": round(r["score"], 3)}
                    for r in retrieved
                ]
            },
        }

        # ── 4. Generation ─────────────────────────────────────────────────────
        history_messages = _build_history_messages(history, settings.max_history_turns)
        messages = [
            {"role": "system", "content": self.system_prompt},
            *history_messages,
            {"role": "user", "content": _build_user_content(retrieval_query, retrieved)},
        ]

        yield {"type": "step", "name": "generation", "status": "start"}
        t0 = time.time()
        answer_parts: list[str] = []
        for token in self.llm.stream_chat(messages, temperature=temperature):
            answer_parts.append(token)
            yield {"type": "token", "text": token}
        raw_answer = _strip_artifacts("".join(answer_parts))
        yield {"type": "step", "name": "generation", "status": "done",
               "detail": {"ms": int((time.time() - t0) * 1000)}}

        # ── 5. Refinement (Groq validate + rewrite) ──────────────────────────
        source_docs = sorted({r["source_doc"] for r in retrieved})

        if settings.answer_rewriter_enabled and settings.groq_api_key:
            yield {"type": "step", "name": "refinement", "status": "start"}
            result = validate_and_rewrite(
                query=query,
                query_type=processed.query_type,
                context_chunks=retrieved,
                answer=raw_answer,
                api_key=settings.groq_api_key,
                model=settings.groq_model,
                min_score=settings.validation_min_score,
            )
            yield {"type": "step", "name": "refinement", "status": "done",
                   "detail": {"valid": result.passed, "layer": result.layer}}
        else:
            # No Groq rewriting — pass the raw answer through
            from app.core.validator import ValidationResult
            result = ValidationResult(passed=True, answer=raw_answer, reason="rewriter disabled")

        # ── 6. Done ──────────────────────────────────────────────────────────
        if result.passed:
            final_answer = result.answer
            self.cache.set(query, mode, {"answer": final_answer, "retrieved_sources": source_docs})
            yield {
                "type": "done",
                "latency_ms": {"total": int((time.time() - t_start) * 1000)},
                "cache_hit": None,
                "retrieved_sources": source_docs,
                "valid": True,
                "final_answer": final_answer,
            }
        else:
            yield {
                "type": "done",
                "latency_ms": {"total": int((time.time() - t_start) * 1000)},
                "cache_hit": None,
                "retrieved_sources": [],
                "valid": False,
                "fallback": _FALLBACK_MESSAGE,
                "validation_reason": result.reason,
            }


@lru_cache(maxsize=1)
def get_chat_pipeline() -> ChatPipeline:
    return ChatPipeline(cache=get_response_cache(), llm=get_llm(), retriever=get_retriever())
