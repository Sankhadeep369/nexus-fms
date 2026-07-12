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
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from typing import Any

from app.core.cache import ResponseCache, get_response_cache
from app.core.capabilities import RETRIEVAL_ENTITY, get_capability, passes_agent_precondition
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


def _doc_type_label(source_doc: str) -> str:
    """Human label for a chunk's document class (CURRENT CONTRACT / MARKET
    REFERENCE / FM REFERENCE DOCUMENT). Derived from the self-describing corpus
    index (manifest + inferred roles) rather than a hardcoded folder map, so a
    new doc class is labelled correctly without a code change."""
    from app.core.corpus_index import get_corpus_index

    return get_corpus_index().label_of(source_doc)


# Hard ceiling on combined context length regardless of how many chunks were
# gathered (standard retrieval, entity-aware, or agent) -- defends prefill time
# even if a future code path passes in more chunks than expected. ~6000 chars
# (~1500 tokens) leaves comfortable room for system prompt + query + output
# within n_ctx=4096.
_MAX_CONTEXT_CHARS = 6000


def _compress_context(query: str, chunks: list[dict], api_key: str, model: str) -> list[dict]:
    """Reduce each retrieved chunk to only the sentences directly relevant to the query.

    A single Groq call processes all chunks at once (no per-chunk round-trip) and
    returns the 2-3 most relevant sentences from each.  The header block (vendor/site
    identity) is always re-prepended so the SLM retains document provenance even after
    compression.  Fails open: any parse failure returns the original chunks unchanged.

    Why: a 1500-char contract section contains section boilerplate, unrelated clauses,
    and repeated metadata.  Stripping these before generation reduces context noise,
    lowers prefill token count (~40% typical reduction), and focuses the SLM on the
    signal that actually answers the query.
    """
    if not api_key or not chunks:
        return chunks

    # Build a numbered chunk list for the prompt
    chunk_texts = "\n\n---CHUNK---\n\n".join(
        f"[{i + 1}]\n{c['text'][:700]}" for i, c in enumerate(chunks)
    )
    prompt = (
        f"QUERY: {query[:300]}\n\n"
        "For each numbered chunk below, copy verbatim the 2-3 sentences most relevant "
        "to the query. Include exact numbers, dates, currency figures, and vendor names "
        "as written. If a chunk has no relevant content write 'SKIP'.\n\n"
        f"CHUNKS:\n{chunk_texts}\n\n"
        f"Output format — one block per chunk, nothing else:\n"
        + "\n".join(f"[{i + 1}]: <extracted sentences or SKIP>" for i in range(len(chunks)))
    )

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max(400, len(chunks) * 120),
            temperature=0.0,
        )
        raw = response.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("contextual compression Groq call failed (%s) — using original chunks", exc)
        return chunks

    compressed = list(chunks)
    for i, chunk in enumerate(chunks):
        # Match "[N]: <content>"
        m = re.search(rf"\[{i + 1}\]:\s*(.+?)(?=\[{i + 2}\]|\Z)", raw, re.DOTALL)
        if not m:
            continue
        extracted = m.group(1).strip()
        if not extracted or extracted.upper() == "SKIP" or len(extracted) < 30:
            continue
        # Preserve the document header block (everything before the first section heading)
        # so vendor/site identity is carried through to the SLM prompt.
        header_end = chunk["text"].find("\n\n# ")
        header = chunk["text"][:header_end].strip() if header_end > 0 else ""
        compressed_text = f"{header}\n\n{extracted}" if header else extracted
        new_chunk = dict(chunk)
        new_chunk["text"] = compressed_text
        compressed[i] = new_chunk

    before_chars = sum(len(c["text"]) for c in chunks)
    after_chars = sum(len(c["text"]) for c in compressed)
    logger.info(
        "contextual compression: %d chunks  %d → %d chars (%.0f%% reduction)",
        len(chunks), before_chars, after_chars,
        100 * (1 - after_chars / max(before_chars, 1)),
    )
    return compressed


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

# Shown ONLY when both the SLM and the Groq recovery are unreachable — i.e. a
# genuine connectivity issue, never a model-quality problem. Everything else is
# recovered silently, so the user never sees a "quality check failed" message.
_CONNECTIVITY_MESSAGE = (
    "NEXUS can't reach the answer service right now. This is a temporary "
    "connectivity issue on the free-tier deployment — please try again in a moment."
)


# Per-intent behaviour (retrieval strategy, k, compression, generation budget,
# history, agent dispatch) now lives in the capability registry — see
# app/core/capabilities.py.  A capability is looked up once per request via
# get_capability(query_type) and its fields drive the whole pipeline, replacing
# the four hand-tuned per-type tables that used to live here.

# Maps a capability's `agent` id to the ChatPipeline method that handles it.
# Registering a new agent = add the method + one entry here (no elif chain).
_AGENT_METHODS: dict[str, str] = {
    "incident_triage": "_agent_incident_triage",
    "vendor_comparison": "_agent_vendor_decision",
    "budget_analysis": "_agent_budget_analysis",
    "portfolio_overview": "_agent_portfolio_overview",
    "contract_timeline": "_agent_contract_timeline",
}


@dataclass
class _AgentOutcome:
    """Result of an agent handler. `handled=True` means it already emitted the
    final `done` event and the pipeline should return; `handled=False` means fall
    through to SLM generation using `retrieved` as context."""

    handled: bool
    retrieved: list[dict] = field(default_factory=list)


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
        bypass_cache: bool = False,
    ) -> Iterator[dict[str, Any]]:
        t_start = time.time()
        history = history or []
        temperature = (
            settings.temperature_thinking if mode == "thinking"
            else settings.temperature_simple
        )

        # ── 1. Cache lookup ─────────────────────────────────────────────────
        # bypass_cache (eval harness) forces cold inference: skip the read here and
        # every self.cache.set below, so a cached answer can't corrupt the metrics.
        yield {"type": "step", "name": "cache_lookup", "status": "start"}
        cached = None if bypass_cache else self.cache.get(query, mode)
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

        # ── 2b. Clarification gate ────────────────────────────────────────────
        # If the preprocessor flagged the query as needing scope clarification
        # (e.g. "per system" without naming the systems), stop here and return a
        # structured clarification response.  The UI renders quick-reply chips so
        # the user can tap an option; the follow-up query then has clear scope
        # and the full pipeline runs normally on the second pass.
        if processed.needs_clarification and processed.clarification_question:
            logger.info("clarification required: %s", processed.clarification_question)
            yield {
                "type": "done",
                "latency_ms": {"total": int((time.time() - t_start) * 1000)},
                "cache_hit": None,
                "retrieved_sources": [],
                "valid": True,
                "final_answer": processed.clarification_question,
                "needs_clarification": True,
                "clarification_question": processed.clarification_question,
                "clarification_options": processed.clarification_options,
            }
            return

        retrieval_query = processed.rewritten
        t_query_analysis = time.time()

        # ── 3. Retrieval / Agent dispatch ────────────────────────────────────
        # The capability decides the path: an agent handler (cap.agent) owns
        # execution and may emit the final answer itself; otherwise standard /
        # entity retrieval runs and we fall through to SLM generation.  All
        # tuning (retrieval strategy, k, generation budget) lives on `cap`.
        cap = get_capability(processed.query_type)
        # Defense in depth: a committed agent runs only if the query genuinely fits
        # it. If the classifier misrouted (e.g. a "how many days until renewal"
        # question onto budget_analysis), the precondition fails and we downgrade to
        # standard retrieval + SLM so the user gets an answer to what they actually
        # asked, not a confident wrong-shaped agent answer.
        agent_ok = cap.agent in _AGENT_METHODS and settings.groq_api_key
        if agent_ok and not passes_agent_precondition(cap.name, query):
            logger.info(
                "agent '%s' precondition failed for query %r — downgrading to SLM path",
                cap.agent, query[:80],
            )
            agent_ok = False

        retrieved: list[dict] = []
        if agent_ok:
            handler = getattr(self, _AGENT_METHODS[cap.agent])
            outcome = yield from handler(query, mode, retrieval_query, t_start, bypass_cache)
            if outcome.handled:
                return
            retrieved = outcome.retrieved
        else:
            retrieved = yield from self._standard_retrieval(cap, retrieval_query)

        t_retrieval = time.time()

        # ── 3b. Contextual compression ────────────────────────────────────────
        # Extract only the query-relevant sentences from each retrieved chunk
        # before passing them to the SLM.  Reduces context noise and prompt
        # length without changing which documents are cited.  Skipped for agent
        # paths (vendor_decision / incident_triage) which already gather curated,
        # targeted chunks via explicit tool calls.
        #
        # Compression is also skipped for capabilities that require exact numeric
        # values, dates, and SLA figures verbatim (cap.compress is False).
        # Extracting "2-3 relevant sentences" from a contract clause strips tables
        # and multi-part financial data, causing the SLM to hallucinate the figures.
        if (
            settings.context_compression_enabled
            and settings.groq_api_key
            and retrieved
            and cap.compress
        ):
            retrieved = _compress_context(
                retrieval_query, retrieved, settings.groq_api_key, settings.groq_model
            )

        # ── 4. Generation ─────────────────────────────────────────────────────
        # Agent-routed queries are standalone research questions with their own
        # freshly-gathered context (already up to 4 chunks); conversation history
        # would only add token overhead without much relevance, so it's skipped
        # to keep the prompt -- and CPU prefill time -- as small as possible.
        history_messages = (
            _build_history_messages(history, settings.max_history_turns)
            if cap.use_history
            else []
        )
        messages = [
            {"role": "system", "content": self.system_prompt},
            *history_messages,
            {"role": "user", "content": _build_user_content(retrieval_query, retrieved)},
        ]
        prompt_chars = sum(len(m["content"]) for m in messages)

        yield {"type": "step", "name": "generation", "status": "start"}
        t0 = time.time()
        gen_max_tokens = cap.max_tokens
        answer_parts: list[str] = []
        try:
            for token in self.llm.stream_chat(messages, temperature=temperature, max_tokens=gen_max_tokens):
                answer_parts.append(token)
                yield {"type": "token", "text": token}
        except LLMBusyError:
            # The single SLM context is busy. Rather than making the user wait,
            # recover immediately with a fast grounded Groq answer from the context
            # already retrieved — no error surfaced, and lower latency than queueing.
            yield {"type": "step", "name": "generation", "status": "done", "detail": {"busy": True}}
            from app.core.recovery import recover_answer

            yield {"type": "step", "name": "recovery", "status": "start"}
            recovered = recover_answer(
                processed.rewritten, processed.query_type, retrieved,
                settings.groq_api_key, settings.groq_model,
            )
            yield {"type": "step", "name": "recovery", "status": "done",
                   "detail": {"ok": bool(recovered), "reason": "slm_busy"}}
            if recovered:
                source_docs = sorted({r["source_doc"] for r in retrieved})
                if not bypass_cache:
                    self.cache.set(query, mode, {"answer": recovered, "retrieved_sources": source_docs})
                yield {"type": "token", "text": recovered}
                yield {
                    "type": "done",
                    "latency_ms": {"total": int((time.time() - t_start) * 1000)},
                    "cache_hit": None, "retrieved_sources": source_docs,
                    "valid": True, "final_answer": recovered, "recovered": True,
                }
                return
            # SLM busy AND Groq unreachable → genuine connectivity issue.
            yield {
                "type": "done",
                "latency_ms": {"total": int((time.time() - t_start) * 1000)},
                "cache_hit": None, "retrieved_sources": [],
                "valid": False, "fallback": _CONNECTIVITY_MESSAGE,
                "validation_reason": "llm busy, recovery unavailable",
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
        # Decide if the answer is unusable and must be recovered rather than shown:
        #  (a) hard validation failure (non-English / garbled / rewriter reject), or
        #  (b) a hallucination that survived the rewriter — ungrounded figures on a
        #      context-backed query. Either way the user must never see an error.
        recovered_flag = False
        needs_recovery = not result.passed
        recovery_reason = result.reason
        if result.passed and retrieved:
            from app.core.validator import _numeric_grounding_check
            ng = _numeric_grounding_check(result.answer, retrieved)
            if ng is not None:
                logger.info("post-refinement hallucination detected (%s) — recovering", ng.reason)
                needs_recovery = True
                recovery_reason = ng.reason

        if needs_recovery:
            from app.core.recovery import recover_answer
            yield {"type": "step", "name": "recovery", "status": "start"}
            recovered = recover_answer(
                processed.rewritten, processed.query_type, retrieved,
                settings.groq_api_key, settings.groq_model,
            )
            yield {"type": "step", "name": "recovery", "status": "done",
                   "detail": {"ok": bool(recovered), "reason": recovery_reason}}
            if recovered:
                from app.core.validator import ValidationResult
                result = ValidationResult(passed=True, answer=recovered, reason="recovered")
                recovered_flag = True
            else:
                # Both the SLM answer and the Groq recovery are unusable — only a
                # genuine outage reaches the user, framed as connectivity.
                yield {
                    "type": "done",
                    "latency_ms": {"total": int((time.time() - t_start) * 1000)},
                    "cache_hit": None, "retrieved_sources": [],
                    "valid": False, "fallback": _CONNECTIVITY_MESSAGE,
                    "validation_reason": f"recovery unavailable ({recovery_reason})",
                }
                return

        final_answer = result.answer
        if not bypass_cache:
            self.cache.set(query, mode, {"answer": final_answer, "retrieved_sources": source_docs})
        yield {
            "type": "done",
            "latency_ms": {"total": int((time.time() - t_start) * 1000)},
            "cache_hit": None,
            "retrieved_sources": source_docs,
            "valid": True,
            "final_answer": final_answer,
            "recovered": recovered_flag,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Agent handlers.  Each owns a self-contained agentic path: it emits its own
    # SSE step/token/done events and returns an _AgentOutcome telling run()
    # whether it produced the final answer (handled=True → return) or fell back
    # (handled=False → run() continues to SLM generation with .retrieved).
    # Registered in _AGENT_METHODS by capability agent id.
    # ─────────────────────────────────────────────────────────────────────────

    def _agent_incident_triage(
        self, query: str, mode: str, retrieval_query: str, t_start: float,
        bypass_cache: bool = False,
    ) -> Iterator[dict[str, Any]]:
        # Incident Triage: classify → find vendor → check SLA → draft escalation
        yield {"type": "step", "name": "incident_triage", "status": "start"}
        from app.core.agents.incident_triage_agent import run_incident_triage

        triage = run_incident_triage(
            incident=retrieval_query,
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            retriever=self.retriever,
        )
        yield {
            "type": "step",
            "name": "incident_triage",
            "status": "done",
            "detail": {
                "domain": triage.domain,
                "severity": triage.severity,
                "vendor": triage.vendor,
                "sla_status": triage.sla_status,
                "sources": [{"source_doc": s, "section": "", "text_preview": ""} for s in (triage.sources or [])],
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
            if not bypass_cache:
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
            return _AgentOutcome(handled=True)
        # Triage failed — fall through to SLM with no context
        return _AgentOutcome(handled=False, retrieved=[])

    def _agent_vendor_decision(
        self, query: str, mode: str, retrieval_query: str, t_start: float,
        bypass_cache: bool = False,
    ) -> Iterator[dict[str, Any]]:
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
                "sources": [
                    {"source_doc": c["source_doc"], "section": c.get("section", ""), "text_preview": c["text"][:300]}
                    for c in retrieved
                ],
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

                # Verify-then-refine: catch structural (malformed table) and
                # currency (raw cross-currency comparison) issues and let the model
                # fix just those once, before the safety validators and shipping.
                from app.core.verify import refine_answer, verify_answer

                report = verify_answer(groq_answer, check_currency=True)
                if not report.ok:
                    revised = refine_answer(
                        groq_answer, report.issues, settings.groq_api_key, settings.groq_model
                    )
                    if revised:
                        revised = _strip_artifacts(revised)
                        report2 = verify_answer(revised, check_currency=True)
                        if len(report2.issues) < len(report.issues):
                            groq_answer, report = revised, report2
                yield {
                    "type": "step", "name": "verification", "status": "done",
                    "detail": {"ok": report.ok, "issues": [i.code for i in report.issues]},
                }

                rule_fail = _rule_check(groq_answer)
                numeric_fail = None if rule_fail else _numeric_grounding_check(groq_answer, retrieved)

                if rule_fail or numeric_fail:
                    failure_reason = (rule_fail or numeric_fail).reason
                    logger.warning("groq synthesis failed safety check: %s", failure_reason)
                    groq_answer = None

            if groq_answer:
                source_docs = sorted({r["source_doc"] for r in retrieved})
                if not bypass_cache:
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
                return _AgentOutcome(handled=True)

            # Fall through to SLM if Groq synthesis failed entirely
            logger.warning("groq synthesis unavailable — falling back to SLM")

        return _AgentOutcome(handled=False, retrieved=retrieved)

    def _agent_budget_analysis(
        self, query: str, mode: str, retrieval_query: str, t_start: float,
        bypass_cache: bool = False,
    ) -> Iterator[dict[str, Any]]:
        # Agentic path: retrieve financial sections from ALL vendor contracts,
        # extract cost data via Groq (structured JSON), synthesise a per-system
        # annual budget table with grand total — bypasses SLM entirely.
        yield {"type": "step", "name": "agent_research", "status": "start"}
        from app.core.agents.budget_analysis_agent import run_budget_analysis

        budget_year = date.today().year
        budget_result = run_budget_analysis(
            query=retrieval_query,
            year=budget_year,
            retriever=self.retriever,
            api_key=settings.groq_api_key,
            model=settings.groq_model,
        )
        t_retrieval = time.time()
        source_docs = sorted({c["source_doc"] for c in budget_result.chunks_used})
        yield {
            "type": "step",
            "name": "agent_research",
            "status": "done",
            "detail": {
                "docs_found": source_docs,
                "line_items": len(budget_result.line_items),
                "sources": [
                    {"source_doc": c["source_doc"], "section": c.get("section", ""), "text_preview": c["text"][:300]}
                    for c in budget_result.chunks_used
                ],
            },
        }

        if budget_result.succeeded and budget_result.answer:
            from app.core.verify import verify_answer

            report = verify_answer(budget_result.answer)
            if not report.ok:
                logger.warning("budget answer failed verification: %s", report.summary())
            yield {"type": "step", "name": "verification", "status": "done",
                   "detail": {"ok": report.ok, "issues": [i.code for i in report.issues]}}
            if not bypass_cache:
                self.cache.set(query, mode, {"answer": budget_result.answer, "retrieved_sources": source_docs})
            yield {"type": "token", "text": budget_result.answer}
            total_ms = int((time.time() - t_start) * 1000)
            logger.info(
                "latency breakdown [budget_analysis/groq]: retrieve=%.1fs total=%.1fs items=%d",
                t_retrieval - t_start, total_ms / 1000, len(budget_result.line_items),
            )
            yield {
                "type": "done",
                "latency_ms": {"total": total_ms},
                "cache_hit": None,
                "retrieved_sources": source_docs,
                "valid": True,
                "final_answer": budget_result.answer,
                "agent_synthesized": True,
                "agent_tool_calls": [
                    {"tool": "read_contract_facts", "args": {"scope": "current"}, "results_found": len(budget_result.line_items)},
                    {"tool": "compute_annual_budget", "args": {"year": budget_year}, "results_found": len(budget_result.chunks_used)},
                    {"tool": "format_budget_table", "args": {}, "results_found": 1},
                ],
            }
            return _AgentOutcome(handled=True)
        # Agent failed — fall through to SLM with whatever chunks were retrieved
        logger.warning("budget_analysis agent failed — falling back to SLM")
        return _AgentOutcome(handled=False, retrieved=budget_result.chunks_used)

    def _agent_portfolio_overview(
        self, query: str, mode: str, retrieval_query: str, t_start: float,
        bypass_cache: bool = False,
    ) -> Iterator[dict[str, Any]]:
        # Agentic path: retrieve contract headers from ALL current vendor agreements,
        # extract {system, vendor, category, agreement_no, term} via Groq, synthesise
        # a complete Markdown registry table — bypasses SLM to avoid format noise.
        yield {"type": "step", "name": "agent_research", "status": "start"}
        from app.core.agents.portfolio_overview_agent import run_portfolio_overview

        overview_result = run_portfolio_overview(
            query=retrieval_query,
            retriever=self.retriever,
            api_key=settings.groq_api_key,
            model=settings.groq_model,
        )
        t_retrieval = time.time()
        source_docs = sorted({c["source_doc"] for c in overview_result.chunks_used})
        yield {
            "type": "step",
            "name": "agent_research",
            "status": "done",
            "detail": {
                "docs_found": source_docs,
                "contracts_found": len(overview_result.contracts),
                "sources": [
                    {"source_doc": c["source_doc"], "section": c.get("section", ""), "text_preview": c["text"][:300]}
                    for c in overview_result.chunks_used
                ],
            },
        }

        if overview_result.succeeded and overview_result.answer:
            from app.core.verify import verify_answer

            report = verify_answer(overview_result.answer)
            if not report.ok:
                logger.warning("portfolio answer failed verification: %s", report.summary())
            yield {"type": "step", "name": "verification", "status": "done",
                   "detail": {"ok": report.ok, "issues": [i.code for i in report.issues]}}
            if not bypass_cache:
                self.cache.set(query, mode, {"answer": overview_result.answer, "retrieved_sources": source_docs})
            yield {"type": "token", "text": overview_result.answer}
            total_ms = int((time.time() - t_start) * 1000)
            logger.info(
                "latency breakdown [portfolio_overview/groq]: retrieve=%.1fs total=%.1fs contracts=%d",
                t_retrieval - t_start, total_ms / 1000, len(overview_result.contracts),
            )
            yield {
                "type": "done",
                "latency_ms": {"total": total_ms},
                "cache_hit": None,
                "retrieved_sources": source_docs,
                "valid": True,
                "final_answer": overview_result.answer,
                "agent_synthesized": True,
                "agent_tool_calls": [
                    {"tool": "retrieve_contract_headers", "args": {"method": "direct_enumeration"}, "results_found": len(overview_result.chunks_used)},
                    {"tool": "extract_contract_records", "args": {"model": settings.groq_model}, "results_found": len(overview_result.contracts)},
                    {"tool": "synthesise_vendor_table", "args": {}, "results_found": 1},
                ],
            }
            return _AgentOutcome(handled=True)
        logger.warning("portfolio_overview agent failed — falling back to SLM")
        return _AgentOutcome(handled=False, retrieved=overview_result.chunks_used)

    def _agent_contract_timeline(
        self, query: str, mode: str, retrieval_query: str, t_start: float,
        bypass_cache: bool = False,
    ) -> Iterator[dict[str, Any]]:
        # Grounded temporal path: compute each current contract's renewal date
        # (effective + term) and days-from-today in Python, then let Groq answer the
        # user's specific "when / how many days until" question from that timeline.
        yield {"type": "step", "name": "agent_research", "status": "start"}
        from app.core.agents.contract_timeline_agent import run_contract_timeline

        result = run_contract_timeline(
            retrieval_query, self.retriever, settings.groq_api_key, settings.groq_model,
        )
        t_retrieval = time.time()
        source_docs = sorted({c["source_doc"] for c in result.chunks_used})
        yield {
            "type": "step", "name": "agent_research", "status": "done",
            "detail": {
                "docs_found": source_docs,
                "contracts_found": len(result.rows),
                "sources": [
                    {"source_doc": c["source_doc"], "section": c.get("section", ""), "text_preview": c["text"][:300]}
                    for c in result.chunks_used
                ],
            },
        }

        if result.succeeded and result.answer:
            from app.core.verify import verify_answer

            report = verify_answer(result.answer)
            if not report.ok:
                logger.warning("timeline answer failed verification: %s", report.summary())
            yield {"type": "step", "name": "verification", "status": "done",
                   "detail": {"ok": report.ok, "issues": [i.code for i in report.issues]}}
            if not bypass_cache:
                self.cache.set(query, mode, {"answer": result.answer, "retrieved_sources": source_docs})
            yield {"type": "token", "text": result.answer}
            total_ms = int((time.time() - t_start) * 1000)
            logger.info(
                "latency breakdown [contract_timeline/groq]: compute=%.1fs total=%.1fs contracts=%d",
                t_retrieval - t_start, total_ms / 1000, len(result.rows),
            )
            yield {
                "type": "done",
                "latency_ms": {"total": total_ms},
                "cache_hit": None,
                "retrieved_sources": source_docs,
                "valid": True,
                "final_answer": result.answer,
                "agent_synthesized": True,
                "agent_tool_calls": [
                    {"tool": "compute_renewal_dates", "args": {"scope": "current"}, "results_found": len(result.rows)},
                    {"tool": "answer_timing_question", "args": {"model": settings.groq_model}, "results_found": 1},
                ],
            }
            return _AgentOutcome(handled=True)
        logger.warning("contract_timeline agent failed — falling back to SLM")
        return _AgentOutcome(handled=False, retrieved=result.chunks_used)

    def _standard_retrieval(
        self, cap, retrieval_query: str
    ) -> Iterator[dict[str, Any]]:
        # Entity capabilities (vendor/comparison) anchor to the correct contract
        # document before filling slots with BM25+dense matches; everything else
        # uses conventional retrieval, better for general/procedural queries.
        yield {"type": "step", "name": "retrieval", "status": "start"}
        use_entity = cap.retrieval == RETRIEVAL_ENTITY
        active_retriever = get_entity_retriever() if use_entity else self.retriever
        retrieval_k = cap.retrieval_k

        if use_entity:
            # Entity-aware retriever: anchor:fill slot ratio is keyed to k, so
            # call with retrieval_k directly.  The 0.18 dense gate handles gate
            # failures for entity-anchored chunks without breaking slot allocation.
            raw_candidates = active_retriever.retrieve(retrieval_query, k=retrieval_k)
            retrieved = [
                c for c in raw_candidates
                if c["dense_score"] >= active_retriever.min_dense_score
                or c["bm25_score"] >= settings.retrieval_min_bm25_score
            ]
        else:
            # Standard retriever: fetch the full cross-encoder candidate pool
            # (reranker_candidates=20) so the relevance gate can rescue high-BM25
            # chunks that the cross-encoder moved below position k.
            # Cross-encoder always evaluates max(k, 20) pairs anyway — no extra compute.
            fetch_k = settings.retrieval_reranker_candidates
            all_candidates = active_retriever.retrieve(retrieval_query, k=fetch_k)
            gated = [
                c for c in all_candidates
                if c["dense_score"] >= active_retriever.min_dense_score
                or c["bm25_score"] >= settings.retrieval_min_bm25_score
            ]
            retrieved = gated[:retrieval_k]
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
        return retrieved


@lru_cache(maxsize=1)
def get_chat_pipeline() -> ChatPipeline:
    return ChatPipeline(cache=get_response_cache(), llm=get_llm(), retriever=get_retriever())
