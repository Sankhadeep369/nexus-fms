"""Query capability registry (Phase 2 dynamic architecture).

Single source of truth for everything the pipeline needs to know about a query
*intent*. Previously this knowledge was scattered across seven places — the
classifier prompt's type enum, `valid_types`, the never-clarify list (in
query_processor), and `_ENTITY_RETRIEVAL_TYPES`, `_RETRIEVAL_K_BY_TYPE`,
`_COMPRESSION_SKIP_TYPES`, `_MAX_TOKENS_BY_TYPE` plus an elif dispatch chain (in
chat_pipeline). Adding or tuning an intent meant editing all of them and hoping
they stayed consistent.

Now each intent is one `QueryCapability` row. The classifier prompt, the valid
type set, the clarification policy, the retrieval strategy, the generation
budget, and the agent dispatch all read from this list. Adding a retrieval-only
intent is pure config (append a row); adding an agent intent additionally means
registering a handler in chat_pipeline's agent map.

The list is ORDER-SENSITIVE: the classifier is told to apply the first matching
type, so the order here is the routing priority (most specific first).
"""

from __future__ import annotations

from dataclasses import dataclass


# Retrieval strategies a capability can request for the standard SLM path.
RETRIEVAL_STANDARD = "standard"   # hybrid BM25+dense over the whole corpus
RETRIEVAL_ENTITY = "entity"       # entity-anchored (vendor/agreement) then fill
RETRIEVAL_NONE = "none"           # no retrieval (answer from system prompt alone)


@dataclass(frozen=True)
class QueryCapability:
    """Declarative description of one query intent."""

    name: str                       # intent id, also the classifier "type" value
    criteria: str                   # guidance rendered into the classifier prompt

    # Agent dispatch — if set, an agent handler owns execution and bypasses the
    # SLM (see chat_pipeline._AGENT_METHODS). None => standard retrieval + SLM.
    agent: str | None = None

    # Standard SLM path config (also used for an agent's SLM fallback).
    retrieval: str = RETRIEVAL_STANDARD
    retrieval_k: int = 3
    compress: bool = False          # contextual compression before generation
    max_tokens: int = 400           # generation budget
    use_history: bool = True        # include conversation history in the prompt

    # Clarification policy — if True, the scope-clarification gate is never raised
    # for this intent (an agent handles it, or retrieval can answer broad scope).
    never_clarify: bool = True


# ---------------------------------------------------------------------------
# The registry — order = classifier routing priority (first match wins).
# ---------------------------------------------------------------------------

CAPABILITIES: list[QueryCapability] = [
    QueryCapability(
        name="incident_triage",
        agent="incident_triage",
        max_tokens=350,
        criteria=(
            "user is REPORTING a live facilities problem right now (e.g. \"AC down "
            "floor 3\", \"water leak in basement\", \"elevator stuck\"). Use ONLY for "
            "in-progress incidents needing triage and escalation — NOT for historical "
            "queries."
        ),
    ),
    QueryCapability(
        name="vendor_decision",
        agent="vendor_comparison",
        retrieval_k=4,
        max_tokens=400,
        use_history=False,
        criteria=(
            "user is asking whether THEY should RENEW, SWITCH, or NEGOTIATE their OWN "
            "ACTIVE contract with a named vendor. MUST contain first-person language: "
            "\"should we renew\", \"should I switch us from\", \"is our current deal "
            "competitive\", \"do we want to continue with\". The vendor referenced must "
            "be one we currently have an active contract with. DO NOT use for: "
            "market-benchmark comparisons, analysing competitor alternatives, evaluating "
            "third-party options that are not our live contracts, or any query that lacks "
            "an explicit first-person renewal/switch/negotiate decision framing."
        ),
    ),
    QueryCapability(
        name="portfolio_overview",
        agent="portfolio_overview",
        criteria=(
            "user wants a LIST or REGISTRY of all current vendors, modules, or active "
            "contracts without asking for costs or a spend summary (e.g. \"what vendors "
            "do we have\", \"list all modules under contract\", \"show all active AMC "
            "agreements\", \"who are our FM vendors\", \"what systems are covered by "
            "contracts\", \"give me an overview of all our agreements\"). Covers the "
            "entire portfolio. DO NOT use for: cost/budget questions (use "
            "budget_analysis), single-vendor lookups (use vendor), comparisons (use "
            "comparison)."
        ),
    ),
    QueryCapability(
        name="budget_analysis",
        agent="budget_analysis",
        criteria=(
            "user wants an AGGREGATED spend summary across the ENTIRE PORTFOLIO of "
            "contracts (e.g. \"total AMC spend across all vendors\", \"complete 2026 "
            "facilities budget breakdown\", \"how much are we spending on all systems "
            "combined\"). The query MUST ask for totals or breakdowns that span multiple "
            "separate vendor contracts. DO NOT use for: single-vendor cost queries, "
            "individual contract arithmetic, budget variance on one contract, or any "
            "query where the key figures are already provided in the user's message."
        ),
    ),
    QueryCapability(
        name="vendor",
        retrieval=RETRIEVAL_ENTITY,
        retrieval_k=4,
        max_tokens=380,
        criteria=(
            "asking about the details of ONE specific named vendor's contract (terms, "
            "SLA, scope, fees, expiry). Use when the answer comes from reading that one "
            "contract. NOT for comparisons or decisions. DO NOT use when the user is "
            "asking to write, draft, compose, or prepare a document (email, memo, "
            "letter, report) about the vendor — that is a draft request (use draft)."
        ),
    ),
    QueryCapability(
        name="comparison",
        retrieval=RETRIEVAL_ENTITY,
        retrieval_k=6,
        max_tokens=400,
        criteria=(
            "comparing two or more vendors, contract options, or market alternatives "
            "side by side (e.g. \"compare ArcticAir vs Climate Prime Care\", \"how do "
            "these three options stack up\", \"which alternative is best value\", "
            "\"evaluate these competitor options\"). Use this for ALL multi-vendor "
            "analysis that does NOT have an explicit first-person "
            "renewal/switch/negotiate decision framing. Also use for single-vendor "
            "budget-variance arithmetic (e.g. \"if we switched to X, how much more would "
            "we pay\")."
        ),
    ),
    QueryCapability(
        name="draft",
        retrieval_k=3,
        max_tokens=400,
        criteria=(
            "requesting a document (email, memo, report, alert, letter, template). This "
            "takes PRECEDENCE whenever the query is an explicit instruction to WRITE, "
            "DRAFT, COMPOSE, or PREPARE such a document — even if it names a specific "
            "vendor, contract, or renewal (e.g. \"draft an email to Apex about the "
            "renewal\", \"write a memo on the HVAC contract\"). The user wants the "
            "document produced, not a lookup or comparison."
        ),
    ),
    QueryCapability(
        name="checklist",
        retrieval_k=3,
        max_tokens=300,
        criteria=(
            "requesting an inspection checklist, step-by-step procedure, maintenance "
            "schedule, or ordered task list."
        ),
    ),
    QueryCapability(
        name="factual",
        retrieval_k=3,
        max_tokens=260,
        never_clarify=False,
        criteria=(
            "asking for a specific fact, SOP, procedure, explanation, or lookup. Default "
            "for single-vendor questions that don't fit the vendor type format."
        ),
    ),
    QueryCapability(
        name="general",
        retrieval_k=3,
        max_tokens=280,
        never_clarify=False,
        criteria=(
            "broad best-practices, FM standards, or open-ended knowledge question "
            "without a specific document or vendor to look up."
        ),
    ),
]

# The intent every unrecognised / fallback query resolves to.
DEFAULT_CAPABILITY_NAME = "general"

_BY_NAME: dict[str, QueryCapability] = {c.name: c for c in CAPABILITIES}


def get_capability(name: str | None) -> QueryCapability:
    """Return the capability for an intent name, falling back to the default."""
    return _BY_NAME.get(name or "", _BY_NAME[DEFAULT_CAPABILITY_NAME])


def capability_names() -> list[str]:
    return [c.name for c in CAPABILITIES]


def never_clarify_names() -> set[str]:
    return {c.name for c in CAPABILITIES if c.never_clarify}


def classifier_type_enum() -> str:
    """Render the `"type": one of ...` enum line for the classifier prompt."""
    return " | ".join(f'"{c.name}"' for c in CAPABILITIES)


def classifier_type_block() -> str:
    """Render the ordered TYPE SELECTION criteria block for the classifier prompt.

    Produces the same `* name — criteria` bullet layout the prompt used when the
    type list was hardcoded, but sourced from the registry so it can never drift
    out of sync with routing behaviour.
    """
    lines = []
    for c in CAPABILITIES:
        lines.append(f"  * {c.name} — {c.criteria}")
    return "\n\n".join(lines)
