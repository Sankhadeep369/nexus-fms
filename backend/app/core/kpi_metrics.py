"""Auto-derived KPI metrics computed from NEXUS's own operational data.

These are read-only, computed live on request from data the app already stores
(reminders in Supabase, answer feedback). Nothing here touches the chat path, so
it has no effect on chat/response latency. Manually-tracked KPIs live client-side;
this module only produces the "live" cards the dashboard merges in.

Incident-based KPIs (count / MTTR / response time) are intentionally absent: the
triage agent emails vendors but does not persist incidents yet, so there is no
data to aggregate. Add incident persistence to unlock those.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta

logger = logging.getLogger("nexus.kpi")


def _as_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _reminder_kpis(email: str) -> list[dict]:
    from app.core.agents.reminder_store import get_reminder_store

    store = get_reminder_store()
    if store is None:
        return []
    try:
        rows = store.list_for_email(email)
    except Exception as exc:  # noqa: BLE001
        logger.warning("reminder KPI fetch failed: %s", exc)
        return []
    if not rows:
        return []

    today = date.today()
    active = [r for r in rows if r.get("status") != "cancelled"]
    overdue = sum(1 for r in active if r.get("status") == "pending" and (_as_date(r.get("due_date")) or today) < today)
    horizon = today + timedelta(days=30)
    upcoming = sum(
        1 for r in active
        if r.get("status") == "pending" and (d := _as_date(r.get("due_date"))) and today <= d <= horizon
    )
    completed = sum(1 for r in active if r.get("status") == "sent")

    # Monthly compliance: of the reminders due in a month, how many were completed
    # on or before their due date.
    by_month_due: dict[str, int] = defaultdict(int)
    by_month_ontime: dict[str, int] = defaultdict(int)
    for r in active:
        due = _as_date(r.get("due_date"))
        if not due:
            continue
        key = due.strftime("%Y-%m")
        by_month_due[key] += 1
        if r.get("status") == "sent":
            sent = _as_date(r.get("sent_at")) or due
            if sent <= due:
                by_month_ontime[key] += 1
    series = [
        {"period": k, "value": round(100 * by_month_ontime[k] / by_month_due[k], 1)}
        for k in sorted(by_month_due)
        if by_month_due[k]
    ]
    latest = series[-1]["value"] if series else None

    return [
        {
            "id": "reminder_compliance", "name": "Reminder Compliance", "category": "Compliance",
            "unit": "%", "target": 95, "direction": "up", "value": latest, "series": series,
            "source": "derived", "hint": "Reminders completed on or before their due date.",
        },
        {
            "id": "overdue_reminders", "name": "Overdue Reminders", "category": "Maintenance",
            "unit": "", "target": 0, "direction": "down", "value": overdue, "series": [],
            "source": "derived", "hint": "Pending reminders already past their due date.",
        },
        {
            "id": "upcoming_reminders", "name": "Upcoming (30 days)", "category": "Maintenance",
            "unit": "", "target": None, "direction": "up", "value": upcoming, "series": [],
            "source": "derived", "hint": "Pending reminders due in the next 30 days.",
        },
        {
            "id": "completed_reminders", "name": "Completed Reminders", "category": "Maintenance",
            "unit": "", "target": None, "direction": "up", "value": completed, "series": [],
            "source": "derived", "hint": "Reminders sent to date.",
        },
    ]


def _feedback_kpi() -> list[dict]:
    from app.core.feedback_store import get_feedback_store

    store = get_feedback_store()
    if store is None:
        return []
    s = store.summary()
    if not s.get("total"):
        return []
    approval = round(100 * s["up"] / s["total"], 1)
    return [
        {
            "id": "assistant_approval", "name": "Assistant Approval", "category": "Service quality",
            "unit": "%", "target": 90, "direction": "up", "value": approval, "series": [],
            "source": "derived",
            "hint": f"Thumbs-up share of {s['total']} rated answers (system-wide).",
        }
    ]


def derived_kpis(email: str | None) -> dict:
    kpis: list[dict] = []
    if email:
        kpis.extend(_reminder_kpis(email))
    kpis.extend(_feedback_kpi())
    return {"kpis": kpis, "generated_at": datetime.utcnow().isoformat() + "Z"}
