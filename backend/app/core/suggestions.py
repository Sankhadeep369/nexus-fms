"""Curated quick-start questions for the UI's suggestion chips and `/` picker.

`scripts/pregenerate_suggestions.py` warms the response cache for each of these
(in "simple" mode) so picking one of them answers instantly instead of waiting
on a fresh CPU generation.
"""

SUGGESTED_QUESTIONS: list[str] = [
    "What should I check weekly for the chiller plant?",
    "Summarize this month's compliance checklist.",
    "Compare vendor terms for the HVAC contract.",
    "Draft a memo on an upcoming AMC renewal.",
    "What's a typical fire safety NOC drill checklist?",
    "Explain the standard preventive maintenance schedule for HVAC systems.",
    "What documentation is needed for an electrical certificate renewal?",
    "What are typical SLA response times for plumbing emergencies?",
    "Summarize the housekeeping SOP for common areas.",
    "Outline the steps for onboarding a new facilities vendor.",
    "Draft an email reminding a vendor about an upcoming contract renewal.",
    "What PPE is required for electrical maintenance work?",
    "How are ANPR barriers typically maintained in parking facilities?",
    "What should be included in a monthly energy audit report?",
    "List common causes of CCTV downtime and how to fix them.",
    "What's a typical emergency evacuation drill checklist?",
    "Summarize best practices for waste disposal compliance.",
    "Which network/BMS components need regular license renewals?",
    "Draft a short incident report template for a security breach.",
    "What's included in a quarterly fire extinguisher inspection?",
]
