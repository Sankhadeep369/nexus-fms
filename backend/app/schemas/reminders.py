from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class ReminderCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    notes: str | None = Field(None, max_length=2000)
    due_date: date
    recipient_email: EmailStr
    related_vendor: str | None = Field(None, max_length=200)


class ReminderResponse(BaseModel):
    id: str
    title: str
    notes: str | None = None
    due_date: date
    recipient_email: str
    related_vendor: str | None = None
    status: Literal["pending", "sent", "cancelled"]
    created_at: datetime
    sent_at: datetime | None = None
