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
1. domain: the facilities system most responsible, chosen from this list:
   {domains}
   Use the exact label as written; use "general" only if none clearly fit.
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
{timing}

Write a complete email (Subject, Greeting, Body, Sign-off) to the vendor.
- Convey urgency appropriate to the incident.
- If a specific SLA response time is given and it has been breached, cite the breach and request immediate attendance; otherwise reference the committed response time only if one is given.
- Do NOT state any duration, number of hours, or SLA status that is not provided above. If the timing is not specified, refer to the issue as "recently reported" — never write the word "unknown" and never leave a blank or placeholder.
- Do not invent any figures, names, or clauses not provided above.
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


def _domain_tokens(label: str | None) -> set[str]:
    return set(re.findall(r"[a-z]+", (label or "").lower()))


def _find_vendor_for_domain(
    domain: str,
    retriever,
) -> tuple[list[dict], str, str, str | None, list[str]]:
    """Resolve the responsible current contract for an incident domain from the
    self-describing corpus index, returning
    (chunks, vendor, site, sla_from_facts, source_docs).

    Vendor, site, and SLA come straight from the indexed contract facts (clean
    legal name + facility name), not from parsing the filename, and the domain is
    matched against the live `system` of each current contract — so a new system
    added to the corpus is handled with no code change.
    """
    from app.core.agents.tools import _rank_chunks_in_docs
    from app.core.corpus_index import get_corpus_index

    ci = get_corpus_index()
    want = _domain_tokens(domain)
    matches = [
        m for m in ci.current_docs
        if want and (want & _domain_tokens(m.system or m.category))
    ]
    if not matches:
        return [], "Unknown Vendor", "Site", None, []

    doc = sorted(matches, key=lambda m: m.source_doc)[0]  # deterministic (HQ first)
    chunks = _rank_chunks_in_docs(
        retriever,
        f"{domain} SLA response time breakdown attendance emergency callout",
        "current_contracts/",
        [doc.source_doc],
        k=2,
    )
    return (
        chunks,
        doc.vendor or "Unknown Vendor",
        doc.site or "Site",
        doc.sla_response,
        [doc.source_doc],
    )


def run_incident_triage(
    incident: str,
    api_key: str,
    model: str,
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

        # Step 1: classify — domain options are the live contracted systems.
        from app.core.corpus_index import get_corpus_index

        domains = ", ".join(get_corpus_index().contracted_systems + ["general"])
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _CLASSIFY_PROMPT.format(
                incident=incident[:800], domains=domains,
            )}],
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

        # Step 2: find responsible vendor + SLA from indexed contract facts
        chunks, vendor, site, sla_from_facts, doc_sources = _find_vendor_for_domain(domain, retriever)
        sources = list({c["source_doc"] for c in chunks}) or doc_sources

        # Step 3: SLA — prefer the indexed fact; fall back to the chunk text when
        # the fact wasn't extracted (SLA is only reliably on file for some contracts).
        sla_text = sla_from_facts or "Not specified"
        if not sla_from_facts:
            for chunk in chunks:
                m = re.search(
                    r"(?:breakdown|response|attendance|emergency|callout)[^\n]*?(\d+\s*hour[s]?[^\.]*)",
                    chunk["text"], re.IGNORECASE,
                )
                if m:
                    sla_text = m.group(0).strip()[:120]
                    break

        sla_hours = _parse_sla_hours(sla_text)
        sla_status = _sla_status(duration_hours, sla_hours)

        # Step 4: draft escalation email. When the report time isn't known we pass a
        # natural-language instruction instead of literal "Unknown" so it never leaks
        # into the email body.
        context_str = "\n\n".join(c["text"][:600] for c in chunks[:2]) if chunks else "No contract found."
        if duration_hours:
            timing_block = f"Hours since reported: {duration_hours:.0f}\nSLA status: {sla_status}"
        else:
            timing_block = (
                "Timing: not specified — refer to the issue as recently reported; "
                "do not state a specific duration or SLA status."
            )
        draft_r = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": _DRAFT_PROMPT.format(
                    summary=summary,
                    vendor=vendor,
                    site=site,
                    sla=sla_text,
                    timing=timing_block,
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
