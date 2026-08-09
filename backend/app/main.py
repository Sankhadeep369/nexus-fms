import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import calendar, chat, documents, feedback, reminders, suggestions
from app.core.chat_pipeline import get_chat_pipeline
from app.core.config import settings
from app.core.llm import get_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nexus.chat")

if sys.platform == "win32":
    # Windows' ProactorEventLoop logs a noisy ConnectionResetError traceback whenever an
    # SSE client disconnects mid-stream (e.g. browser tab closed). It's benign -- swallow it.
    from asyncio.proactor_events import _ProactorBasePipeTransport

    _orig_call_connection_lost = _ProactorBasePipeTransport._call_connection_lost

    def _quiet_call_connection_lost(self, exc):
        try:
            _orig_call_connection_lost(self, exc)
        except ConnectionResetError:
            pass

    _ProactorBasePipeTransport._call_connection_lost = _quiet_call_connection_lost


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build the self-describing corpus index first: the system prompt's live
    # "systems under contract" list and doc-class labels are derived from it, and
    # it must exist before the LLM warm-up renders the prompt.
    from app.core.corpus_index import get_corpus_index

    corpus = get_corpus_index()
    logger.info("Corpus index ready: %d docs, systems=%s", corpus.doc_count, corpus.categories)

    if settings.llm_backend == "hf_endpoint":
        logger.info("Using remote LLM backend: %s", settings.hf_endpoint_url)
    else:
        logger.info("Loading LLM (this can take a while on first run / first download)...")
    get_llm()

    get_chat_pipeline()
    logger.info("NEXUS backend ready.")
    yield


app = FastAPI(title="NEXUS API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(suggestions.router)
app.include_router(reminders.router)
app.include_router(feedback.router)
app.include_router(calendar.router)
app.include_router(documents.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/info")
def info() -> dict:
    return {
        "model": settings.hf_repo_id.split("/")[-1],
        "ctx": settings.llm_n_ctx,
        "backend": settings.llm_backend,
    }
