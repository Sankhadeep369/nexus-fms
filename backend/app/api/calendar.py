"""SLM-driven calendar event extraction.

Given a piece of text (a chat answer, a reminder note), the model pulls out a single
calendar event — title, date, optional time, notes — resolving relative dates against
today. The frontend turns that into a Google Calendar link and a downloadable .ics
(Outlook/Teams/Apple). This runs ONLY when the user clicks "Add to calendar", so it
never touches chat response timing.
"""

import json
import re
from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/calendar", tags=["calendar"])


class ExtractRequest(BaseModel):
    text: str


_PROMPT = """\
Extract a SINGLE calendar event from the text below, if one is clearly implied
(a renewal, deadline, inspection, drill, meeting, audit, due date, etc.).

Today is {today}. Resolve any relative dates ("next Friday", "in 30 days", "end of
the month") to an absolute calendar date.

Return ONLY valid JSON, no other text:
{{"found": true, "title": "short event title", "date": "YYYY-MM-DD", "time": "HH:MM" or null, "notes": "one-line detail"}}
If there is no clear event or date, return exactly: {{"found": false}}

Text:
{text}"""


@router.post("/extract")
def extract_event(req: ExtractRequest) -> dict:
    if not settings.groq_api_key:
        return {"found": False, "reason": "not_configured"}
    try:
        from groq import Groq

        client = Groq(api_key=settings.groq_api_key, max_retries=1)
        r = client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": _PROMPT.format(today=date.today().isoformat(), text=req.text[:1500])}],
            max_tokens=200,
            temperature=0.0,
        )
        raw = r.choices[0].message.content or ""
        m = re.search(r"\{[\s\S]+\}", raw)
        data = json.loads(m.group()) if m else {"found": False}
        if not isinstance(data, dict) or not data.get("found"):
            return {"found": False}
        # Validate the date shape; drop the event if the model returned junk.
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(data.get("date", ""))):
            return {"found": False}
        time_val = data.get("time")
        if time_val is not None and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(time_val)):
            time_val = None
        return {
            "found": True,
            "title": str(data.get("title") or "Reminder")[:200],
            "date": data["date"],
            "time": time_val,
            "notes": str(data.get("notes") or "")[:500],
        }
    except Exception as exc:  # noqa: BLE001
        return {"found": False, "reason": str(exc)[:120]}
