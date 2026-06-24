from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    mode: Literal["simple", "thinking"] = "simple"
