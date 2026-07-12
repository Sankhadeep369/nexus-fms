"""Fast query triage — keep cheap edge cases off the slow fine-tuned SLM.

Layer A (pre_filter): a deterministic, instant filter for greetings, capability/
"what can you do" questions, adversarial/prompt-injection attempts, and empty or
gibberish input. These are answered from templates and never reach Groq or the
SLM, so a "hi" costs ~0ms instead of a multi-minute generation.

Layer B (compose_decline): builds an honest "decline + best-guess offer" reply for
queries the enriched classifier flags as out-of-scope, an action it can't perform,
or dependent on data NEXUS doesn't hold.

Both layers exist to preserve latency: no edge case here needs the fine-tuned
model, so none of them incur an SLM call.
"""

from __future__ import annotations

import re

_CAPABILITY_CARD = (
    "**I'm NEXUS — your facilities-management contract assistant.** I answer "
    "questions about your active FM contracts. For example:\n\n"
    "- **Contracts & vendors** — \"What does our HVAC contract with Apex cover?\"\n"
    "- **Costs & budget** — \"What's our total annual facilities spend?\"\n"
    "- **Renewals & timing** — \"How many days until the lift contract renews?\"\n"
    "- **Compare & decide** — \"Should we renew with Apex or look at alternatives?\"\n"
    "- **Report an incident** — \"The AC is down on floor 3\"\n"
    "- **Draft documents** — \"Write a renewal reminder email for Apex\"\n\n"
    "What would you like to know?"
)

_GREETING_REPLY = (
    "Hi! I'm NEXUS, your facilities-management contract assistant. I can help with "
    "contracts, costs, renewals, vendor comparisons, incidents, and drafting "
    "documents. What would you like to know?"
)

_EMPTY_REPLY = (
    "I didn't quite catch a question there. I can help with your FM contracts — try "
    "asking about costs, a renewal date, a specific vendor, or an SLA."
)

_ADVERSARIAL_REPLY = (
    "I can only help with facilities-management contract questions. What would you "
    "like to know about your contracts, costs, or renewals?"
)

# Anchored to the WHOLE query so these never catch a real question that merely
# contains the word (e.g. "help me understand the HVAC contract" is not "help").
_GREETING = re.compile(
    r"^\s*(hi+|hey+|hello+|yo|howdy|greetings|sup|"
    r"good\s+(morning|afternoon|evening|day)|what'?s\s+up|how'?s\s+it\s+going)"
    r"[\s!.?,]*$",
    re.IGNORECASE,
)
_THANKS = re.compile(
    r"^\s*(thanks?|thank\s+you|thx|ty|cheers|much\s+appreciated|ok(ay)?|got\s+it|"
    r"cool|nice|great|awesome|perfect|bye|goodbye)[\s!.?,]*$",
    re.IGNORECASE,
)
_META = re.compile(
    r"^\s*(help|menu|options|"
    r"(what|which)\s+can\s+(you|i|it)\s+(do|help|ask|answer)[\w\s]*|"
    r"what\s+do\s+you\s+(do|know|offer)|what\s+(is|are)\s+(this|you|your\s+capabilities)|"
    r"how\s+(do|does)\s+(this|it|you)\s+work|who\s+are\s+you|are\s+you\s+(an?\s+)?(ai|bot|real|human))"
    r"[\s!.?,]*$",
    re.IGNORECASE,
)
_ADVERSARIAL = re.compile(
    r"ignore\s+(the\s+|your\s+|all\s+|previous\s+)?(instruction|prompt|rule)|"
    r"disregard\s+(the|your|all|previous)|you\s+are\s+now\b|pretend\s+(you\s+are|to\s+be)|"
    r"jailbreak|reveal\s+your\s+(prompt|instruction|system)|(system|your)\s+prompt\b|"
    r"act\s+as\s+(a|an|if)|roleplay\s+as",
    re.IGNORECASE,
)
# Imperative verbs for actions NEXUS cannot perform (it is read-only). Deterministic
# backstop to the classifier's action_request signal.
_ACTION = re.compile(
    r"^\s*(book|schedule|re-?schedule|send|e-?mail|call|phone|order|arrange|set\s?up|"
    r"dispatch|deploy|pay|sign|cancel\s+(the|our|my)|renew\s+(the|our|my)|"
    r"terminate\s+(the|our|my))\b",
    re.IGNORECASE,
)


def is_action_request(query: str) -> bool:
    """Deterministic detection of an imperative action NEXUS can't perform
    (book/schedule/send/renew-the/cancel-the …), independent of the classifier."""
    return bool(_ACTION.match((query or "").strip()))


def pre_filter(query: str) -> tuple[str, str] | None:
    """Return (kind, canned_answer) for an instantly-handleable edge case, else None.

    kind is one of: empty | adversarial | greeting | capability | gibberish.
    """
    q = (query or "").strip()
    if len(q) < 2 or not re.search(r"[a-zA-Z0-9]", q):
        return ("empty", _EMPTY_REPLY)
    if _ADVERSARIAL.search(q):
        return ("adversarial", _ADVERSARIAL_REPLY)
    if _META.match(q):
        return ("capability", _CAPABILITY_CARD)
    if _GREETING.match(q) or _THANKS.match(q):
        return ("greeting", _GREETING_REPLY)
    # Gibberish: a single long token dominated by consonants (keyboard mash like
    # "asdfgh", "qwerty"). Length >= 6 avoids catching abbreviations like "hvac".
    if len(q.split()) == 1 and len(q) >= 6:
        vowels = sum(1 for c in q.lower() if c in "aeiou")
        if vowels / len(q) < 0.25:
            return ("gibberish", _EMPTY_REPLY)
    return None


def compose_decline(action_request: bool, missing_data: str, suggested_question: str) -> str:
    """Layer B: honest decline for out-of-scope / action / missing-data queries,
    always ending with the single closest in-scope question the user could ask."""
    sq = (suggested_question or "").strip().rstrip("?")
    offer = (
        f" Did you mean: \"{sq}?\""
        if sq
        else " For example, you could ask what we spend on HVAC, or when a contract renews."
    )
    if action_request:
        return (
            "I can't take actions like booking, scheduling, sending, or signing on "
            "your behalf — I'm a read-only contract assistant. I can look up the "
            "details or draft the text for you, though." + offer
        )
    if missing_data:
        return (
            f"That relies on {missing_data}, which isn't part of the contract data I "
            "have on file." + offer
        )
    return (
        "I'm focused on your facilities-management contracts, so I can't help with "
        "that." + offer
    )
