"""Reminder Agent orchestration: checks for due reminders and sends emails.

Triggered by an external cron (GitHub Actions, see .github/workflows/
reminder-check.yml) hitting GET /agents/reminders/check on a schedule, since
the backend only runs code on request — a reminder set for "60 days from now"
will never fire on its own if the container is asleep and nobody happens to
visit the site that day.
"""

from __future__ import annotations

import logging
from datetime import date

from app.core.agents.email_sender import send_reminder_email
from app.core.agents.reminder_store import ReminderStore

logger = logging.getLogger("nexus.reminder_agent")


def check_and_send_due_reminders(
    store: ReminderStore,
    resend_api_key: str,
    from_email: str,
) -> dict:
    due = store.find_due(as_of=date.today())
    sent_count = 0
    failed_count = 0

    for reminder in due:
        ok = send_reminder_email(
            api_key=resend_api_key,
            from_email=from_email,
            to_email=reminder["recipient_email"],
            title=reminder["title"],
            notes=reminder.get("notes"),
            due_date=reminder["due_date"],
            related_vendor=reminder.get("related_vendor"),
        )
        if ok:
            store.mark_sent(reminder["id"])
            sent_count += 1
        else:
            failed_count += 1

    logger.info("reminder check: %d due, %d sent, %d failed", len(due), sent_count, failed_count)
    return {"due": len(due), "sent": sent_count, "failed": failed_count}
