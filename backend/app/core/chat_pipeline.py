import time
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from app.core.cache import ResponseCache, get_response_cache
from app.core.config import settings
from app.core.llm import ChatModel, get_llm, load_system_prompt
from app.core.retrieval import Retriever, get_retriever

# --- SSE event shapes (all dicts get JSON-encoded as-is by the API layer) ---
# {"type": "step", "name": <str>, "status": "start" | "done", "detail": {...}?}
# {"type": "token", "text": <str>}
# {"type": "done", "latency_ms": {...}, "cache_hit": <str | None>, "retrieved_sources": [...]}


def _build_user_content(query: str, retrieved: list[dict]) -> str:
    if not retrieved:
        return query

    context_block = "\n\n---\n\n".join(
        f"[Source: {r['source_doc']} | Section: {r['section']}]\n{r['text']}" for r in retrieved
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
        answer = "".join(answer_parts)
        yield {"type": "step", "name": "generation", "status": "done", "detail": {"ms": int((time.time() - t0) * 1000)}}

        source_docs = sorted({r["source_doc"] for r in retrieved})
        self.cache.set(query, mode, {"answer": answer, "retrieved_sources": source_docs})

        yield {
            "type": "done",
            "latency_ms": {"total": int((time.time() - t_start) * 1000)},
            "cache_hit": None,
            "retrieved_sources": source_docs,
        }


@lru_cache(maxsize=1)
def get_chat_pipeline() -> "ChatPipeline":
    return ChatPipeline(cache=get_response_cache(), llm=get_llm(), retriever=get_retriever())
