"""Curated quick-start questions for the UI's suggestion chips and `/` picker.

`scripts/pregenerate_suggestions.py` / `scripts/seed_suggestion_cache.py` warm the
response cache for each of these (in "simple" mode) so picking one answers instantly
instead of waiting on a fresh CPU generation.

Questions are grouped by category purely for the UI's command palette; the flat
`SUGGESTED_QUESTIONS` list remains the source of truth for cache seeding, so the
category grouping never affects backend behaviour or performance.
"""

# Ordered category -> questions. Order here is the order the palette renders in.
SUGGESTIONS_BY_CATEGORY: dict[str, list[str]] = {
    "HVAC & Chiller": [
        "What should I check weekly for the chiller plant?",
        "Explain the standard preventive maintenance schedule for HVAC systems.",
        "What are the ideal temperature and humidity setpoints for an office building?",
        "What water treatment parameters should I monitor for cooling towers?",
    ],
    "Compliance & Safety": [
        "Summarize this month's compliance checklist.",
        "What's a typical fire safety NOC drill checklist?",
        "What documentation is needed for an electrical certificate renewal?",
        "What PPE is required for electrical maintenance work?",
        "What's a typical emergency evacuation drill checklist?",
        "What's included in a quarterly fire extinguisher inspection?",
        "What's the checklist for an annual lift/elevator inspection?",
        "What's the standard procedure for handling a fire alarm false trigger?",
    ],
    "Vendors & Contracts": [
        "Compare vendor terms for the HVAC contract.",
        "What are typical SLA response times for plumbing emergencies?",
        "Outline the steps for onboarding a new facilities vendor.",
        "What's the escalation path when a vendor repeatedly misses its SLA?",
        "How do I calculate the AMC cost per square foot?",
    ],
    "Drafting & Templates": [
        "Draft a memo on an upcoming AMC renewal.",
        "Draft an email reminding a vendor about an upcoming contract renewal.",
        "Draft a short incident report template for a security breach.",
        "Draft a work order for AC repair on the third floor.",
        "Draft a tenant notice about scheduled water tank cleaning.",
    ],
    "Operations & SOPs": [
        "Summarize the housekeeping SOP for common areas.",
        "Which network/BMS components need regular license renewals?",
        "How often should diesel generator (DG) sets be tested and serviced?",
        "What should a facility shift handover report include?",
    ],
    "Security & Surveillance": [
        "How are ANPR barriers typically maintained in parking facilities?",
        "List common causes of CCTV downtime and how to fix them.",
    ],
    "Energy & Sustainability": [
        "What should be included in a monthly energy audit report?",
        "Summarize best practices for waste disposal compliance.",
        "How can I reduce energy consumption during peak load hours?",
        "What should a monthly water consumption report track?",
    ],
}

# Flat list -- the source of truth for cache seeding (unchanged contract).
SUGGESTED_QUESTIONS: list[str] = [
    q for questions in SUGGESTIONS_BY_CATEGORY.values() for q in questions
]

# question -> category, for the UI's grouped palette.
SUGGESTION_CATEGORIES: dict[str, str] = {
    q: category
    for category, questions in SUGGESTIONS_BY_CATEGORY.items()
    for q in questions
}
