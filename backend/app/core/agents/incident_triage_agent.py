"""Incident Triage Agent.

User reports a facilities problem in plain language. The agent:
1. Classifies the incident: domain, severity, urgency
2. Identifies the responsible vendor from the corpus (by service category)
3. Retrieves the relevant SLA response time commitment
4. Determines if the SLA window has been breached given the reported duration
5. Drafts an escalation email to the vendor + an internal summary note

All five steps use Groq (fast, grounded in context) — no SLM generation.
Total time: ~3-5 seconds end-to-end.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger("nexus.agent.incident_triage")

# ---------------------------------------------------------------------------
# Step 1: Classify the incident
# ---------------------------------------------------------------------------

_CLASSIFY_PROMPT = """\
Classify this facilities incident report. Extract:
1. domain: one of hvac|electrical|fire_safety|security_cctv|plumbing|civil|lifts|access_control|housekeeping|landscape|waste|bms|parking|general
2. severity: critical|high|medium|low
   - critical: safety risk or business stopping (fire, flood, trapped person, no power)
   - high: affects multiple people or core operations (AC down floor, major leak)
   - medium: single area impact, ongoing but not acute
   - low: minor inconvenience, cosmetic
3. duration_hours: estimated hours the issue has been ongoing (null if not mentioned)
4. summary: one-sentence factual summary of the issue

Incident: {incident}

Return ONLY valid JSON, no other text:
{{"domain": "...", "severity": "...", "duration_hours": null, "summary": "..."}}"""

# ---------------------------------------------------------------------------
# Step 5: Draft escalation email
# ---------------------------------------------------------------------------

_DRAFT_PROMPT = """\
Draft a professional facilities escalation email. Use only the provided facts.

Incident: {summary}
Vendor: {vendor}
Site: {site}
SLA response time: {sla}
Hours since reported: {hours}
SLA status: {sla_status}

Write a complete email (Subject, Greeting, Body, Sign-off) to the vendor.
- If SLA is BREACHED: formal tone, cite the breach, request immediate attendance
- If within SLA: professional but urgent tone, reference the committed response time
- Do not invent any figures, names, or clauses not provided above
- Close as "Facilities Management Team"

Return ONLY the email text, no other commentary."""


@dataclass
class TriageResult:
    domain: str
    severity: str
    duration_hours: float | None
    summary: str
    vendor: str
    site: str
    sla_hours: float | None
    sla_status: str           # "BREACHED" | "AT_RISK" | "WITHIN_SLA" | "UNKNOWN"
    escalation_email: str
    sources: list[str] = field(default_factory=list)
    succeeded: bool = True
    reason: str = "ok"


def _parse_sla_hours(sla_text: str) -> float | None:
    """Extract numeric hours from SLA text like 'Within 2 hours', '24x7', etc."""
    m = re.search(r"within\s+(\d+)\s*hour", sla_text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+)\s*hour", sla_text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    if re.search(r"24.?7|immediately|instant", sla_text, re.IGNORECASE):
        return 0.5
    return None


def _sla_status(duration_hours: float | None, sla_hours: float | None) -> str:
    if duration_hours is None or sla_hours is None:
        return "UNKNOWN"
    if duration_hours >= sla_hours:
        return "BREACHED"
    if duration_hours >= sla_hours * 0.75:
        return "AT_RISK"
    return "WITHIN_SLA"


_DOMAIN_CATEGORY_MAP = {
    "hvac": ["HVAC", "Chiller", "Air Conditioning", "Cooling", "Heating"],
    "electrical": ["Electrical", "Power", "Generator", "UPS"],
    "fire_safety": ["Fire", "Safety", "Suppression", "Sprinkler"],
    "security_cctv": ["CCTV", "Security", "Surveillance", "Access Control", "Guard"],
    "plumbing": ["Plumbing", "Water", "Drainage", "Leak"],
    "civil": ["Civil", "Structural", "Facade", "Waterproof"],
    "lifts": ["Lift", "Elevator", "Escalator"],
    "access_control": ["Access Control", "Door", "Barrier", "Lock"],
    "housekeeping": ["Housekeeping", "Cleaning", "Hygiene"],
    "landscape": ["Landscape", "Groundskeeping", "Garden"],
    "waste": ["Waste", "Disposal", "Garbage"],
    "parking": ["Parking", "ANPR", "Barrier"],
    "bms": ["BMS", "Building Management", "SCADA", "DDC", "Network"],
}


def _find_vendor_for_domain(
    domain: str,
    registry,
    retriever,
) -> tuple[list[dict], str, str]:
    """Find chunks from the current contract matching the incident domain.
    Returns (chunks, vendor_name, site_name)."""
    search_terms = _DOMAIN_CATEGORY_MAP.get(domain, [domain])
    all_chunks = []
    for term in search_terms[:2]:
        docs = [d for d in registry.find_docs(term) if d.startswith("current_contracts/")]
        if docs:
            from app.core.agents.tools import _rank_chunks_in_docs
            chunks = _rank_chunks_in_docs(
                retriever,
                f"{term} SLA response time breakdown attendance",
                "current_contracts/",
                docs,
                k=2,
            )
            all_chunks.extend(chunks)
            if all_chunks:
                break

    # Extract vendor and site from first chunk's source_doc filename
    vendor, site = "Unknown Vendor", "Site"
    if all_chunks:
        fname = all_chunks[0]["source_doc"].split("/")[-1].replace(".txt", "")
        parts = fname.split("_")
        # Filename pattern: NN_VendorName_ServiceType_Site
        if len(parts) >= 3:
            vendor = " ".join(parts[1:-2]).replace("_", " ") if len(parts) > 3 else parts[1]
            site = parts[-1]

    seen = set()
    deduped = []
    for c in all_chunks:
        key = (c["source_doc"], c["section"])
        if key not in seen:
            seen.add(key)
            deduped.append(c)

    return deduped[:3], vendor, site


def run_incident_triage(
    incident: str,
    api_key: str,
    model: str,
    registry,
    retriever,
) -> TriageResult:
    if not api_key:
        return TriageResult(
            domain="general", severity="medium", duration_hours=None,
            summary=incident, vendor="Unknown", site="Site",
            sla_hours=None, sla_status="UNKNOWN", escalation_email="",
            succeeded=False, reason="no Groq API key configured",
        )
    try:
        from groq import Groq

        client = Groq(api_key=api_key)

        # Step 1: classify
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _CLASSIFY_PROMPT.format(incident=incident[:800])}],
            max_tokens=150, temperature=0.0,
        )
        raw = r.choices[0].message.content.strip()
        clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)
        m = re.search(r"\{[\s\S]+\}", clean)
        meta = json.loads(m.group(), strict=False) if m else {}

        domain = meta.get("domain", "general")
        severity = meta.get("severity", "medium")
        duration_hours = meta.get("duration_hours")
        summary = meta.get("summary", incident[:120])
        logger.info("incident classified: domain=%s severity=%s duration=%.1fh",
                    domain, severity, duration_hours or 0)

        # Step 2: find responsible vendor + SLA
        chunks, vendor, site = _find_vendor_for_domain(domain, registry, retriever)
        sources = list({c["source_doc"] for c in chunks})

        # Step 3: extract SLA from retrieved chunks
        sla_text = "Not specified"
        for chunk in chunks:
            text = chunk["text"]
            m = re.search(
                r"(?:breakdown|response|attendance|emergency|callout)[^\n]*?(\d+\s*hour[s]?[^\.]*)",
                text, re.IGNORECASE,
            )
            if m:
                sla_text = m.group(0).strip()[:120]
                break

        sla_hours = _parse_sla_hours(sla_text)
        sla_status = _sla_status(duration_hours, sla_hours)

        # Step 4: draft escalation email
        context_str = "\n\n".join(c["text"][:600] for c in chunks[:2]) if chunks else "No contract found."
        draft_r = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": _DRAFT_PROMPT.format(
                    summary=summary,
                    vendor=vendor,
                    site=site,
                    sla=sla_text,
                    hours=f"{duration_hours:.1f}" if duration_hours else "Unknown",
                    sla_status=sla_status,
                ) + f"\n\nRelevant contract context:\n{context_str}",
            }],
            max_tokens=600, temperature=0.2,
        )
        escalation_email = draft_r.choices[0].message.content.strip()
        logger.info("triage complete: vendor=%s sla_status=%s", vendor, sla_status)

        return TriageResult(
            domain=domain, severity=severity, duration_hours=duration_hours,
            summary=summary, vendor=vendor, site=site,
            sla_hours=sla_hours, sla_status=sla_status,
            escalation_email=escalation_email, sources=sources,
        )

    except Exception as exc:
        logger.warning("incident triage failed (%s)", exc)
        return TriageResult(
            domain="general", severity="medium", duration_hours=None,
            summary=incident, vendor="Unknown", site="Site",
            sla_hours=None, sla_status="UNKNOWN", escalation_email="",
            succeeded=False, reason=str(exc),
        )
