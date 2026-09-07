
# NEXUS — AI Assistant

NEXUS is a domain-specific AI assistant built for facilities management teams. It answers operational questions — maintenance schedules, compliance checklists, vendor contract comparisons, SLA benchmarks, safety drills — that would otherwise require digging through binders or tracking down the right person.

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

### Issue Analysis (Analysis tab)
- **Structured root-cause analysis** — 5 Whys, Ishikawa (fishbone), Fault Tree (FTA), and RCA reports, generated as editable structured output and rendered with clean HTML/CSS + SVG.
- **CAPA** — one-click corrective & preventive actions from the identified root causes.
- Optional **grounding** on uploaded documents; Markdown export; local history. Endpoints: `POST /analysis/generate`, `POST /analysis/capa`.

### KPI Dashboard (Dashboard tab)
- **Track facilities KPIs against targets** with R/A/G status, warning thresholds, trend sparklines, line/bar charts, and per-KPI stats.
- **Live cards auto-derived** from your data — reminder compliance %, overdue/upcoming counts, answer-approval — via `GET /kpis/derived`.
- **12 FM templates**, custom KPIs, calendar-date entry (auto-bucketed by period), CSV import/export, a **"Needs attention"** strip, a printable report, and **one-click breach logging** (System / Compliance).

### Home (personal canvas)
- A per-user **drag-and-drop widget canvas** (greeting, shortcuts, KPI tiles, notes) — move/resize in Customize mode; layout saved per user. Hand-rolled pointer drag/resize, no drag library.

### Access control & admin
- **Optional login** — sign in, or **continue as a guest** (full everyday tools; admin locked). Seeded admin: `admin` / `admin123`.
- **Role-based access** — admins create users and toggle per-user access to tools, agents, and reminder create/manage rights (role presets + fine-tuning).
- **Admin settings** — branding (name/accent), announcement banner, global feature toggles, config **snapshots & rollback**, full **backup/restore** (export/import all data as JSON), and an **audit log**.
- Knowledge-base document upload is an **admin-only** privilege that updates the shared corpus for every user.

### Help & onboarding
- A **Help Center** with per-agent/use-case tutorials (from the `?` icon and contextual `i` icons), a first-run **guided tour** (coach-marks), and a **getting-started checklist** on Home.

### UI / UX
- **Categorized command palette** — type `/` or press **⌘K / Ctrl+K** to browse suggested questions, with "Instant" badges on pre-cached answers and full keyboard navigation.
- **Pre-cached suggestions** across FM categories that answer instantly (seeded at build time — zero runtime cost).
- **Chat history** with search and date grouping (localStorage); a collapsible right-hand **suggestions & rating** panel.
- **Design system** — documented tokens in [DESIGN.md](DESIGN.md); Archivo + Hanken Grotesk with JetBrains Mono for metrics; a lazy-loaded three.js login hero. Dark / light theme, mobile-responsive (sidebar → overlay drawer), and an accessibility pass (keyboard-dismissible dialogs, in-app confirmations instead of native popups).

> **Note on persistence:** users, KPIs, admin config, Home layouts, chats and the audit log are currently stored in the browser's **localStorage** (per-device). Reminders, feedback and uploaded documents persist server-side in Supabase. A shared/server-backed store for the rest is the planned next step.

---

## Stack

**Backend**
- Python 3.11 + FastAPI, Server-Sent Events for streaming
- [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) — runs the GGUF locally via CPU inference (Groq for cloud)
- [sentence-transformers](https://www.sbert.net/) + BM25 for hybrid retrieval
- [diskcache](https://github.com/grantjenks/python-diskcache) — SQLite-backed response cache with SHA-256 keying
- [Supabase](https://supabase.com) (reminders, answer feedback, uploaded documents) + [Resend](https://resend.com) (reminder email)

**Frontend**
- React 18 + Vite, Tailwind CSS (custom dark/light design system — see [DESIGN.md](DESIGN.md))
- Framer Motion for transitions; react-markdown + remark-gfm for rendered responses
- three.js (lazy-loaded 3D login hero); hand-rolled SVG charts (no chart library)

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

## Feature walkthrough — reproduce each functionality

With the backend and frontend running (above), each feature is reachable from the top tabs / account menu:

| Feature | How to reproduce | Backend touched |
|---|---|---|
| **Guest vs. login** | On the login card, click the **×** or "Continue without signing in" for guest access; or sign in as `admin` / `admin123` for the Admin tab. | none (localStorage) |
| **Chat** | Ask an FM question (e.g. *"What's the SLA response time in the Apex HVAC contract?"*). Toggle Simple/Thinking; open the reference tile to see sources. | `POST /chat` (SSE) |
| **Agents** | Agents tab → Incident Triage (describe an incident), Vendor Comparison, Reminder (set an email, create a reminder). A follow-up opens in a **new chat thread**. | `/chat`, `/reminders` |
| **Analysis (RCA)** | Analysis tab → pick a method, enter an issue, Analyse; edit the result; "Suggest actions" for CAPA; Export / Save. | `POST /analysis/generate`, `/analysis/capa` |
| **KPI Dashboard** | Dashboard tab → "Add KPI" (template or custom), open a card to add a value by date, watch status/trend; "Log breach"; "Report"; CSV import/export. Live cards appear once a profile email is set. | `GET /kpis/derived` |
| **Home canvas** | Home tab → "Customize" → drag/resize widgets, "Add widget", "Done". Layout persists per user. | none |
| **Knowledge base (admin)** | As admin, the chat paperclip / drag-drop uploads docs to the shared corpus (owner `global`); every user's chat then retrieves them. | `POST /documents` |
| **Admin & settings** | Admin tab → Users (create/edit/delete, permission toggles) and Settings (branding, announcement, feature flags, snapshots/rollback, backup/restore, audit log). | none |
| **Help & onboarding** | `?` icon → Help Center; contextual `i` on agent cards; first-run guided tour; Home getting-started checklist. | `GET /suggestions` |

Everything except reminders, feedback and documents runs client-side, so most features are reproducible with the frontend alone (`npm run dev`) pointed at any running backend.

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

Began as dissertation research; now being built toward a client-usable product.

- **Phase 1 — model fine-tuning:** complete.
- **Phase 2 — app + deployment:** complete; the deployed backend runs the actual fine-tuned GGUF (or Groq), not a stand-in.
- **Phase 3 — agentic workflows + product surface:** live — Incident Triage, Vendor Comparison, and Reminder agents plus deterministic budget/portfolio/timeline agents; Analysis (RCA), KPI Dashboard, Home canvas, Help Center, and an admin/access layer.

**Known limitations (honest):**
- **Access control and most app data (users, KPIs, config, layouts, chats) are client-side (localStorage)** — a UI-level gate, not yet server-enforced or shared across devices. The planned next step is a shared backend store + enforced auth.
- **Response time** on the free HF `cpu-basic` tier is gated by CPU SLM inference (fresh generations are slow; cached/suggestion answers are instant). Orchestration (Groq) is sub-second. A GPU tier is the lever for faster fresh answers.

---

## License

MIT
