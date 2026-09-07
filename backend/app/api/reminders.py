from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.core.agents.email_sender import send_reminder_confirmation_email
from app.core.agents.reminder_agent import check_and_send_due_reminders
from app.core.agents.reminder_store import get_reminder_store
from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.schemas.reminders import ReminderCreate, ReminderResponse, ReminderUpdate

router = APIRouter(prefix="/agents/reminders", tags=["reminders"])


def _require_store():
    store = get_reminder_store()
    if store is None:
        raise HTTPException(
            status_code=503,
            detail="Reminder Agent is not configured (missing Supabase credentials).",
        )
    return store


@router.post("", response_model=ReminderResponse, dependencies=[Depends(rate_limiter(15))])
def create_reminder(reminder: ReminderCreate, background_tasks: BackgroundTasks) -> dict:
    store = _require_store()
    created = store.create(
        title=reminder.title,
        due_date=reminder.due_date,
        recipient_email=reminder.recipient_email,
        notes=reminder.notes,
        related_vendor=reminder.related_vendor,
        due_time=reminder.due_time,
        system=reminder.system,
    )
    # Best-effort confirmation email so the user immediately knows the reminder is
    # set and that email delivery works (the due-date reminder itself is sent later
    # by the daily cron). Runs in the background so it never delays or fails the
    # create response; delivery errors are logged inside the sender.
    if settings.resend_api_key:
        background_tasks.add_task(
            send_reminder_confirmation_email,
            api_key=settings.resend_api_key,
            from_email=settings.reminder_from_email,
            to_email=created["recipient_email"],
            title=created["title"],
            notes=created.get("notes"),
            due_date=created["due_date"],
            due_time=created.get("due_time"),
            system=created.get("system"),
            related_vendor=created.get("related_vendor"),
        )
    return created


@router.get("", response_model=list[ReminderResponse], dependencies=[Depends(rate_limiter(60))])
def list_reminders(email: str = Query(..., description="Recipient email to list reminders for")) -> list[dict]:
    store = _require_store()
    return store.list_for_email(email)


@router.patch("/{reminder_id}", response_model=ReminderResponse, dependencies=[Depends(rate_limiter(30))])
def update_reminder(
    reminder_id: str,
    patch: ReminderUpdate,
    email: str = Query(..., description="Owner email — must match the reminder's recipient"),
) -> dict:
    store = _require_store()
    fields = patch.model_dump(exclude_unset=True, mode="json")
    # Ownership check: the update only applies to a reminder whose recipient_email
    # matches the caller-supplied email, so a bare reminder id can't be tampered with.
    updated = store.update(reminder_id, fields, owner_email=email)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail="Reminder not found, not yours, or not editable (only pending reminders can be edited).",
        )
    return updated


@router.delete("/{reminder_id}", dependencies=[Depends(rate_limiter(30))])
def cancel_reminder(
    reminder_id: str,
    email: str = Query(..., description="Owner email — must match the reminder's recipient"),
) -> dict:
    store = _require_store()
    ok = store.cancel(reminder_id, owner_email=email)
    if not ok:
        raise HTTPException(status_code=404, detail="Reminder not found, not yours, or already sent/cancelled.")
    return {"cancelled": True}


@router.get("/check")
def check_due_reminders(secret: str = Query(...)) -> dict:
    """Triggered by the GitHub Actions cron workflow on a schedule. Requires a
    shared secret so public traffic can't spam-trigger reminder checks."""
    if not settings.reminder_check_secret or secret != settings.reminder_check_secret:
        raise HTTPException(status_code=403, detail="Invalid or missing secret.")
    if not settings.resend_api_key:
        raise HTTPException(status_code=503, detail="Resend is not configured (missing RESEND_API_KEY).")

    store = _require_store()
    return check_and_send_due_reminders(
        store=store,
        resend_api_key=settings.resend_api_key,
        from_email=settings.reminder_from_email,
    )
