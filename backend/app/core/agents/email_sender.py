"""Resend email integration for the Reminder Agent."""

from __future__ import annotations

import logging

logger = logging.getLogger("nexus.email_sender")

_WRAPPER = """
<div style="font-family: sans-serif; max-width: 480px;">
  <h2 style="color: #4f46e5; margin-bottom: 4px;">{heading}</h2>
  <p style="font-size: 18px; font-weight: 600; margin-top: 0;">{title}</p>
  {intro}
  <table style="border-collapse: collapse; font-size: 14px; margin-top: 8px;">
    {rows}
  </table>
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


def _detail_rows(
    due_date: str,
    due_time: str | None,
    system: str | None,
    related_vendor: str | None,
    notes: str | None,
) -> str:
    """Renders the reminder's fields as table rows, skipping any that are unset."""
    when = f"{due_date} at {due_time}" if due_time else due_date
    fields = [
        ("System", system or "General"),
        ("Due", when),
        ("Related vendor", related_vendor),
        ("Notes", notes),
    ]
    rows = []
    for label, value in fields:
        if not value:
            continue
        rows.append(
            f'<tr>'
            f'<td style="padding: 4px 12px 4px 0; color: #6b7280; vertical-align: top; white-space: nowrap;">{label}</td>'
            f'<td style="padding: 4px 0; color: #111827;">{value}</td>'
            f"</tr>"
        )
    return "".join(rows)


def _build_html(
    heading: str,
    title: str,
    intro: str,
    due_date: str,
    due_time: str | None,
    system: str | None,
    related_vendor: str | None,
    notes: str | None,
) -> str:
    return _WRAPPER.format(
        heading=heading,
        title=title,
        intro=intro,
        rows=_detail_rows(due_date, due_time, system, related_vendor, notes),
    )


def send_reminder_email(
    api_key: str,
    from_email: str,
    to_email: str,
    title: str,
    notes: str | None,
    due_date: str,
    related_vendor: str | None,
    due_time: str | None = None,
    system: str | None = None,
) -> bool:
    """The due-date reminder itself, fired by the daily cron check. The subject is
    the reminder title; the body lays out every field."""
    html = _build_html(
        heading="NEXUS Reminder",
        title=title,
        intro="",
        due_date=due_date,
        due_time=due_time,
        system=system,
        related_vendor=related_vendor,
        notes=notes,
    )
    return _send(api_key, from_email, to_email, title, html)


def send_reminder_confirmation_email(
    api_key: str,
    from_email: str,
    to_email: str,
    title: str,
    notes: str | None,
    due_date: str,
    related_vendor: str | None,
    due_time: str | None = None,
    system: str | None = None,
) -> bool:
    """Immediate confirmation sent when a reminder is created, so the user knows
    it's set and that email delivery works. The actual reminder is sent again on
    the due date by the daily cron check."""
    when = f"{due_date} at {due_time}" if due_time else due_date
    intro = (
        f'<p style="color: #6b7280; font-size: 13px; margin: 4px 0 0;">'
        f"We'll email you again on <strong>{when}</strong> when this reminder is due.</p>"
    )
    html = _build_html(
        heading="Reminder set ✓",
        title=title,
        intro=intro,
        due_date=due_date,
        due_time=due_time,
        system=system,
        related_vendor=related_vendor,
        notes=notes,
    )
    return _send(api_key, from_email, to_email, f"Reminder set: {title}", html)
