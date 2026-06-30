"""Resend email integration for the Reminder Agent."""

from __future__ import annotations

import logging

logger = logging.getLogger("nexus.email_sender")


def send_reminder_email(
    api_key: str,
    from_email: str,
    to_email: str,
    title: str,
    notes: str | None,
    due_date: str,
    related_vendor: str | None,
) -> bool:
    try:
        import resend

        resend.api_key = api_key

        vendor_line = f"<p><strong>Related vendor:</strong> {related_vendor}</p>" if related_vendor else ""
        notes_line = f"<p>{notes}</p>" if notes else ""

        html = f"""
        <div style="font-family: sans-serif; max-width: 480px;">
          <h2 style="color: #4f46e5;">NEXUS Reminder</h2>
          <p style="font-size: 18px; font-weight: 600;">{title}</p>
          <p><strong>Due:</strong> {due_date}</p>
          {vendor_line}
          {notes_line}
          <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 16px 0;" />
          <p style="color: #6b7280; font-size: 12px;">
            Sent by NEXUS Facilities Management Assistant.
          </p>
        </div>
        """

        resend.Emails.send(
            {
                "from": from_email,
                "to": [to_email],
                "subject": f"Reminder: {title}",
                "html": html,
            }
        )
        logger.info("reminder email sent to %s for '%s'", to_email, title)
        return True

    except Exception as exc:
        logger.warning("failed to send reminder email to %s: %s", to_email, exc)
        return False
