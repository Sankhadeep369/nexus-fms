import json
from collections.abc import Iterator

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.core.chat_pipeline import get_chat_pipeline
from app.schemas.chat import ChatRequest

router = APIRouter(tags=["chat"])


def _event_stream(query: str, mode: str, history: list) -> Iterator[dict]:
    pipeline = get_chat_pipeline()
    for event in pipeline.run(query, mode, history):
        yield {"event": event["type"], "data": json.dumps(event)}


@router.post("/chat")
def chat(request: ChatRequest) -> EventSourceResponse:
    history = [{"role": m.role, "content": m.content} for m in request.history]
    return EventSourceResponse(_event_stream(request.query, request.mode, history))
