---
title: NEXUS FMS
emoji: 🏢
colorFrom: indigo
colorTo: blue
sdk: docker
pinned: false
license: mit
short_description: Facilities management AI assistant — fine-tuned Gemma 3 4B
---

# NEXUS — Facilities Management AI Assistant

NEXUS is a domain-specific AI assistant built for facilities management teams. It answers operational questions — maintenance schedules, compliance checklists, vendor contract comparisons, SLA benchmarks, safety drills — the kind of thing that usually means digging through binders or chasing down the right person.

The model is a fine-tuned Gemma 3 4B, trained on ~600 instruction pairs drawn from real facilities documents: AMC contracts, HSE SOPs, HVAC maintenance records, fire safety NOCs, and more. It's not a generic chatbot pointed at a knowledge base — the domain knowledge is baked into the weights.

This repository is the application layer: a FastAPI backend that runs the model locally (or via Groq for cloud deployment) and a React frontend with a clean chat interface.

---

## What it can do

- Answer detailed facilities questions (PPE requirements, inspection checklists, SLA response times, PM schedules)
- Draft documents — memos, vendor emails, incident reports, compliance summaries
- Compare contract structures (comprehensive vs. non-comprehensive AMCs, SLA tiers)
- 20 pre-cached instant-response suggestions across the most common FM query types
- Simple / Thinking mode toggle: lower temperature for focused answers, higher for more exploratory reasoning
- Full chat history persistence, dark/light theme, slash-command suggestion picker

---

## Stack

**Backend**
- Python 3.11 + FastAPI
- [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) — runs the GGUF locally via CPU inference
- [diskcache](https://github.com/grantjenks/python-diskcache) — SQLite-backed response cache with SHA-256 keying
- Server-Sent Events (SSE) for streaming token-by-token output

**Frontend**
- React 18 + Vite
- Tailwind CSS (custom dark/light design system)
- Framer Motion for transitions and the thinking indicator
- react-markdown + remark-gfm for rendered responses

**Model**
- Base: Gemma 3 4B
- Fine-tuning: QLoRA via Unsloth on ~600 facilities-domain instruction pairs
- Format: GGUF Q4_K_M, hosted on HuggingFace Hub at [MioA9/gemma3-4b-nexus-qlora-v1](https://huggingface.co/MioA9/gemma3-4b-nexus-qlora-v1)

---

## Running locally

### Prerequisites
- Python 3.11+
- Node 18+
- ~3 GB free disk space (GGUF download on first run)

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# llama-cpp-python needs a prebuilt CPU wheel (no C++ toolchain required)
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
pip install -r requirements.txt

# Copy and edit the environment file
cp .env.example .env
# Add your HF_TOKEN if the model repo is private

uvicorn app.main:app --reload
```

The model downloads automatically on first startup from HuggingFace Hub. Expect ~30 seconds for the download and load. After that it's ready at `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open `http://localhost:5173`.

### Seeding the suggestion cache (optional but recommended)

The 20 suggestion chips in the UI answer instantly because they hit a pre-seeded cache. Run this once after setup:

```bash
cd backend
python -m scripts.seed_suggestion_cache
```

---

## Cloud deployment (POC / free tier)

For demos and stakeholder reviews, the backend can route inference to Groq instead of running the GGUF locally. This fits inside free-tier container RAM limits.

```
LLM_BACKEND=groq
GROQ_API_KEY=your_key
GROQ_MODEL=llama-3.1-8b-instant
```

- **Frontend**: Vercel (zero-config Vite, auto-deploys from `main`)
- **Backend**: Render (Docker, free tier, set env vars above)
- **Cache**: pre-baked into the Docker image so suggestions work on cold start

---

## Project structure

```
backend/
  app/
    api/          # FastAPI route handlers (chat, suggestions)
    core/         # Pipeline, cache, LLM wrapper, config
    prompts/      # system_prompt.md — edit this to adjust NEXUS's tone/persona
    schemas/      # Pydantic request/response models
  scripts/
    seed_suggestion_cache.py   # injects pre-written answers directly into cache
    pregenerate_suggestions.py # alternative: LLM-based cache warming (slower)
  data/
    cache/        # diskcache SQLite store (gitignored)

frontend/
  src/
    components/   # ChatWindow, ChatInput, MessageBubble, Sidebar, Header, etc.
    context/      # ChatHistoryContext, ThemeContext
    hooks/        # useChat, useSuggestions
    lib/          # SSE streaming helper
```

---

## How the system prompt works

NEXUS's persona, formatting rules, and answer style live in `backend/app/prompts/system_prompt.md`. You can edit that file directly — no code changes needed. The backend reads it at startup.

The file controls things like: use **bold** for key terms, proper Markdown tables (never fake ones), `##`/`###` headings, no emojis, full documents for writing requests (emails need a subject, greeting, body, and sign-off), not just outlines.

---

## Status

This is a proof-of-concept built during dissertation research. Phase 1 (fine-tuning the model) is complete. Phase 2 (this app + deployment) is in progress. Phase 3 (agentic workflows) is next.

It's not production-hardened — there's no user auth, no multi-tenancy, and the free-tier inference backend is a stand-in for the actual fine-tuned model. The point right now is to demonstrate the domain capability, not scale it.

---

## License

MIT
