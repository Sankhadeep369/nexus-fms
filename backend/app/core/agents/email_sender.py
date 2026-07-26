"""Resend email integration for the Reminder Agent."""

from __future__ import annotations

import logging

logger = logging.getLogger("nexus.email_sender")

_WRAPPER = """
<div style="font-family: sans-serif; max-width: 480px;">
  <h2 style="color: #4f46e5;">{heading}</h2>
  {body}
  <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 16px 0;" />
  <p style="color: #6b7280; font-size: 12px;">
    Sent by NEXUS Facilities Management Assistant.
  </p>
</div>
"""


def _send(api_key: str, from_email: str, to_email: str, subject: str, html: str) -> bool:
    """Low-level Resend send. Returns True on success, False on any error
    (errors are logged, never raised, so a failed email never breaks the caller)."""
    try:
        import resend

        resend.api_key = api_key
        resend.Emails.send({"from": from_email, "to": [to_email], "subject": subject, "html": html})
        logger.info("email sent to %s (subject=%r)", to_email, subject)
        return True
    except Exception as exc:
        logger.warning("failed to send email to %s (subject=%r): %s", to_email, subject, exc)
        return False


def _details_html(title: str, due_date: str, related_vendor: str | None, notes: str | None) -> str:
    vendor_line = f"<p><strong>Related vendor:</strong> {related_vendor}</p>" if related_vendor else ""
    notes_line = f"<p>{notes}</p>" if notes else ""
    return (
        f'<p style="font-size: 18px; font-weight: 600;">{title}</p>'
        f"<p><strong>Due:</strong> {due_date}</p>"
        f"{vendor_line}{notes_line}"
    )


def send_reminder_email(
    api_key: str,
    from_email: str,
    to_email: str,
    title: str,
    notes: str | None,
    due_date: str,
    related_vendor: str | None,
) -> bool:
    """The due-date reminder itself, fired by the daily cron check."""
    body = _details_html(title, due_date, related_vendor, notes)
    html = _WRAPPER.format(heading="NEXUS Reminder", body=body)
    return _send(api_key, from_email, to_email, f"Reminder: {title}", html)


def send_reminder_confirmation_email(
    api_key: str,
    from_email: str,
    to_email: str,
    title: str,
    notes: str | None,
    due_date: str,
    related_vendor: str | None,
) -> bool:
    """Immediate confirmation sent when a reminder is created, so the user knows
    it's set and that email delivery works. The actual reminder is sent again on
    the due date by the daily cron check."""
    body = (
        _details_html(title, due_date, related_vendor, notes)
        + f'<p style="color: #6b7280; font-size: 13px;">'
        f"We'll email you again on <strong>{due_date}</strong> when this reminder is due.</p>"
    )
    html = _WRAPPER.format(heading="Reminder set ✓", body=body)
    return _send(api_key, from_email, to_email, f"Reminder set: {title}", html)
