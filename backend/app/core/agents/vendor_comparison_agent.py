"""Vendor Comparison Agent.

Unlike single-shot retrieval, this agent explicitly plans and executes
separate, targeted lookups for the current vendor's contract AND the
competitor/market benchmark — guaranteeing both are represented in the
gathered context, regardless of how they'd rank against each other in a
combined similarity search.

The agent's job is RESEARCH GATHERING only. It does not write the final
answer — that stays with the fine-tuned SLM (consistent with the rest of the
pipeline), keeping domain-specific writing in the fine-tuned model's voice.
Groq acts purely as the planner/orchestrator deciding which tools to call.

Capped at MAX_TOOL_CALLS iterations to bound latency and Groq API usage.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from app.core.agents.tools import find_competitor_benchmark, find_vendor_contract
from app.core.entity_registry import EntityRegistry
from app.core.retrieval import Retriever

logger = logging.getLogger("nexus.agent.vendor_comparison")

MAX_TOOL_CALLS = 4

_AGENT_SYSTEM_PROMPT = """\
You are a procurement research agent for NEXUS, a facilities management assistant.
Your job is to GATHER information needed to answer a vendor comparison or renewal
decision question. You do NOT write the final answer — only gather research.

Tools available:
- find_vendor_contract(vendor_or_service): looks up the CURRENT contract terms for
  a named vendor or service type (e.g. "Summit Lift Services", "HVAC vendor")
- find_competitor_benchmark(service_category): looks up market/competitor benchmark
  data for a service category (e.g. "Lifts", "HVAC", "CCTV", "Plumbing")

For a vendor renewal or comparison decision, call BOTH tools: first
find_vendor_contract for the current terms, then find_competitor_benchmark for
the same service category to get market alternatives.

Once you have gathered enough information (usually 2 tool calls), respond with
a short confirmation sentence. Do not attempt to answer the user's question."""

_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "find_vendor_contract",
            "description": "Look up the CURRENT contract terms for a named vendor or service type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "vendor_or_service": {
                        "type": "string",
                        "description": "Vendor name or service type, e.g. 'Summit Lift Services' or 'HVAC vendor'",
                    }
                },
                "required": ["vendor_or_service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_competitor_benchmark",
            "description": "Look up market/competitor comparison data for a service category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_category": {
                        "type": "string",
                        "description": "Service category, e.g. 'Lifts', 'HVAC', 'CCTV', 'Plumbing'",
                    }
                },
                "required": ["service_category"],
            },
        },
    },
]


@dataclass
class AgentResult:
    chunks: list[dict] = field(default_factory=list)
    tool_calls_made: list[dict] = field(default_factory=list)
    succeeded: bool = True
    reason: str = "ok"


def _dedupe_chunks(chunks: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for c in chunks:
        key = (c["source_doc"], c["section"])
        if key not in seen:
            seen.add(key)
            result.append(c)
    return result


def run_vendor_comparison_agent(
    query: str,
    retriever: Retriever,
    registry: EntityRegistry,
    api_key: str,
    model: str,
) -> AgentResult:
    if not api_key:
        return AgentResult(succeeded=False, reason="no Groq API key configured")

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        messages: list[dict] = [
            {"role": "system", "content": _AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        gathered_chunks: list[dict] = []
        tool_calls_made: list[dict] = []

        for _ in range(MAX_TOOL_CALLS):
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=_TOOL_SCHEMAS,
                tool_choice="auto",
                max_tokens=300,
                temperature=0.0,
            )
            msg = response.choices[0].message

            if not msg.tool_calls:
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )

            for tool_call in msg.tool_calls:
                name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                if name == "find_vendor_contract":
                    result = find_vendor_contract(retriever, registry, args.get("vendor_or_service", ""))
                elif name == "find_competitor_benchmark":
                    result = find_competitor_benchmark(retriever, registry, args.get("service_category", ""))
                else:
                    result = []

                gathered_chunks.extend(result)
                tool_calls_made.append({"tool": name, "args": args, "results_found": len(result)})

                summary = (
                    f"Found {len(result)} section(s): "
                    + ", ".join(f"{r['source_doc'].split('/')[-1]}::{r['section']}" for r in result)
                    if result
                    else "No matching documents found."
                )
                messages.append(
                    {"role": "tool", "tool_call_id": tool_call.id, "content": summary}
                )

        logger.info("agent gathered %d chunks via %d tool calls", len(gathered_chunks), len(tool_calls_made))
        return AgentResult(
            chunks=_dedupe_chunks(gathered_chunks),
            tool_calls_made=tool_calls_made,
            succeeded=len(gathered_chunks) > 0,
            reason="ok" if gathered_chunks else "no documents found by agent",
        )

    except Exception as exc:
        logger.warning("vendor comparison agent failed (%s)", exc)
        return AgentResult(succeeded=False, reason=str(exc))


# ---------------------------------------------------------------------------
# Groq-based synthesis (replaces the slow fine-tuned SLM for vendor_decision)
# ---------------------------------------------------------------------------

_SYNTHESIS_PROMPT = """\
You are a facilities management procurement analyst. Using only the retrieved \
contract context below, write a concise vendor renewal analysis in English.

RETRIEVED CONTEXT:
{context}

USER QUESTION: {query}

Write:
1. A Markdown table with columns: Term | Current Vendor | Market Benchmark
   - Extract exact values VERBATIM from the context, including the currency symbol
     and units as written (e.g. "$36,000", "INR 14,40,000", "Included", "N/A")
   - CURRENT CONTRACT entries → Current Vendor column
   - MARKET REFERENCE entries → Market Benchmark column
   - Write "Not specified" only if the context genuinely has no value for that term
2. A bolded **Recommendation:** sentence — state renew, switch, or negotiate, \
with one brief reason grounded in the table

Rules: English only. No invented names, amounts, or dates. Do not mention \
"retrieved documents" or "context". No trailing disclaimers or meta-commentary."""


def synthesize_comparison(
    query: str,
    chunks: list[dict],
    api_key: str,
    model: str,
) -> str | None:
    """Use Groq to synthesize the final vendor comparison answer from the gathered
    context chunks. Returns the answer text, or None on failure.

    This replaces the fine-tuned SLM for vendor_decision queries because:
    - Speed: 2-3s vs ~5-12 min CPU generation
    - Quality: instruction-following is far more reliable at this task
    - Grounding: context is explicitly provided, minimizing hallucination risk
    """
    if not chunks or not api_key:
        return None
    try:
        from app.core.chat_pipeline import _doc_type_label

        from groq import Groq

        context_text = "\n\n---\n\n".join(
            f"[{_doc_type_label(c['source_doc'])} | {c['section']}]\n{c['text']}"
            for c in chunks
        )[:5000]

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": _SYNTHESIS_PROMPT.format(
                        context=context_text,
                        query=query[:500],
                    ),
                }
            ],
            max_tokens=800,
            temperature=0.1,
        )
        answer = response.choices[0].message.content.strip()
        logger.info("groq synthesis produced %d chars", len(answer))
        return answer
    except Exception as exc:
        logger.warning("groq synthesis failed (%s)", exc)
        return None
