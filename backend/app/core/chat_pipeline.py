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

import logging
import re
import time
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from app.core.cache import ResponseCache, get_response_cache
from app.core.config import settings
from app.core.llm import ChatModel, LLMBusyError, get_llm, load_system_prompt
from app.core.query_processor import ProcessedQuery, preprocess
from app.core.retrieval import EntityAwareRetriever, Retriever, get_entity_retriever, get_retriever
from app.core.validator import validate_and_rewrite

logger = logging.getLogger("nexus.chat_pipeline")

# ---------------------------------------------------------------------------
# Artifact stripping — training-data template leakage patterns
# ---------------------------------------------------------------------------

_ARTIFACT_PATTERNS = [
    # Original template-end markers
    re.compile(r"\n*This response was assembled from[\s\S]*", re.IGNORECASE),
    re.compile(r"\n*End of template[\s\S]*", re.IGNORECASE),
    re.compile(r"\n*Do not reuse this formatted text[\s\S]*", re.IGNORECASE),
    re.compile(r"\n*Note:\s*This (?:response|answer|output) (?:was|is)[\s\S]{0,300}template[\s\S]*", re.IGNORECASE),
    re.compile(r"\n*\[End of (?:response|answer|template)\][\s\S]*", re.IGNORECASE),
    # Instruction-following meta-commentary
    re.compile(r"\n*This response follows all[\s\S]*", re.IGNORECASE),
    re.compile(r"\n*All (?:four|five|three|six) (?:mandatory |compliance |format )?(?:rules|checks)[\s\S]*", re.IGNORECASE),
    re.compile(r"\n*(?:This is a |It is a )?role.?play exercise[\s\S]*", re.IGNORECASE),
    re.compile(r"\n*(?:This is an? )?internal training exercise[\s\S]*", re.IGNORECASE),
    re.compile(r"\n*no actual (?:commercial|vendor|contract) data should be used[\s\S]*", re.IGNORECASE),
    re.compile(r"\n*If asked to write[\s\S]*", re.IGNORECASE),
    re.compile(r"\n*The recommendation would be based on[\s\S]{0,200}training[\s\S]*", re.IGNORECASE),
    # System-prompt echoing
    re.compile(r"\n*(?:Accuracy|Consistency) \(only using approved internal[\s\S]*", re.IGNORECASE),
    re.compile(r"\n*Use this source as the definitive record[\s\S]*", re.IGNORECASE),
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


_DOC_TYPE_LABELS = {
    "current_contracts": "CURRENT CONTRACT",
    "competitor_contracts": "MARKET REFERENCE (benchmark only — not a current agreement)",
    "domain_docs": "FM REFERENCE DOCUMENT",
}


def _doc_type_label(source_doc: str) -> str:
    folder = source_doc.split("/")[0]
    return _DOC_TYPE_LABELS.get(folder, "REFERENCE DOCUMENT")


# Hard ceiling on combined context length regardless of how many chunks were
# gathered (standard retrieval, entity-aware, or agent) -- defends prefill time
# even if a future code path passes in more chunks than expected. ~6000 chars
# (~1500 tokens) leaves comfortable room for system prompt + query + output
# within n_ctx=4096.
_MAX_CONTEXT_CHARS = 6000


def _build_user_content(query: str, retrieved: list[dict]) -> str:
    if not retrieved:
        return query
    # Each chunk is labelled with its document type so the model knows whether
    # it is reading a live contract or a synthetic comparison benchmark.
    context_block = "\n\n---\n\n".join(
        f"[{_doc_type_label(r['source_doc'])} | Section: {r['section']}]\n{r['text']}"
        for r in retrieved
    )[:_MAX_CONTEXT_CHARS]
    return (
        "Context (retrieved from internal facilities documents):\n"
        "- CURRENT CONTRACT entries are authoritative — use exact figures, names, and dates.\n"
        "- MARKET REFERENCE entries are synthetic benchmarks for comparison only — "
        "never present their figures as real contract values.\n"
        "- FM REFERENCE DOCUMENT entries are general knowledge — not contract-specific.\n"
        "If needed information is absent from the context, write 'Not specified' — "
        "do not invent details.\n\n"
        f"{context_block}\n\n---\n\nRequest:\n{query}"
    )


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

_FALLBACK_MESSAGE = (
    "NEXUS generated an answer but the quality check found it unreliable — "
    "likely a hallucinated figure or non-English fragment from the fine-tuned model.\n\n"
    "The answer has been withheld to avoid surfacing incorrect information. "
    "Try the same question on a fresher session, or use the suggestion chips "
    "for instant verified answers on common FM topics."
)


# Query types that benefit from entity-anchored retrieval (vendor/contract queries)
_ENTITY_RETRIEVAL_TYPES = {"vendor", "comparison"}

# Per-query-type generation budget.  Tighter caps for factual/general queries
# directly reduce the 2.5× length ratio without hurting quality — those answers
# don't need 400 tokens.  Structured output types (tables, emails) keep more room.
_MAX_TOKENS_BY_TYPE: dict[str, int] = {
    "factual": 180,
    "vendor": 260,
    "comparison": 260,
    "checklist": 280,
    "general": 220,
    "draft": 350,
    "vendor_decision": 350,
    "incident_triage": 300,
}


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
            # Run the fast rule-based check on cached answers to evict any bad entries
            # that were stored before the validator was tightened (no API call needed).
            from app.core.validator import _rule_check
            cache_rule = _rule_check(cached["answer"])
            if cache_rule is not None:
                # Evict the bad cached entry and fall through to regenerate
                import hashlib
                bad_key = hashlib.sha256(f"{mode}:{query.strip().lower()}".encode()).hexdigest()
                try:
                    del self.cache._cache[bad_key]
                except Exception:
                    pass
                cached = None

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
        t_query_analysis = time.time()

        # ── 3. Retrieval / Agent dispatch ────────────────────────────────────
        if processed.query_type == "incident_triage" and settings.groq_api_key:
            # Incident Triage: classify → find vendor → check SLA → draft escalation
            yield {"type": "step", "name": "incident_triage", "status": "start"}
            from app.core.agents.incident_triage_agent import run_incident_triage
            from app.core.entity_registry import get_entity_registry

            triage = run_incident_triage(
                incident=retrieval_query,
                api_key=settings.groq_api_key,
                model=settings.groq_model,
                registry=get_entity_registry(),
                retriever=self.retriever,
            )
            t_retrieval = time.time()
            yield {
                "type": "step",
                "name": "incident_triage",
                "status": "done",
                "detail": {
                    "domain": triage.domain,
                    "severity": triage.severity,
                    "vendor": triage.vendor,
                    "sla_status": triage.sla_status,
                },
            }

            if triage.succeeded and triage.escalation_email:
                sla_label = {
                    "BREACHED": "SLA breached",
                    "AT_RISK": "SLA at risk",
                    "WITHIN_SLA": "within SLA",
                    "UNKNOWN": "SLA unknown",
                }.get(triage.sla_status, "")
                hours_label = (
                    f"{triage.duration_hours:.0f}h reported, {sla_label}"
                    if triage.duration_hours else sla_label
                )
                final_answer = (
                    f"## Incident Summary\n\n"
                    f"**Domain:** {triage.domain.replace('_', ' ').title()}  \n"
                    f"**Severity:** {triage.severity.upper()}  \n"
                    f"**Responsible vendor:** {triage.vendor} ({triage.site})  \n"
                    f"**SLA:** {triage.sla_hours and f'{triage.sla_hours:.0f}h response' or 'Not specified'}  \n"
                    f"**Status:** {hours_label}\n\n"
                    f"---\n\n"
                    f"## Escalation Email\n\n"
                    f"{triage.escalation_email}"
                )
                source_docs = triage.sources
                self.cache.set(query, mode, {"answer": final_answer, "retrieved_sources": source_docs})
                yield {"type": "token", "text": final_answer}
                yield {
                    "type": "done",
                    "latency_ms": {"total": int((time.time() - t_start) * 1000)},
                    "cache_hit": None,
                    "retrieved_sources": source_docs,
                    "valid": True,
                    "final_answer": final_answer,
                    "agent_synthesized": True,
                    "agent_tool_calls": [
                        {"tool": "classify_incident", "args": {"incident": retrieval_query[:60]}, "results_found": 1},
                        {"tool": "find_vendor_for_domain", "args": {"domain": triage.domain}, "results_found": len(source_docs)},
                        {"tool": "check_sla_terms", "args": {"vendor": triage.vendor}, "results_found": 1},
                        {"tool": "draft_escalation_email", "args": {"sla_status": triage.sla_status}, "results_found": 1},
                    ],
                }
                return
            # Fall through to SLM if triage failed
            retrieved = []

        elif processed.query_type == "vendor_decision" and settings.groq_api_key:
            # Agentic path: explicitly research BOTH the current contract and the
            # competitor benchmark via separate, targeted tool calls — guaranteed
            # coverage of both document types, not just whichever ranks higher in
            # a combined similarity search.
            yield {"type": "step", "name": "agent_research", "status": "start"}
            from app.core.agents.vendor_comparison_agent import run_vendor_comparison_agent
            from app.core.entity_registry import get_entity_registry

            agent_result = run_vendor_comparison_agent(
                query=retrieval_query,
                retriever=self.retriever,
                registry=get_entity_registry(),
                api_key=settings.groq_api_key,
                model=settings.groq_model,
            )
            retrieved = agent_result.chunks
            yield {
                "type": "step",
                "name": "agent_research",
                "status": "done",
                "detail": {
                    "tool_calls": agent_result.tool_calls_made,
                    "docs_found": sorted({c["source_doc"] for c in retrieved}),
                },
            }

            t_retrieval = time.time()  # capture timestamp so log statement works in both paths

            # For vendor_decision queries, skip the 5-12 min fine-tuned SLM
            # generation entirely and use Groq to synthesize the comparison
            # directly from the gathered context. Groq is 2-3s vs 5-12 min and
            # produces more reliable, grounded, table-formatted output for this
            # structured comparison task than the small quantized SLM.
            if retrieved and settings.groq_api_key:
                yield {"type": "step", "name": "synthesis", "status": "start"}
                from app.core.agents.vendor_comparison_agent import synthesize_comparison
                from app.core.validator import _rule_check, _numeric_grounding_check

                t_synth = time.time()
                groq_answer = synthesize_comparison(
                    query=retrieval_query,
                    chunks=retrieved,
                    api_key=settings.groq_api_key,
                    model=settings.groq_model,
                )
                synth_ms = int((time.time() - t_synth) * 1000)
                yield {"type": "step", "name": "synthesis", "status": "done",
                       "detail": {"ms": synth_ms}}

                if groq_answer:
                    groq_answer = _strip_artifacts(groq_answer)
                    rule_fail = _rule_check(groq_answer)
                    numeric_fail = None if rule_fail else _numeric_grounding_check(groq_answer, retrieved)

                    if rule_fail or numeric_fail:
                        failure_reason = (rule_fail or numeric_fail).reason
                        logger.warning("groq synthesis failed safety check: %s", failure_reason)
                        groq_answer = None

                if groq_answer:
                    source_docs = sorted({r["source_doc"] for r in retrieved})
                    self.cache.set(query, mode, {"answer": groq_answer, "retrieved_sources": source_docs})
                    yield {"type": "token", "text": groq_answer}
                    total_ms = int((time.time() - t_start) * 1000)
                    logger.info(
                        "latency breakdown [vendor_decision/groq]: agent=%.1fs synthesis=%.1fs total=%.1fs",
                        t_retrieval - t_start, synth_ms / 1000, total_ms / 1000,
                    )
                    yield {
                        "type": "done",
                        "latency_ms": {"total": total_ms},
                        "cache_hit": None,
                        "retrieved_sources": source_docs,
                        "valid": True,
                        "final_answer": groq_answer,
                        "agent_synthesized": True,
                        "agent_tool_calls": agent_result.tool_calls_made,
                    }
                    return

                # Fall through to SLM if Groq synthesis failed entirely
                logger.warning("groq synthesis unavailable — falling back to SLM")
        else:
            # Route vendor/comparison queries through the entity-aware retriever
            # (anchors to the correct contract document before filling slots with
            # BM25+dense matches). All other query types use conventional retrieval
            # which is better for general domain / procedural queries.
            yield {"type": "step", "name": "retrieval", "status": "start"}
            active_retriever = (
                get_entity_retriever()
                if processed.query_type in _ENTITY_RETRIEVAL_TYPES
                else self.retriever
            )
            candidates = active_retriever.retrieve(retrieval_query)
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
                        {
                            "source_doc": r["source_doc"],
                            "section": r["section"],
                            "score": round(r["score"], 3),
                            # First 400 chars of chunk text — used by the eval harness
                            # for G-Eval faithfulness scoring without bloating the SSE payload.
                            "text_preview": r["text"][:400],
                        }
                        for r in retrieved
                    ]
                },
            }

        t_retrieval = time.time()

        # ── 4. Generation ─────────────────────────────────────────────────────
        # Agent-routed queries are standalone research questions with their own
        # freshly-gathered context (already up to 4 chunks); conversation history
        # would only add token overhead without much relevance, so it's skipped
        # to keep the prompt -- and CPU prefill time -- as small as possible.
        history_messages = (
            []
            if processed.query_type == "vendor_decision"
            else _build_history_messages(history, settings.max_history_turns)
        )
        messages = [
            {"role": "system", "content": self.system_prompt},
            *history_messages,
            {"role": "user", "content": _build_user_content(retrieval_query, retrieved)},
        ]
        prompt_chars = sum(len(m["content"]) for m in messages)

        yield {"type": "step", "name": "generation", "status": "start"}
        t0 = time.time()
        gen_max_tokens = _MAX_TOKENS_BY_TYPE.get(processed.query_type, settings.max_new_tokens)
        answer_parts: list[str] = []
        try:
            for token in self.llm.stream_chat(messages, temperature=temperature, max_tokens=gen_max_tokens):
                answer_parts.append(token)
                yield {"type": "token", "text": token}
        except LLMBusyError:
            # Fail fast instead of silently queueing behind another generation --
            # queueing let two overlapping requests compound into 20+ minute waits.
            yield {"type": "step", "name": "generation", "status": "done", "detail": {"busy": True}}
            yield {
                "type": "done",
                "latency_ms": {"total": int((time.time() - t_start) * 1000)},
                "cache_hit": None,
                "retrieved_sources": [],
                "valid": False,
                "fallback": (
                    "NEXUS is currently generating another answer and can only handle one "
                    "request at a time on this free-tier deployment.\n\n"
                    "Please wait a minute and try again."
                ),
                "validation_reason": "llm busy",
            }
            return
        raw_answer = _strip_artifacts("".join(answer_parts))
        t_generation = time.time()
        yield {"type": "step", "name": "generation", "status": "done",
               "detail": {"ms": int((t_generation - t0) * 1000)}}

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
        t_end = time.time()
        logger.info(
            "latency breakdown [%s]: query_analysis=%.1fs retrieval/agent=%.1fs "
            "generation=%.1fs refinement=%.1fs total=%.1fs prompt_chars=%d",
            processed.query_type,
            t_query_analysis - t_start,
            t_retrieval - t_query_analysis,
            t_generation - t0,
            t_end - t_generation,
            t_end - t_start,
            prompt_chars,
        )
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
