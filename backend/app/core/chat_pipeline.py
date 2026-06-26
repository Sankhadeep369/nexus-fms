import re
import time
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from app.core.cache import ResponseCache, get_response_cache
from app.core.config import settings
from app.core.llm import ChatModel, get_llm, load_system_prompt
from app.core.retrieval import Retriever, get_retriever
from app.core.validator import validate

# --- SSE event shapes (all dicts get JSON-encoded as-is by the API layer) ---
# {"type": "step", "name": <str>, "status": "start" | "done", "detail": {...}?}
# {"type": "token", "text": <str>}
# {"type": "done", "latency_ms": {...}, "cache_hit": <str | None>, "retrieved_sources": [...]}

# Patterns that mark the start of training-data template artifacts that the
# fine-tuned model sometimes appends at the end of a response. Everything from
# the first match to the end of the string is stripped before caching.
_ARTIFACT_PATTERNS = [
    re.compile(r"\n*This response was assembled from[\s\S]*", re.IGNORECASE),
    re.compile(r"\n*End of template use[\s\S]*", re.IGNORECASE),
    re.compile(r"\n*Do not reuse this formatted text[\s\S]*", re.IGNORECASE),
    re.compile(r"\n*Note:\s*This (response|answer|output) (was|is)[\s\S]{0,300}template[\s\S]*", re.IGNORECASE),
]


def _strip_artifacts(text: str) -> str:
    for pattern in _ARTIFACT_PATTERNS:
        text = pattern.sub("", text)
    return text.rstrip()


def _build_user_content(query: str, retrieved: list[dict]) -> str:
    if not retrieved:
        return query

    # File paths are stripped from the context block so the model never echoes
    # raw filenames in its response. The UI surfaces source references separately
    # as a collapsible reference tile via the `retrieved_sources` field on `done`.
    context_block = "\n\n---\n\n".join(
        f"[Section: {r['section']}]\n{r['text']}" for r in retrieved
    )
    return (
        "Context (retrieved from internal facilities documents -- treat this as the "
        "source of truth for any vendor/client names, agreement numbers, sites, dates, "
        "amounts, and section references; if it does not contain what's needed, say so "
        "instead of inventing details):\n"
        f"{context_block}\n\n---\n\nRequest:\n{query}"
    )


class ChatPipeline:
    def __init__(self, cache: ResponseCache, llm: ChatModel, retriever: Retriever):
        self.cache = cache
        self.llm = llm
        self.retriever = retriever
        self.system_prompt = load_system_prompt()

    def run(self, query: str, mode: str = "simple") -> Iterator[dict[str, Any]]:
        t_start = time.time()
        temperature = settings.temperature_thinking if mode == "thinking" else settings.temperature_simple

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
            }
            return
        yield {"type": "step", "name": "cache_lookup", "status": "done", "detail": {"hit": False}}

        yield {"type": "step", "name": "retrieval", "status": "start"}
        candidates = self.retriever.retrieve(query)
        retrieved = [
            c
            for c in candidates
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

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": _build_user_content(query, retrieved)},
        ]

        yield {"type": "step", "name": "generation", "status": "start"}
        t0 = time.time()
        answer_parts: list[str] = []
        for token in self.llm.stream_chat(messages, temperature=temperature):
            answer_parts.append(token)
            yield {"type": "token", "text": token}
        answer = _strip_artifacts("".join(answer_parts))
        yield {"type": "step", "name": "generation", "status": "done", "detail": {"ms": int((time.time() - t0) * 1000)}}

        # --- Output validation ---
        validation = validate(
            query=query,
            context_chunks=retrieved,
            answer=answer,
            api_key=settings.groq_api_key,
            model=settings.groq_judge_model,
            min_score=settings.validation_min_score,
        )

        source_docs = sorted({r["source_doc"] for r in retrieved})

        if validation.passed:
            # Only cache answers that passed validation
            self.cache.set(query, mode, {"answer": answer, "retrieved_sources": source_docs})
            yield {
                "type": "done",
                "latency_ms": {"total": int((time.time() - t_start) * 1000)},
                "cache_hit": None,
                "retrieved_sources": source_docs,
                "valid": True,
            }
        else:
            # Replace the streamed answer with a safe fallback; do not cache
            fallback = (
                "NEXUS wasn't able to produce a reliable answer for this query.\n\n"
                "This can happen when the question spans multiple documents or asks "
                "for very specific contract details that aren't fully captured in the "
                "retrieved context.\n\n"
                "**Try:**\n"
                "- Rephrasing the question more specifically\n"
                "- Asking about one vendor at a time\n"
                "- Using the suggestion chips above for instant verified answers"
            )
            yield {
                "type": "done",
                "latency_ms": {"total": int((time.time() - t_start) * 1000)},
                "cache_hit": None,
                "retrieved_sources": [],
                "valid": False,
                "fallback": fallback,
                "validation_reason": validation.reason,
            }


@lru_cache(maxsize=1)
def get_chat_pipeline() -> "ChatPipeline":
    return ChatPipeline(cache=get_response_cache(), llm=get_llm(), retriever=get_retriever())
