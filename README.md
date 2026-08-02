---
title: NEXUS FMS
emoji: 🏗️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# NEXUS — Facilities Management AI Assistant

NEXUS is a domain-specific AI assistant built for facilities management teams. It answers operational questions — maintenance schedules, compliance checklists, vendor contract comparisons, SLA benchmarks, safety drills — the kind of thing that usually means digging through binders or chasing down the right person.

The model is a fine-tuned **Gemma 3 4B**, trained on facilities-domain instruction pairs drawn from real documents: AMC contracts, HSE SOPs, HVAC maintenance records, fire safety NOCs, and more. It's not a generic chatbot pointed at a knowledge base — the domain knowledge is baked into the weights, and a retrieval + grounding pipeline keeps answers tied to the actual corpus.

This repository is the **application layer**: a FastAPI backend that runs the model (locally via GGUF, or via Groq for cloud deployment), a retrieval-augmented orchestration pipeline, a set of deterministic agents, and a React frontend with a polished chat interface.

---

## Features

### Core assistant
- **Domain Q&A** — PPE requirements, inspection checklists, SLA response times, PM schedules, statutory renewals, and more.
- **Document drafting** — memos, vendor emails, incident reports, tenant notices, work orders, compliance summaries (full documents, not just outlines).
- **Contract comparison** — comprehensive vs. non-comprehensive AMCs, SLA tiers, vendor terms.
- **Token-by-token streaming** over Server-Sent Events, with a live step indicator showing what the pipeline is doing.
- **Simple / Thinking modes** — lower temperature for focused answers, higher for exploratory reasoning.

### Retrieval & grounding pipeline
- **Self-describing corpus index** — the corpus (~57 documents) is parsed into structured, schema-versioned facts (vendor, site, system, fees, currency, effective/renewal dates, term). Deterministic extraction is authoritative over the LLM; the index is content-hash gated and committed so it loads instantly on cold start.
- **Hybrid retrieval** — dense (BAAI/bge-small-en-v1.5) + BM25, with an auto-calibrated dense-score gate and site-preference re-ranking.
- **Multi-layer answer grounding** — SLM generation → Groq-based rewriter that grounds claims to context → numeric grounding check → **LLM faithfulness gate** (flags unsupported claims) → grounded recovery that re-synthesises an answer from the retrieved context when a gate fails.
- **Capability registry** — declarative routing rows with deterministic preconditions decide when a query goes to a specialised agent vs. standard retrieval, with guards against misroutes (e.g. budget-variance vs. vendor-decision).
- **Triage** — an instant pre-filter for greetings/meta/adversarial/gibberish, and a scope gate that declines out-of-scope / action / missing-data queries with a helpful best-guess offer.

### Agents (Agents tab)
- **Incident Triage Agent** — classifies an incident, finds the responsible vendor, checks the SLA, and drafts an escalation email.
- **Vendor Comparison Agent** — researches and synthesises a side-by-side comparison, and can hand a follow-up question back into chat.
- **Reminder Agent** — durable, scheduled reminders for renewals, audits, and deadlines (see below).
- **Deterministic compute agents** — budget analysis, portfolio overview, and contract-timeline answers are computed directly from the corpus index facts (rate-limit-proof, no hallucinated numbers).

### Reminder Agent
- Create reminders with a **title, due date, optional time, a system/category dropdown** (HVAC, Electrical, Fire & Life Safety, …, or General), an **optional related vendor**, and notes.
- **Durable storage** in Supabase (survives free-tier container sleeps, unlike diskcache).
- **Immediate confirmation email** on create (so you know it's set and delivery works), plus the **due-date reminder** itself, fired by a daily GitHub Actions cron hitting the backend.
- Emails use the reminder **title as the subject** and lay out every field in a clean table.
- Email via [Resend](https://resend.com); persistence via [Supabase](https://supabase.com).

### UI / UX
- **Categorized command palette** — type `/` or press **⌘K / Ctrl+K** to browse suggested questions grouped by category, with "Instant" badges on pre-cached answers and full keyboard navigation.
- **32 pre-cached suggestions** across 7 FM categories that answer instantly (seeded into the cache at build time — zero runtime cost).
- **Document upload placeholder** — attach PDFs/Word docs via a button or drag-and-drop (visual preview; analysis is a roadmap item).
- **Chat history** with search and date grouping, persisted to localStorage.
- **Dark / light theme**, **scroll-to-latest** control, friendly cold-start/offline error messaging, and a **mobile-responsive** layout (the sidebar becomes an overlay drawer on phones).

---

## Stack

**Backend**
- Python 3.11 + FastAPI, Server-Sent Events for streaming
- [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) — runs the GGUF locally via CPU inference (Groq for cloud)
- [sentence-transformers](https://www.sbert.net/) + BM25 for hybrid retrieval
- [diskcache](https://github.com/grantjenks/python-diskcache) — SQLite-backed response cache with SHA-256 keying
- [Supabase](https://supabase.com) (reminders persistence) + [Resend](https://resend.com) (reminder email)

**Frontend**
- React 18 + Vite, Tailwind CSS (custom dark/light design system)
- Framer Motion for transitions; react-markdown + remark-gfm for rendered responses

**Model**
- Base: Gemma 3 4B — fine-tuned with QLoRA (Unsloth) on facilities-domain instruction pairs
- Format: GGUF Q4_K_M, hosted at [MioA9/gemma3-4b-nexus-qlora-v1](https://huggingface.co/MioA9/gemma3-4b-nexus-qlora-v1)

---

## Running locally

### Prerequisites
- Python 3.11+, Node 18+, ~3 GB free disk (GGUF download on first run)

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# llama-cpp-python needs a prebuilt CPU wheel (no C++ toolchain required)
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
pip install -r requirements.txt

cp .env.example .env         # then edit (HF_TOKEN if the model repo is private)

uvicorn app.main:app --reload
```

The model downloads automatically on first startup. Ready at `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open `http://localhost:5173`.

### Seeding the suggestion cache (recommended)

The suggestion chips and `/` palette answer instantly because they hit a pre-seeded cache:

```bash
cd backend
python -m scripts.seed_suggestion_cache
```

### Enabling the Reminder Agent (optional)

1. Create a Supabase project and run [`backend/sql/reminders_schema.sql`](backend/sql/reminders_schema.sql) in its SQL Editor.
2. Set env vars: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `RESEND_API_KEY`, and `REMINDER_CHECK_SECRET`.
3. For the scheduled due-date emails, set GitHub repo secrets `NEXUS_BACKEND_URL` and `REMINDER_CHECK_SECRET` (the included Actions workflow hits the check endpoint daily).

> **Resend note:** with the default sandbox sender (`onboarding@resend.dev`), Resend only delivers to the address that owns the Resend account. To email arbitrary recipients, verify a domain at resend.com/domains and set `REMINDER_FROM_EMAIL` to an address on it.

---

## Cloud deployment

- **Backend**: Hugging Face Spaces (Docker, port 7860). The GGUF downloads on first boot; the suggestion cache is seeded at build time so chips work on cold start.
- **Frontend**: Vercel (zero-config Vite, auto-deploys from `main`).
- **Cloud inference (free tier)**: route inference to Groq instead of the local GGUF to fit inside free-tier RAM:

```
LLM_BACKEND=groq
GROQ_API_KEY=your_key
GROQ_MODEL=llama-3.1-8b-instant
```

---

## Project structure

```
backend/
  app/
    api/          # FastAPI routes (chat, suggestions, reminders)
    core/         # pipeline, cache, LLM wrapper, retrieval, corpus index,
                  # triage, capabilities, validator, recovery, config
      agents/     # budget, portfolio, timeline, vendor comparison,
                  # incident triage, reminder store + email sender
    prompts/      # system_prompt.md — edit to adjust NEXUS's tone/persona
    schemas/      # Pydantic request/response models
  scripts/        # seed_suggestion_cache, pregenerate_suggestions, seed_demo_reminders
  sql/            # reminders_schema.sql (run once in Supabase)
  data/           # corpus, models (GGUF), cache (diskcache)

frontend/
  src/
    components/   # ChatWindow, ChatInput, MessageBubble, Sidebar, Header,
                  # OptionsPanel, AgentsPage, agents/*
    context/      # ChatHistoryContext, ThemeContext
    hooks/        # useChat, useSuggestions, useReminders
    lib/          # SSE streaming helper

.github/workflows/  # reminder-check.yml — daily cron for due reminders
```

---

## How the system prompt works

NEXUS's persona, formatting rules, and answer style live in `backend/app/prompts/system_prompt.md` — edit it directly, no code changes needed. It controls things like bold key terms, proper Markdown tables, `##`/`###` headings, no emojis, and full documents for writing requests (emails need a subject, greeting, body, and sign-off). The system prompt's live "systems under contract" list is derived from the self-describing corpus index at startup.

---

## Status

Proof-of-concept built during dissertation research.

- **Phase 1 — model fine-tuning:** complete.
- **Phase 2 — app + deployment:** complete; the deployed backend runs the actual fine-tuned GGUF (or Groq), not a stand-in.
- **Phase 3 — agentic workflows:** underway; Incident Triage, Vendor Comparison, and Reminder agents are live, with deterministic compute agents for budget/portfolio/timeline.

It's not production-hardened — no user auth, no multi-tenancy. The point is to demonstrate the domain capability, not scale it.

---

## License

MIT
