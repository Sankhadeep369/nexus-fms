"""KPI dashboard API — read-only, auto-derived metrics from NEXUS's own data.

Manually-tracked KPIs are stored client-side (localStorage); this endpoint only
returns the "live" cards computed from reminders + feedback. Entirely off the chat
path, so it never affects response latency.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.kpi_metrics import derived_kpis

router = APIRouter(prefix="/kpis", tags=["kpis"])


@router.get("/derived")
def get_derived_kpis(email: str | None = Query(default=None, description="Owner email for per-user reminder KPIs")) -> dict:
    return derived_kpis(email)
