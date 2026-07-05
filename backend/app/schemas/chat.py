from typing import Literal

from pydantic import BaseModel, Field


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    mode: Literal["simple", "thinking"] = "simple"
    # Last N turns of conversation sent from the frontend for context.
    # The pipeline caps this at settings.max_history_turns pairs.
    history: list[HistoryMessage] = Field(default_factory=list)
    # Force cold inference (skip cache read/write). Used by the eval harness so every
    # record is generated fresh — a cache hit returns no retrieved_sources and would
    # otherwise corrupt retrieval_hit and geval aggregates.
    bypass_cache: bool = False
