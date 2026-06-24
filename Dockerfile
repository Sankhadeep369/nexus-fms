# HuggingFace Spaces requires the app to bind on port 7860 and run as a
# non-root user (uid 1000).  The GGUF is NOT baked in — it downloads from
# HF Hub on first startup (~60-90s cold-start on free tier) and is cached
# in /app/backend/data/models/ for the lifetime of the container.

FROM python:3.11-slim

# Non-root user required by HF Spaces
RUN useradd -m -u 1000 nexus

# All app code lives under /app/backend so `from app.core...` imports resolve
# correctly when uvicorn is launched from this directory.
WORKDIR /app/backend

# libgomp1 is a runtime dep of the llama-cpp-python CPU wheel (OpenMP)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps as a separate layer so rebuilds on code-only changes
# don't re-download the full torch + sentence-transformers stack (~1.5 GB).
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        llama-cpp-python \
        --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source (corpus lands at data/corpus/, already present)
COPY backend/ .

# Seed the 20 suggestion-chip answers directly into the cache at build time.
# This step only touches diskcache — no model is loaded.
RUN python -m scripts.seed_suggestion_cache

# Fix ownership before dropping to the non-root user
RUN chown -R nexus:nexus /app
USER nexus

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
