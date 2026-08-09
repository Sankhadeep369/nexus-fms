from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.feedback_store import get_feedback_store

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackCreate(BaseModel):
    query: str
    answer: str
    rating: Literal["up", "down"]
    mode: str | None = None
    comment: str | None = Field(None, max_length=2000)


@router.post("")
def create_feedback(fb: FeedbackCreate) -> dict:
    """Record a thumbs up/down on an answer. Best-effort — never errors hard so the
    UI's fire-and-forget call is safe."""
    store = get_feedback_store()
    if store is None:
        return {"ok": False, "reason": "not_configured"}
    try:
        store.record(fb.query, fb.answer, fb.rating, fb.mode, fb.comment)
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001 — feedback must never surface a hard error
        return {"ok": False, "reason": str(exc)[:120]}
