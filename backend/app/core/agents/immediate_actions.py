"""Immediate on-site safety actions for a live incident.

Answers "what do we do RIGHT NOW / before the vendor arrives?" with a safety-first
action checklist — never vendor/SLA/contract content. This is deliberately separate
from the Incident Triage agent (which handles vendor escalation): a *report* of a
hazard routes to triage, but a *"what do we do?"* question routes here.

Hybrid generation: curated, instant checklists for the common high-risk hazards,
with a Groq safety-prompt fallback for anything else. No SLM generation, so this is
a fast lane that never touches the main pipeline's latency.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("nexus.immediate_actions")

# ---------------------------------------------------------------------------
# Curated, safety-vetted action checklists. Keyed by hazard.
# ---------------------------------------------------------------------------
_CURATED: dict[str, tuple[str, list[str]]] = {
    "lift_entrapment": (
        "People trapped in a lift",
        [
            "**Stay calm and reassure the people inside** — a stalled lift car is designed to stay put; there is no danger of it falling.",
            "Tell them to **press and hold the alarm/emergency button** in the car, and use the intercom/phone if fitted, to reach the control room.",
            "**Do not try to force the doors open** or climb out, and tell occupants not to — wait for trained rescuers.",
            "Keep everyone clear of the doors; note the car's position/floor if visible.",
            "Keep talking to the occupants so they know help is on the way.",
            "Call building **security/facilities control** and the **lift emergency line** immediately.",
            "If anyone inside is unwell (breathing difficulty, chest pain, panic, a medical condition), treat it as a **medical emergency** and call emergency services.",
            "**Do not attempt a manual rescue** (winding/brake release) unless you are trained and authorised — it must be done by a competent lift technician.",
        ],
    ),
    "entrapment": (
        "A person stuck behind a malfunctioning door",
        [
            "Stay with the person and **keep them calm** — reassure them help is on the way.",
            "**Check for a manual release or override** — accessible/powered doors usually have an emergency release or can be unlocked from the outside; try it gently.",
            "Make sure the person has **air and is comfortable**, and keep talking to them.",
            "If the facility has an **emergency assist alarm / pull-cord** (common in accessible washrooms), confirm it has been triggered.",
            "If the person is **unwell, panicking, elderly, disabled, or otherwise at risk**, treat it as urgent and **call emergency services**.",
            "**Do not force the door** in a way that could injure the person or jam it further.",
            "Call building **security/facilities control** and note the exact door/location for the technician.",
        ],
    ),
    "fire": (
        "Fire or smoke",
        [
            "**Raise the alarm** — activate the nearest fire call point.",
            "**Evacuate** by the nearest safe exit and **do not use lifts**; help anyone who needs assistance.",
            "**Call the fire brigade** (your local emergency number).",
            "Close doors behind you to slow the spread — do not lock them.",
            "Only tackle a small fire with the correct extinguisher **if you are trained and it is safe** — never put yourself at risk.",
            "If there is smoke, **keep low**; check doors for heat with the back of your hand before opening.",
            "Go to the **assembly point**, do a head-count, and **do not re-enter** until the fire service says it is safe.",
        ],
    ),
    "gas": (
        "Gas leak or smell of gas",
        [
            "**Do not operate any electrical switches, lights, or appliances** and use **no naked flames** — a spark can ignite the gas.",
            "**Ventilate** the area — open doors and windows if you can do so quickly.",
            "**Evacuate** the area and keep others well away.",
            "Turn off the gas supply at the meter/isolation valve **only if it is safe to reach**.",
            "From a **safe location outside**, call the **gas emergency line** and building security.",
            "**Do not re-enter** until the area has been declared safe.",
        ],
    ),
    "flood": (
        "Flooding or major water leak",
        [
            "If safe, **shut off the water** at the nearest isolation valve or stopcock.",
            "Keep people **away from the affected area**, especially near any electrical equipment or sockets.",
            "If water is reaching electrics, **switch off the power** to that area at the distribution board — only if you can do so safely and while dry.",
            "**Contain the spread** with bunds, absorbent materials, or barriers; lift/protect equipment and documents.",
            "Note the source if visible so the technician can find it quickly.",
        ],
    ),
    "power": (
        "Power outage",
        [
            "Stay calm; use **torches, not candles or naked flames**.",
            "Check whether it is a **local trip** (reset the breaker only if it is safe and obvious) or a wider outage.",
            "Confirm **emergency lighting and exit signs** are working; guide people if areas are dark.",
            "**Check the lifts** for anyone trapped (treat as a lift entrapment) and confirm safety-critical systems (fire alarm, UPS-backed equipment) are up.",
            "**Turn off or unplug** sensitive equipment to protect it from a surge when power is restored.",
        ],
    ),
    "electrical": (
        "Electrical hazard (shock, sparks, or burning smell)",
        [
            "**Do not touch** anyone who is in contact with a live source — **switch off the power first** at the isolator or distribution board.",
            "**Isolate** the affected circuit or equipment if you can do so safely.",
            "Keep yourself and others **well clear** of the hazard.",
            "For an electrical fire, use a **CO2 or dry-powder extinguisher — never water**.",
            "If someone is injured or unconscious, **call emergency services** and give first aid only if trained.",
            "**Do not use the equipment** again until it has been inspected by an electrician.",
        ],
    ),
    "medical": (
        "Medical emergency or injury",
        [
            "**Call emergency services immediately** and give a clear location.",
            "Send someone to **guide responders in** and to fetch the **first-aid kit / AED**.",
            "If trained, **give first aid**; do not move a seriously injured person unless they are in immediate danger.",
            "Keep the person **calm, warm, and reassured**, and monitor their breathing.",
            "Clear the area and note what happened for the responders.",
        ],
    ),
    "general": (
        "General incident response",
        [
            "**Make people safe first** — move anyone at risk to a safe area.",
            "**Isolate the hazard** if you can do so safely (power, water, or gas as appropriate).",
            "Call **building security/facilities control**, and **emergency services** if there is any risk to life.",
            "Keep others **away from the affected area**.",
            "Note **what happened, when, and where** for the responders and the technician.",
            "**Do not attempt repairs** beyond making the area safe — wait for the technician.",
        ],
    ),
}

_ESCALATE_NOTE = (
    "Once everyone is safe and the area is secured, log the incident and escalate to the responsible maintenance vendor."
)

# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

# Hazard keyword patterns -> curated key. Order matters (more specific first).
_HAZARD_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "lift_entrapment",
        re.compile(
            r"(lift|elevator)s?\b.{0,40}\b(stuck|trapped|stranded|stopped|not\s+moving|jammed|inside)"
            r"|\b(stuck|trapped|stranded|passengers?|people)\b.{0,40}\b(lift|elevator)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "entrapment",
        re.compile(
            r"\b(person|someone|somebody|man|woman|child|kid|user|occupant|patient|visitor|staff|guest|colleague|resident)\b.{0,40}\b(stuck|trapped|locked\s+in|jammed\s+in)"
            r"|\b(stuck|trapped|locked|jammed)\b.{0,40}\b(behind|inside|in)\b.{0,25}\b(door|washroom|restroom|toilet|bathroom|room|cabin|cubicle|stall|office|chamber)"
            r"|\b(door|washroom|restroom|toilet|bathroom|cubicle|gate)\b.{0,25}\b(malfunction\w*|jam\w*|stuck|won'?t\s+open|not\s+open\w*|fault\w*)\b.{0,45}\b(person|someone|somebody|stuck|trapped|inside)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    ("gas", re.compile(r"\b(gas\s+leak|smell(?:l|ing)?\s+of\s+gas|gas\s+smell|lpg\s+leak)\b", re.IGNORECASE)),
    ("fire", re.compile(r"\b(fire|smoke|flames?|burning\s+smell)\b", re.IGNORECASE)),
    (
        "flood",
        re.compile(r"\b(flood(?:ing|ed)?|burst\s+pipe|water\s+leak|major\s+leak|water\s+ingress|overflow(?:ing)?|inundat)\b", re.IGNORECASE),
    ),
    (
        "power",
        re.compile(r"\b(power\s+(?:cut|outage|failure|down|loss|off)|no\s+power|black\s?out|electricity\s+(?:out|down|failure|cut))\b", re.IGNORECASE),
    ),
    (
        "electrical",
        re.compile(r"\b(electric\s+shock|electrocut\w*|sparks?|short\s+circuit|exposed\s+wire|live\s+wire|burning\s+smell\s+from\s+(?:the\s+)?(?:socket|panel|wiring|wire))\b", re.IGNORECASE),
    ),
    (
        "medical",
        re.compile(r"\b(injur\w+|unconscious|collapsed|not\s+breathing|bleeding|heart\s+attack|first\s+aid|fainted|seizure|choking)\b", re.IGNORECASE),
    ),
]

# "What do we do?" style intent.
_ACTION_INTENT = re.compile(
    r"\bwhat\s+(should|do|can|must|to|are|is)\b[\w\s]{0,25}\b(do|action|actions|steps|measures|next|first)\b"
    r"|\bwhat\s+(immediate\s+)?(action|actions|steps|measures)\b"
    r"|\bwhat\s+to\s+do\b"
    r"|\b(action|actions|steps|measures)\s+(to\s+(take|do)|before|while|until|needed|required)\b"
    r"|\bhow\s+(do|should|to|can)\b[\w\s]{0,20}\b(respond|react|handle|deal|proceed|stay\s+safe)\b"
    r"|\bis\s+it\s+safe\b"
    r"|\bwhat\s+should\s+(occupants|people|staff|passengers|we|i)\b",
    re.IGNORECASE,
)

# Marks a query as being about a live/emergent situation (vs a general how-to).
_INCIDENT_CONTEXT = re.compile(
    r"\b(before|until|till)\b[\w\s]{0,25}\b(vendor|technician|engineer|help|team|someone|maintenance|service|fitter|electrician|plumber)\b[\w\s]{0,12}\b(arrive|arrives|arriving|come|comes|coming|get|gets|reach|reaches)"
    r"|\bwhile\s+(we|they|you|i)\s+(wait|await)\b"
    r"|\b(meanwhile|in\s+the\s+meantime|right\s+now|straight\s+away)\b"
    r"|\b(trapped|stuck|stranded)\b",
    re.IGNORECASE,
)

# Clearly-not-an-incident topics; keep contract/renewal/finance follow-ups out of
# this fast path even when an incident is in the recent history.
_NON_INCIDENT = re.compile(
    r"\b(renew\w*|renewal|contract|amc|agreement|invoice|budget|cost|price|pricing|payment|onboard\w*|compare|comparison|expire\w*|expiry|when\s+does|sla\s+terms)\b",
    re.IGNORECASE,
)

# Map an incident-triage domain (contracted system) -> hazard, for the report path.
_DOMAIN_HAZARD: list[tuple[str, tuple[str, ...]]] = [
    ("lift_entrapment", ("lift", "elevator", "escalator")),
    ("fire", ("fire", "life safety", "extinguisher")),
    ("electrical", ("electric", "generator", "ups")),
    ("flood", ("plumb", "water")),
]


def detect_hazard(text: str) -> str | None:
    for key, pat in _HAZARD_PATTERNS:
        if pat.search(text or ""):
            return key
    return None


def _hazard_from_history(history: list[dict] | None) -> str | None:
    for msg in reversed((history or [])[-6:]):
        hz = detect_hazard(msg.get("content", ""))
        if hz:
            return hz
    return None


# Words that mark a message as describing an incident (broader than the hazard
# patterns — used to pull the original incident description as context).
_INCIDENT_HINT = re.compile(
    r"\b(stuck|trapped|locked|jammed|malfunction\w*|broken|not\s+working|won'?t\s+open|"
    r"leak\w*|flood\w*|fire|smoke|gas|outage|black\s?out|power\s+(?:cut|down|failure|loss)|"
    r"shock|spark\w*|injur\w*|unconscious|collapsed|fault\w*|breakdown|emergency|fail\w*|down)\b",
    re.IGNORECASE,
)


def incident_context_from_history(history: list[dict] | None) -> str:
    """Pull the original incident description from the conversation so a follow-up
    ("what do we do now?") can be answered about the ACTUAL incident, not generically.
    Prefers the user's own report."""
    hist = (history or [])[-8:]
    for want_user in (True, False):
        for msg in reversed(hist):
            if want_user and msg.get("role") != "user":
                continue
            c = (msg.get("content") or "").strip()
            if c and _INCIDENT_HINT.search(c):
                return c[:400]
    return ""


def detect_incident_action(query: str, history: list[dict] | None = None) -> str | None:
    """Return a hazard key if `query` is a "what do we do about this incident?"
    question (so it should get safety actions, not vendor content), else None.

    A query that *describes* a hazard without asking what to do (a report) returns
    None — those stay with the Incident Triage agent.
    """
    if _NON_INCIDENT.search(query):
        return None
    if not _ACTION_INTENT.search(query):
        return None
    hz = detect_hazard(query)
    if hz:
        return hz
    # Action-intent but no hazard named: only treat as an incident follow-up when
    # there's clear live-incident context or a recent incident in the conversation.
    if _INCIDENT_CONTEXT.search(query) or _hazard_from_history(history):
        return _hazard_from_history(history) or "general"
    return None


def hazard_for_incident(text: str, domain: str | None) -> str:
    """Best hazard for an incident REPORT (used to attach actions to triage output)."""
    hz = detect_hazard(text)
    if hz:
        return hz
    d = re.sub(r"[^a-z]+", " ", (domain or "").lower())
    for key, tokens in _DOMAIN_HAZARD:
        if any(t in d for t in tokens):
            return key
    return "general"


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def curated_for(hazard: str | None) -> str:
    title, actions = _CURATED.get(hazard or "general", _CURATED["general"])
    bullets = "\n".join(f"- {a}" for a in actions)
    return (
        f"## Immediate Actions — {title}\n\n"
        f"> Do these now, before the technician/vendor arrives. "
        f"If there is any risk to life, call your emergency services first.\n\n"
        f"{bullets}\n- {_ESCALATE_NOTE}"
    )


_SAFETY_PROMPT = """\
A facilities incident is happening now and the user is asking what to do about it.
{context_block}List the IMMEDIATE on-site safety actions the people there should take
RIGHT NOW, before any technician or vendor arrives. Your actions MUST be specific to
THIS incident — do not give generic fire-evacuation steps unless the incident is a fire.

Rules:
- Focus ONLY on immediate occupant/staff safety and containment for this specific incident.
- Do NOT mention vendors, contracts, SLAs, escalation emails, or who is responsible.
- Put life safety first; if there is any risk to life, tell them to call emergency services.
- Be specific, practical, and brief — short bullet points, safest action first.
- Never advise anything unsafe or anything that needs trained/authorised personnel; instead say to wait for trained help.

User's question: {query}

Reply with a short markdown answer that begins with a heading "## Immediate Actions" followed by a bullet list."""


def _groq_safety(query: str, context: str, api_key: str, model: str) -> str | None:
    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        context_block = f"The incident being dealt with: {context}\n" if context else ""
        prompt = _SAFETY_PROMPT.format(context_block=context_block, query=query[:500])
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=380,
            temperature=0.2,
        )
        return (r.choices[0].message.content or "").strip() or None
    except Exception as exc:
        logger.warning("immediate-actions Groq fallback failed (%s)", exc)
        return None


def build_immediate_actions(
    query: str,
    hazard: str | None,
    api_key: str | None,
    model: str | None,
    allow_llm: bool = True,
    context: str = "",
) -> str:
    """Curated checklist for a known hazard (instant); otherwise a Groq safety answer
    grounded in the incident `context` (hybrid), falling back to the generic curated
    checklist if the LLM is unavailable."""
    if hazard in _CURATED and hazard != "general":
        return curated_for(hazard)
    if allow_llm and api_key:
        llm = _groq_safety(query, context, api_key, model or "")
        if llm:
            return llm
    return curated_for("general")
