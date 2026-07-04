from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Paths ---
    # Defaults resolve inside the repo so the app is self-contained in Docker and
    # on any fresh clone.  Override via .env to point at the larger project tree
    # on a local dev machine (e.g. GGUF_DIR=D:/NEXUS/06_model_artifacts/gguf).
    data_dir: Path = BACKEND_ROOT / "data"
    gguf_dir: Path = BACKEND_ROOT / "data" / "models"
    system_prompt_path: Path = BACKEND_ROOT / "app" / "prompts" / "system_prompt.md"
    corpus_dir: Path = BACKEND_ROOT / "data" / "corpus"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    # --- Model source ---
    hf_repo_id: str = "MioA9/gemma3-4b-nexus-qlora-v1"
    gguf_filename: str = "gguf/gemma3-4b-nexus-q4_k_m-v1.gguf"
    hf_token: str | None = None

    # --- LLM runtime ---
    # 4096 gives headroom for system prompt (~500 tok) + conversation history (~400 tok)
    # + 3 retrieved chunks (~1500 tok) + query (~50 tok) + generated answer (400 tok).
    llm_n_ctx: int = 4096
    # Match physical core count of the deployment target.
    # HF Spaces cpu-basic = 2 vCPU → set to 2. Local dev can override via .env.
    llm_n_threads: int = 2
    llm_n_gpu_layers: int = 0
    # Capped at 400 to keep response time reasonable on CPU; covers all FM answers.
    max_new_tokens: int = 400
    # Larger batch speeds up prompt prefill on CPU.
    llm_n_batch: int = 1024
    # "Simple" mode favors focused, deterministic answers; "Thinking" mode raises the
    # temperature for more exploratory, multi-angle reasoning on harder questions.
    temperature_simple: float = 0.2
    temperature_thinking: float = 0.7
    # >1.0 penalizes tokens the model has already generated, which is what stops the
    # long repetition loops seen at the llama.cpp default of 1.0 (no-op).
    repeat_penalty: float = 1.15
    # KV-cache prefix protection intent: keep the first llm_n_keep tokens (system
    # prompt) safe from context-shift eviction.  In llama-cpp-python 0.3.x this is
    # handled internally by the C layer and is NOT exposed as a Python constructor or
    # inference parameter — the field is retained for documentation and future-proofing
    # but is not actively passed to the model.
    llm_n_keep: int = 600
    # Enable CPU Flash Attention (added to llama.cpp ≥ b3753).  Reduces attention
    # memory from O(n²) to O(n), giving ~10-20% generation speedup on long contexts.
    # Silently skipped if the installed llama-cpp-python wheel predates support.
    llm_flash_attn: bool = True
    # Contextual compression: after retrieval, a single Groq call extracts only the
    # 2-3 sentences per chunk most relevant to the query.  Disabled: compression
    # strips scenario-matrix rows, exact INR figures, and multi-clause SLA content
    # that the SLM needs verbatim — faithfulness and ROUGE both drop when active.
    context_compression_enabled: bool = False

    # --- LLM backend ---
    # "local"      -> run the GGUF on-device via llama.cpp (default, no extra setup)
    # "hf_endpoint" -> call a deployed Hugging Face Inference Endpoint over HTTP instead,
    #                  offloading generation to a cloud GPU. Requires hf_endpoint_url and
    #                  (for private/protected endpoints) hf_token.
    llm_backend: str = "local"
    hf_endpoint_url: str | None = None

    # --- Retrieval (hybrid BM25 + embeddings over 02_extracted_text) ---
    retrieval_top_k: int = 3
    # BGE-small outperforms MiniLM-L6 on MTEB retrieval benchmarks at the same 384-D
    # and is a drop-in swap.  MiniLM-L6 is a symmetric similarity model; BGE is
    # trained specifically for asymmetric query-to-passage retrieval.
    retrieval_embedding_model: str = "BAAI/bge-small-en-v1.5"
    # Instruction prefix prepended to queries (NOT to passage/chunk text) for BGE
    # models.  Improves retrieval quality by moving query embeddings into passage
    # space.  Set to "" to disable (e.g. when switching back to MiniLM).
    retrieval_query_instruction: str = "Represent this sentence for searching relevant passages: "
    # Weight on the (min-max normalized) BM25 score vs. the dense cosine score when
    # combining the two rankings, in [0, 1].
    retrieval_bm25_weight: float = 0.5
    # A chunk is treated as relevant -- and included in the injected context -- if
    # either of these is met:
    # - dense cosine similarity >= retrieval_min_dense_score (catches paraphrased /
    #   semantically related queries), or
    # - raw BM25 score >= retrieval_min_bm25_score (catches queries dominated by
    #   exact numbers/names/codes, which can have strong lexical overlap with a
    #   chunk despite low semantic similarity).
    # If neither chunk meets either bar, the query is treated as unrelated to the
    # corpus (e.g. "write an email about my vacation") and no context is injected.
    #
    # 0.18 (was 0.30): BGE-small uses a contrastive training objective that produces
    # numerically lower cosine scores than MiniLM for equally relevant pairs.
    # Threshold was recalibrated from BGE score distributions on the FM eval set —
    # relevant chunks routinely scored 0.14-0.22, well below the MiniLM-calibrated 0.30.
    retrieval_min_dense_score: float = 0.18
    retrieval_min_bm25_score: float = 15.0
    # Cross-encoder re-ranking: after BM25+dense retrieves the top
    # `retrieval_reranker_candidates` chunks, a cross-encoder scores each
    # (query, chunk) pair jointly and re-orders them before returning top-k.
    # Cross-encoders are far more accurate than bi-encoders for relevance ranking
    # because they attend to both texts simultaneously rather than comparing
    # independent embeddings.  MiniLM-L6 cross-encoder is fast on CPU (~50ms
    # per query for 20 candidates) and adds negligible wall-clock latency.
    retrieval_reranker_enabled: bool = True
    retrieval_reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    retrieval_reranker_candidates: int = 20  # fetch this many, rerank, keep top_k
    # Overlap from the tail of the previous section prepended to the next chunk.
    # Ensures content at section boundaries appears in at least two chunks so a
    # query matching the transition region is not missed.
    # 75 (was 150): reduced to limit BM25 dilution — the extra 150 chars of
    # off-topic section text lowered BM25 scores enough to fail the 20.0 gate for
    # numeric/financial queries. 75 chars preserves boundary coverage at half the cost.
    retrieval_chunk_overlap_chars: int = 75

    # --- Groq (query pre-processor + answer rewriter/validator) ---
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"
    # Toggle the Groq query pre-processor (rewrites/classifies the query before retrieval)
    query_preprocessor_enabled: bool = True
    # Toggle the Groq answer rewriter (validates + rewrites the generated answer)
    answer_rewriter_enabled: bool = True
    # Minimum quality score (0-10) to accept an answer; below this a fallback is shown.
    validation_min_score: int = 6
    # How many previous conversation turns (user+assistant pairs) to include in the
    # prompt for context. 0 disables conversation memory.
    max_history_turns: int = 2

    # Legacy alias kept for backwards compat with existing .env files
    @property
    def groq_judge_model(self) -> str:
        return self.groq_model

    # --- Reminder Agent (Supabase persistence + Resend email) ---
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    resend_api_key: str | None = None
    # Sender shown on outgoing reminder emails. Resend's sandbox domain works
    # without DNS verification; replace with a verified domain in production.
    reminder_from_email: str = "NEXUS Reminders <onboarding@resend.dev>"
    # Shared secret required as a query param on the cron-triggered check
    # endpoint so public internet traffic can't spam-trigger reminder checks.
    reminder_check_secret: str | None = None

    # --- Cache ---
    cache_ttl_seconds: int = 60 * 60 * 24 * 7

    # --- API ---
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
