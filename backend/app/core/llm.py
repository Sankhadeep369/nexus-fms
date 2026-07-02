import logging
import threading
from abc import ABC, abstractmethod
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger("nexus.llm")

DEFAULT_SYSTEM_PROMPT = (
    "You are NEXUS, a facilities-management assistant. Be concise and helpful, and say "
    "so plainly if you are not confident about a specific detail instead of guessing."
)


class LLMBusyError(Exception):
    """Raised when a generation request arrives while another is already running.

    A single llama.cpp context can only run one generation at a time. Blocking
    silently on the lock let two overlapping requests compound into a 20+ minute
    wait for the second one (queued behind the first's full ~5-10 min generation,
    then ran its own). Failing fast instead lets the pipeline return a clear
    "try again shortly" message immediately rather than hanging.
    """


def load_system_prompt() -> str:
    path = settings.system_prompt_path
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return DEFAULT_SYSTEM_PROMPT


class ChatModel(ABC):
    """Common interface so the pipeline doesn't care whether generation happens
    on-device or on a remote Hugging Face Inference Endpoint."""

    @abstractmethod
    def stream_chat(
        self,
        messages: list[dict],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Iterator[str]: ...


class HFEndpointLLM(ChatModel):
    """Calls a deployed Hugging Face Inference Endpoint instead of running the model
    on-device -- offloads generation to a cloud GPU."""

    def __init__(self, endpoint_url: str, token: str | None):
        from huggingface_hub import InferenceClient

        self._client = InferenceClient(model=endpoint_url, token=token)

    def stream_chat(
        self,
        messages: list[dict],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Iterator[str]:
        stream = self._client.chat_completion(
            messages=messages,
            max_tokens=max_tokens or settings.max_new_tokens,
            temperature=settings.temperature_simple if temperature is None else temperature,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content


class LLM(ChatModel):
    """Wraps a llama-cpp-python model. A lock serializes generations because a single
    llama.cpp context cannot safely run concurrent inference calls."""

    def __init__(self, model_path: Path):
        from llama_cpp import Llama

        self._lock = threading.Lock()

        llm_kwargs: dict = dict(
            model_path=str(model_path),
            n_ctx=settings.llm_n_ctx,
            n_threads=settings.llm_n_threads or None,
            n_gpu_layers=settings.llm_n_gpu_layers,
            n_batch=settings.llm_n_batch,
            n_keep=settings.llm_n_keep,
            verbose=False,
        )
        if settings.llm_flash_attn:
            try:
                self._llm = Llama(**llm_kwargs, flash_attn=True)
                logger.info("llama.cpp: flash_attn=True")
            except TypeError:
                # Prebuilt wheel predates flash_attn support — fall back silently.
                logger.warning("flash_attn not supported by this llama-cpp-python build — skipping")
                self._llm = Llama(**llm_kwargs)
        else:
            self._llm = Llama(**llm_kwargs)

        # Warm the KV cache with the static system prompt so subsequent requests
        # skip re-encoding these ~500 tokens.  llama.cpp reuses KV entries for any
        # prompt prefix that matches what is already in the cache, so a single dummy
        # call at startup effectively pre-fills the system-prompt portion for all
        # real requests that follow.
        system_prompt = load_system_prompt()
        try:
            self._llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": ""},
                ],
                max_tokens=1,
                temperature=0.0,
            )
            logger.info("KV cache warmed — system prompt prefix (%d chars) ready", len(system_prompt))
        except Exception as exc:
            logger.warning("KV cache warm-up failed (%s) — first request will be slower", exc)

    def stream_chat(
        self,
        messages: list[dict],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Iterator[str]:
        if not self._lock.acquire(blocking=False):
            raise LLMBusyError("Another generation is already in progress")
        try:
            stream = self._llm.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens or settings.max_new_tokens,
                temperature=settings.temperature_simple if temperature is None else temperature,
                repeat_penalty=settings.repeat_penalty,
                stream=True,
            )
            for chunk in stream:
                delta = chunk["choices"][0].get("delta", {})
                text = delta.get("content")
                if text:
                    yield text
        finally:
            self._lock.release()


def _resolve_gguf_path() -> Path:
    local_path = settings.gguf_dir / Path(settings.gguf_filename).name
    if local_path.exists():
        return local_path

    from huggingface_hub import hf_hub_download

    settings.gguf_dir.mkdir(parents=True, exist_ok=True)
    # gguf_filename is "gguf/<name>.gguf" in the HF repo; downloading with local_dir set to
    # the parent of gguf_dir reproduces that "gguf/" subpath, landing the file at exactly
    # `local_path` above so subsequent runs hit the early-return.
    downloaded = hf_hub_download(
        repo_id=settings.hf_repo_id,
        filename=settings.gguf_filename,
        local_dir=str(settings.gguf_dir.parent),
        token=settings.hf_token,
    )
    return Path(downloaded)


@lru_cache(maxsize=1)
def get_llm() -> ChatModel:
    if settings.llm_backend == "hf_endpoint":
        if not settings.hf_endpoint_url:
            raise RuntimeError("LLM_BACKEND=hf_endpoint requires HF_ENDPOINT_URL to be set")
        return HFEndpointLLM(endpoint_url=settings.hf_endpoint_url, token=settings.hf_token)
    return LLM(model_path=_resolve_gguf_path())
