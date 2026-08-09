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
            r"\b(person|someone|somebody|man|woman|child|kid|user|occupant|patient|visitor|staff|guest|colleague|resident|lady|gentleman)\b.{0,45}\b(stuck|trapped|locked\s+in|jammed\s+in|confined|shut\s+in|can'?t\s+get\s+out|cannot\s+get\s+out|unable\s+to\s+(?:get\s+out|exit))"
            r"|\b(stuck|trapped|locked|jammed|confined|shut)\b.{0,30}\b(behind|inside|in)\b.{0,25}\b(door|washroom|restroom|toilet|loo|bathroom|room|cabin|cubicle|stall|office|chamber|lavatory)"
            r"|\b(door|washroom|restroom|toilet|loo|bathroom|cubicle|gate|shutter)\b.{0,25}\b(malfunction\w*|jam\w*|stuck|won'?t\s+open|not\s+open\w*|fault\w*|broke\w*)\b.{0,50}\b(person|someone|somebody|stuck|trapped|inside|in\s+there)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    ("gas", re.compile(r"\b(gas\s+leak|leak\w*\s+gas|smell(?:l|ing)?\s+of\s+gas|gas\s+smell|smell\s+gas|lpg\s+leak|gas\s+is\s+leaking)\b", re.IGNORECASE)),
    ("fire", re.compile(r"\b(fire|smoke|flames?|blaze|on\s+fire|something'?s?\s+burning|burning\s+smell)\b", re.IGNORECASE)),
    (
        "flood",
        re.compile(r"\b(flood(?:ing|ed)?|burst\s+pipe|water\s+leak|major\s+leak|water\s+ingress|overflow(?:ing)?|inundat|water\s+everywhere|waterlogged|submerged|gushing\s+water|pipe\s+burst)\b", re.IGNORECASE),
    ),
    (
        "power",
        re.compile(r"\b(power\s+(?:cut|outage|failure|down|loss|off|gone)|no\s+power|no\s+electricity|lost\s+power|black\s?out|electricity\s+(?:out|down|failure|cut|gone)|lights?\s+(?:are\s+)?(?:out|off|gone))\b", re.IGNORECASE),
    ),
    (
        "electrical",
        re.compile(r"\b(electric\w*\s+shock|electrocut\w*|sparks?|sparking|short\s+circuit|exposed\s+wire|live\s+wire|wire\s+sparking|burning\s+smell\s+(?:from|near|at)\s+(?:the\s+)?(?:socket|plug|panel|board|wiring|wire|switch))\b", re.IGNORECASE),
    ),
    (
        "medical",
        re.compile(r"\b(injur\w+|hurt|unconscious|collapsed|passed\s+out|not\s+breathing|breathing\s+difficult\w*|can'?t\s+breathe|bleeding|heart\s+attack|chest\s+pain|first\s+aid|fainted|faint\w*|seizure|choking|fell\s+(?:down|over|and)|stroke)\b", re.IGNORECASE),
    ),
]

# The families of incident follow-up questions we handle. Kept deliberately broad
# (synonyms / paraphrases) because users phrase "what do we do now?" many ways; the
# actual answer is then produced semantically — a curated hazard checklist, or a
# context-grounded Groq safety answer — so novel wording still gets a relevant reply.
#
# Covered intents (examples):
#   what do we do / what now / what next / what first / what to do
#   what can we|staff|occupants|the user do   •   what (immediate/safety) actions|steps|measures
#   how do we handle|respond|deal with|manage|proceed|cope   •   how do we keep them safe
#   any advice|tips|guidance|suggestions|pointers   •   what do you suggest|recommend|advise
#   what's the procedure|protocol|process|best way|right thing|next step
#   should we <do X>   •   can we <do X>   •   is it safe|ok|advisable to <X>
#   who do we call|contact|inform|notify   •   what should we tell them   •   what precautions
#   meanwhile / in the meantime / until help arrives / while we wait / right now
_ACTION_INTENT = re.compile(
    r"\bwhat\s+(?:should|shall|do|does|can|could|must|are|is|to)\b[\w\s'’]{0,30}\b(do|action|actions|steps|measures|next|first|now|handle|respond|precaution|precautions)\b"
    r"|\bwhat\s+(?:to\s+do|now|next|first)\b"
    r"|\bwhat\s+(?:immediate\s+|safety\s+)?(action|actions|steps|measures|precautions)\b"
    r"|\bwhat\s+can\s+(?:we|i|they|you|the\s+\w+|staff|occupants?|people|users?|passengers?|residents?)\b[\w\s'’]{0,20}\bdo\b"
    r"|\b(?:action|actions|steps|measures)\s+(?:to\s+(?:take|do)|before|while|until|needed|required|now)\b"
    r"|\bhow\s+(?:do|should|to|can|would|might)\b[\w\s'’]{0,30}\b(handle|respond|react|deal|proceed|manage|cope|help|keep\s+\w+\s+safe|stay\s+safe)\b"
    r"|\b(?:any|some|got\s+any|need\s+(?:any\s+)?)\s*(advice|tips|guidance|suggestions?|recommendations?|pointers?|precautions?)\b"
    r"|\bwhat\s+(?:do|would|can)\s+you\s+(suggest|recommend|advise)\b"
    r"|\bwhat['’]?s?\s+(?:the\s+)?(procedure|protocol|process|best\s+way|right\s+thing|next\s+step)\b"
    r"|\b(?:should|shall|can|could|ought)\s+(?:we|i|they)\s+\w+"
    r"|\bis\s+it\s+(safe|ok|okay|advisable|wise|alright|all\s+right)\b"
    r"|\bwho\s+(?:do|should|to|can)\s+(?:we|i)?\s*(call|contact|inform|notify|reach|ring)\b"
    r"|\bwhat\s+should\s+(?:we|i|occupants?|people|staff|passengers?|residents?|the\s+\w+)\b"
    r"|\bwhat\s+(precautions?|safety\s+measures?)\b",
    re.IGNORECASE,
)

# Marks a query as being about a live/emergent situation (vs a general how-to).
_INCIDENT_CONTEXT = re.compile(
    r"\b(before|until|till|whilst|while)\b[\w\s'’]{0,30}\b(vendor|technician|engineer|contractor|help|rescue|team|someone|maintenance|service|fitter|electrician|plumber|fire\s+brigade|ambulance|paramedics?|security|guard)\b[\w\s'’]{0,15}\b(arrive|arrives|arriving|come|comes|coming|get|gets|reach|reaches|here|turn\s+up)"
    r"|\bwhile\s+(we|they|you|i)\s+(wait|await|hold)\b"
    r"|\b(meanwhile|in\s+the\s+meantime|right\s+now|straight\s+away|immediately|on\s+the\s+spot|on[-\s]?site)\b"
    r"|\b(trapped|stuck|stranded|confined)\b",
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
    r"\b(stuck|trapped|locked|jammed|confined|can'?t\s+get\s+out|won'?t\s+open|malfunction\w*|"
    r"broken|broke\s+down|not\s+working|out\s+of\s+order|leak\w*|flood\w*|water\s+everywhere|"
    r"fire|smoke|blaze|gas|outage|black\s?out|no\s+power|no\s+electricity|lost\s+power|"
    r"power\s+(?:cut|down|failure|loss|gone)|lights?\s+(?:out|off)|shock|spark\w*|burning\s+smell|"
    r"injur\w*|hurt|unconscious|collapsed|fainted|bleeding|choking|chest\s+pain|fault\w*|"
    r"breakdown|emergency|fail\w*|down|tripped|not\s+responding)\b",
    re.IGNORECASE,
)

# A prior assistant turn that produced an incident triage / immediate-actions answer
# is a strong, vocabulary-independent signal that we're in an incident context — so a
# follow-up in ANY wording afterwards is treated as an incident follow-up.
_INCIDENT_MARKER = re.compile(
    r"##\s*Incident\s+Summary|##\s*Escalation\s+Email|##\s*Immediate\s+Actions|Responsible\s+vendor|SLA\s+status",
    re.IGNORECASE,
)


def _recent_incident_in_history(history: list[dict] | None) -> bool:
    """True if the last few turns are about a live incident, regardless of wording."""
    for msg in reversed((history or [])[-4:]):
        c = msg.get("content") or ""
        if _INCIDENT_MARKER.search(c) or detect_hazard(c) or _INCIDENT_HINT.search(c):
            return True
    return False


def incident_context_from_history(history: list[dict] | None) -> str:
    """Pull the original incident description from the conversation so a follow-up
    ("what do we do now?") can be answered about the ACTUAL incident, not generically.
    Prefers a user message that clearly describes an incident, then falls back to the
    most recent user message (almost always the report)."""
    hist = (history or [])[-8:]
    # 1. a user message that clearly describes an incident
    for msg in reversed(hist):
        if msg.get("role") == "user":
            c = (msg.get("content") or "").strip()
            if c and _INCIDENT_HINT.search(c):
                return c[:400]
    # 2. fallback: the most recent user message (the report usually precedes the follow-up)
    for msg in reversed(hist):
        if msg.get("role") == "user":
            c = (msg.get("content") or "").strip()
            if c:
                return c[:400]
    # 3. last resort: any incident-ish message
    for msg in reversed(hist):
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
    # Action-intent but no hazard named: treat as an incident follow-up when there's
    # clear live-incident context in the query, or a recent incident in the chat
    # (the latter is vocabulary-independent — a prior triage answer counts). The
    # hazard is then best-effort from history; anything unmatched falls to "general",
    # which the Groq fallback answers semantically using the incident context.
    if _INCIDENT_CONTEXT.search(query) or _recent_incident_in_history(history):
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
A facilities incident has been reported. Give the practical on-site actions the people \
there should take right now, before a technician/vendor arrives.

Incident: {incident}
{question_line}
How to answer:
- First WORK OUT what this specific incident actually is, then give steps that fit it.
- Where it helps, start with quick diagnosis/observation — e.g. check the source, look \
for visible damage, check the supply/breaker, note whether it's intermittent or total.
- Make the response PROPORTIONATE to the real severity. A minor fault (e.g. a light \
flickering or not working) is NOT a life-threatening emergency — do not give alarmist \
or unrelated advice. Do NOT mention fire extinguishers, evacuation, or calling \
emergency services UNLESS there is a genuine fire, injury, or threat to life.
- Keep occupants safe and contain the problem; isolate power/water/gas only when that \
is clearly warranted and can be done safely.
- Do NOT advise anything that needs trained/authorised personnel — say to wait for them.
- Do NOT mention vendors, contracts, SLAs, or escalation emails.
- Be specific to THIS incident, short bullet points, most useful/safest first.

Reply with a markdown answer beginning with a heading "## Immediate Actions" followed by a short bullet list."""


def _groq_safety(query: str, context: str, api_key: str, model: str) -> str | None:
    try:
        from groq import Groq

        # Bounded retries: under a rate limit, fail fast to the curated fallback
        # rather than stacking long backoff onto the incident response.
        client = Groq(api_key=api_key, max_retries=1)
        incident = context.strip() or query.strip() or "an unspecified facilities incident"
        question_line = f"The user asks: {query.strip()}\n" if query.strip() else ""
        prompt = _SAFETY_PROMPT.format(incident=incident[:600], question_line=question_line)
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=380,
            temperature=0.2,
        )
        return (r.choices[0].message.content or "").strip() or None
    except Exception as exc:
        logger.warning("immediate-actions Groq generation failed (%s)", exc)
        return None


def build_immediate_actions(
    query: str,
    hazard: str | None,
    api_key: str | None,
    model: str | None,
    allow_llm: bool = True,
    context: str = "",
) -> str:
    """LLM-first: understand the actual incident and give proportionate, specific
    actions. Curated checklists are only an OFFLINE fallback (LLM unavailable) — a
    hazard-specific one when the wording clearly indicates a high-risk hazard,
    otherwise the generic one. This avoids forcing every incident into a hardcoded
    (and often over-escalated) bucket."""
    if allow_llm and api_key:
        llm = _groq_safety(query, context, api_key, model or "")
        if llm:
            return llm
    return curated_for(hazard if hazard in _CURATED else "general")
