"""Supabase-backed store for answer feedback (thumbs up / down).

Feedback is written after an answer is shown, off the response critical path, so it
never affects generation latency. Best-effort: a storage failure is logged, never
surfaced to the user.
"""

from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger("nexus.feedback_store")


class FeedbackStore:
    def __init__(self, url: str, key: str):
        from supabase import create_client

        self._client = create_client(url, key)

    def record(self, query: str, answer: str, rating: str, mode: str | None = None, comment: str | None = None) -> None:
        self._client.table("feedback").insert(
            {
                "query": (query or "")[:2000],
                "answer": (answer or "")[:8000],
                "rating": rating,
                "mode": mode,
                "comment": (comment or None),
            }
        ).execute()

    def summary(self) -> dict:
        """Aggregate thumbs up/down counts (system-wide — feedback isn't per-user).
        Best-effort: returns zeros on any error so the dashboard never breaks."""
        try:
            rows = self._client.table("feedback").select("rating,created_at").execute().data or []
        except Exception as exc:  # noqa: BLE001
            logger.warning("feedback summary failed: %s", exc)
            return {"up": 0, "down": 0, "total": 0}
        up = sum(1 for r in rows if r.get("rating") == "up")
        down = sum(1 for r in rows if r.get("rating") == "down")
        return {"up": up, "down": down, "total": up + down}


@lru_cache(maxsize=1)
def get_feedback_store() -> FeedbackStore | None:
    from app.core.config import settings

    if not settings.supabase_url or not settings.supabase_anon_key:
        logger.warning("Feedback store not configured (missing SUPABASE_URL/SUPABASE_ANON_KEY)")
        return None
    return FeedbackStore(settings.supabase_url, settings.supabase_anon_key)
