"""Supabase-backed persistence for the Reminder Agent.

Diskcache on HF Spaces free tier is wiped whenever the container sleeps or
restarts, which makes it unsuitable for a reminder that needs to survive
days or weeks until its due date. Supabase (a hosted, open-source Postgres
platform with a generous free tier) provides durable storage instead.

Schema: see sql/reminders_schema.sql — run once in the Supabase SQL Editor.
"""

from __future__ import annotations

import logging
from datetime import date
from functools import lru_cache
from typing import Any

logger = logging.getLogger("nexus.reminder_store")


def _is_missing_column_error(exc: Exception) -> bool:
    """True if a PostgREST/Postgres error is about an unknown column (i.e. the
    optional due_time/system columns haven't been migrated yet)."""
    msg = str(exc).lower()
    return (
        "pgrst204" in msg
        or "schema cache" in msg
        or ("column" in msg and "does not exist" in msg)
    )


class ReminderStore:
    def __init__(self, url: str, key: str):
        from supabase import create_client

        self._client = create_client(url, key)

    def create(
        self,
        title: str,
        due_date: date,
        recipient_email: str,
        notes: str | None = None,
        related_vendor: str | None = None,
        due_time: str | None = None,
        system: str | None = None,
    ) -> dict[str, Any]:
        base = {
            "title": title,
            "due_date": due_date.isoformat(),
            "recipient_email": recipient_email,
            "notes": notes,
            "related_vendor": related_vendor,
        }
        payload = {**base, "due_time": due_time, "system": system}
        try:
            result = self._client.table("reminders").insert(payload).execute()
        except Exception as exc:
            # If the optional columns haven't been migrated yet, fall back to the
            # base insert so reminder creation never breaks on a stale schema.
            if _is_missing_column_error(exc):
                logger.warning(
                    "reminders: due_time/system columns missing — inserting base fields only. "
                    "Run the ALTER statements in sql/reminders_schema.sql. (%s)",
                    exc,
                )
                result = self._client.table("reminders").insert(base).execute()
            else:
                raise
        return result.data[0]

    def update(self, reminder_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        """Update a still-pending reminder. Returns the updated row, or None if it
        doesn't exist or is no longer pending (sent/cancelled reminders are frozen)."""
        if not fields:
            result = self._client.table("reminders").select("*").eq("id", reminder_id).execute()
            return result.data[0] if result.data else None

        def _do(payload: dict[str, Any]):
            return (
                self._client.table("reminders")
                .update(payload)
                .eq("id", reminder_id)
                .eq("status", "pending")
                .execute()
            )

        try:
            result = _do(fields)
        except Exception as exc:
            # Fall back if the optional columns haven't been migrated yet.
            if _is_missing_column_error(exc):
                base = {k: v for k, v in fields.items() if k not in ("due_time", "system")}
                result = _do(base)
            else:
                raise
        return result.data[0] if result.data else None

    def list_for_email(self, recipient_email: str) -> list[dict[str, Any]]:
        result = (
            self._client.table("reminders")
            .select("*")
            .eq("recipient_email", recipient_email)
            .order("due_date", desc=False)
            .execute()
        )
        return result.data

    def cancel(self, reminder_id: str) -> bool:
        result = (
            self._client.table("reminders")
            .update({"status": "cancelled"})
            .eq("id", reminder_id)
            .eq("status", "pending")
            .execute()
        )
        return len(result.data) > 0

    def find_due(self, as_of: date) -> list[dict[str, Any]]:
        """Pending reminders due on or before `as_of` (catches any missed by a
        cron gap)."""
        result = (
            self._client.table("reminders")
            .select("*")
            .eq("status", "pending")
            .lte("due_date", as_of.isoformat())
            .execute()
        )
        return result.data

    def mark_sent(self, reminder_id: str) -> None:
        from datetime import datetime, timezone

        self._client.table("reminders").update(
            {"status": "sent", "sent_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", reminder_id).execute()


@lru_cache(maxsize=1)
def get_reminder_store() -> ReminderStore | None:
    from app.core.config import settings

    if not settings.supabase_url or not settings.supabase_anon_key:
        logger.warning("Reminder store not configured (missing SUPABASE_URL/SUPABASE_ANON_KEY)")
        return None
    return ReminderStore(settings.supabase_url, settings.supabase_anon_key)
