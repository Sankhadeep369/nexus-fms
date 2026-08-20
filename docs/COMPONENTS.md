# NEXUS — Component Catalog

A reference to every reusable building block in NEXUS, documented so each can be lifted
out and used **on its own, independent of this project**. For each entry: what it does,
its public interface, what it depends on, and how portable it is.

This is documentation only — no runtime behaviour changes.

## How to read this

**Portability legend**

| | Meaning |
|---|---|
| 🟢 | **Drop-in** — copy the one file; no internal dependencies (only npm/pip packages). |
| 🟡 | **Needs a sibling** — bring along a listed context / lib / util. |
| 🔴 | **Needs the backend** — talks to a NEXUS API endpoint (or a service like Supabase/Groq). |

**Layering.** The most portable assets are the **design tokens**, **`lib/` utilities**, and
**contexts** (self-contained state). UI components sit on top of those. Backend modules are
independent Python units wired together only by `main.py` + the capability registry.

**Stack.** Frontend: React 18 + Vite + Tailwind + Framer Motion + react-markdown.
Backend: FastAPI + SSE, sentence-transformers + BM25, llama-cpp-python / Groq, diskcache,
Supabase, Resend.

---

# 1. Design system (the foundation)

### `frontend/src/index.css` + `tailwind.config` — Design tokens 🟢
CSS-variable theme (`--nexus-bg/panel/panel2/border/text/muted/accent/accent2/violet`) with
light/dark values, exposed to Tailwind as `nexus-*` colours. Also ships helpers: `.aurora`
(animated ambient blobs), `.text-gradient`, `.scroll-thin`, `.shimmer-text`, `.bg-grid`, and
the `font-display` family. Every UI component below is styled with these tokens.
**Reuse:** copy the `:root`/`.light` variable blocks + the Tailwind colour extension to adopt
the whole look; components then theme automatically.

### `frontend/src/components/icons.jsx` — Icon set 🟢
~45 stroke-based SVG icons (`SendIcon`, `SparkleIcon`, `BotIcon`, `PaperclipIcon`,
`CalendarIcon`, `ThumbUpIcon`, `GlobeIcon`, `UploadIcon`, `LogoIcon`, …) sharing one `base`
style object. Each is a plain `(props) => <svg>`.
**Reuse:** copy the file; import only the icons you want. No dependencies.

---

# 2. Frontend — State (React contexts)

Each is a `Provider` + a `use*()` hook, persists to `localStorage`, and has **no internal
dependencies** unless noted.

### `context/ThemeContext.jsx` — `useTheme()` 🟢
`{ theme, toggleTheme }`. Persists dark/light and stamps the root element so CSS can react.

### `context/DensityContext.jsx` — `useDensity()` 🟢
`{ density, setDensity, toggleDensity }` (`comfortable`|`compact`). Scales the root font-size,
so a rem-based UI shrinks together. Purely visual.

### `context/LanguageContext.jsx` — `useLanguage()` 🟢
`{ lang, setLang, t }` + exported `LANGUAGES` (English + 10 international + 10 Indian, each
`{ code, native, dir, group }`). `t(key)` looks up a small UI-string dictionary with English
fallback; sets `document.dir` for RTL. **Reuse:** extend the `STRINGS` map for your own keys.

### `context/ProfileContext.jsx` — `useProfile()` 🟢
`{ profile, saveProfile, signOut }` — an optional, passwordless local profile `{ name, email }`.
Also exports `initials(name)` and `ownerId(profile)` (email, or a stable per-device guest id —
used to scope per-user data).

### `context/ChatHistoryContext.jsx` — `useChatHistory()` 🟢
Full conversation store in `localStorage`: `{ conversations, activeConversation, activeId,
createConversation, selectConversation, deleteConversation, commitMessages, clearAll }`.
Auto-titles a chat from its first user message and buckets by date. **Reuse:** a complete
"chat history sidebar" backend-in-a-file for any chat UI.

### `context/DocumentsContext.jsx` — `useDocuments()` 🔴
`{ owner, documents, uploads, upload(file), remove(id), refresh, dismissUpload }`. Owner-scoped
document management. **Needs** `ProfileContext` (for `ownerId`) and the backend
`/documents` endpoints.

---

# 3. Frontend — Hooks

### `hooks/useChat.js` — chat state machine 🔴🟡
Returns `{ messages, isStreaming, sendMessage, clarify, regenerate, editAndResend,
stopGeneration, sendFeedback, mode, setMode }`. Streams `POST /chat` over SSE, applies the
step/token/done protocol, handles regenerate (optionally in the other mode), edit-and-resend,
clarification chips, friendly cold-start errors, and cache-hit buffering. **Needs**
`ChatHistoryContext`, `ProfileContext`, `lib/sse`, and the `/chat` SSE endpoint.

### `hooks/useSuggestions.js` — suggestion chips 🔴
Returns `[{ text, cached, category }]`. Fetches `/suggestions`; falls back to a built-in list
if offline. **Reuse:** works standalone (fallback) or with the endpoint.

### `hooks/useReminders.js` — reminder CRUD 🔴
`useReminders(email)` → `{ reminders, loading, error, createReminder, updateReminder,
cancelReminder, refresh }`. Talks to `/agents/reminders`.

---

# 4. Frontend — Lib utilities

### `lib/sse.js` — `parseSSEStream(response)` 🟢
Async generator that yields `{ event, data }` from a `fetch` streaming body. Framework-agnostic
Server-Sent-Events parser. **Reuse:** any SSE consumer.

### `lib/calendar.js` — calendar helpers 🟢 / 🔴
`googleCalendarUrl(event)` and `downloadIcs(event)` build a Google Calendar "add event" link and
an `.ics` file from `{ title, date, time, notes }` — **pure client-side, no deps** (🟢).
`extractEvent(text)` asks `POST /calendar/extract` to pull an event from free text (🔴).

---

# 5. Frontend — UI components

## 5.1 Primitives (most reusable)

### `components/CalendarMenu.jsx` — "Add to calendar" dropdown 🟡
Props: `{ getEvent: () => Promise<event|null>, triggerClassName, label }`. Renders a button that,
on click, resolves an event (synchronously for structured data, or via the SLM extractor) and
offers **Google Calendar** + **.ics** download. **Needs** `lib/calendar` + `icons`.

### `components/ThinkingIndicator.jsx` — loading shimmer 🟢
No props. A three-dot / shimmer "thinking" animation (uses `.shimmer-text`). Drop-in.

### `components/WorkflowSteps.jsx` — pipeline step timeline 🟡
Exports `WorkflowStepsLive({ steps })` (live, animated) and `WorkflowStepsDisclosure({ steps,
agentToolCalls })` (collapsible post-hoc). Renders a labelled progress list for a multi-step
backend job. **Needs** `icons`.

### `components/MessageBubble.jsx` — rich chat message 🟡
Props: `{ message, disabled, mode, onRegenerate, onEditResend, onClarify, onFeedback }`. Renders
a user/assistant turn: full **Markdown** (react-markdown + remark-gfm) with themed tables,
**code blocks with copy buttons** (`CodeBlock`), a collapsible **sources panel**
(`SourcesPanel`), clarification chips, error/stopped/validation states, latency, and a hover
toolbar (copy / regenerate / try-in-other-mode / add-to-calendar / 👍👎). **Needs**
`react-markdown`, `remark-gfm`, `CalendarMenu`, `lib/calendar`, `ThinkingIndicator`,
`WorkflowSteps`, `icons`. Internally-defined `CodeBlock`, `SourcesPanel`, and `markdownComponents`
are individually liftable.

## 5.2 Composer & transcript

### `components/ChatInput.jsx` — composer + command palette 🟡
Props: `{ onSend, onStop, isStreaming, mode, onModeChange, prefill, onOpenDocuments }`. Auto-grow
textarea, Simple/Thinking mode toggle, an attach button, and a **categorised slash/⌘K command
palette** (grouped, keyboard-navigable, "Instant" badges) driven by `useSuggestions`. **Needs**
`useSuggestions`, `useLanguage`, `icons`. The palette is a strong standalone pattern.

### `components/ChatWindow.jsx` — transcript + empty state 🟡
Props: `{ messages, onSend, onClarify, onRegenerate, onEditResend, onFeedback, onOpenGuide,
onExample, mode, disabled }`. Scrollable message list (renders `MessageBubble`), auto-follow +
scroll-to-latest, and a rich empty state (greeting, suggestion chips, example starters). **Needs**
`MessageBubble`, `useSuggestions`, `useLanguage`, `icons`.

## 5.3 Shell

### `components/Header.jsx` — top bar 🟡
Props: `{ onToggleSidebar, onToggleOptions, activeTab, onTabChange }`. Logo, backend
online/offline status (polls `/info`), Chat/Agents tabs, Theme + Settings. **Needs** `useTheme`,
`useLanguage`, `icons`.

### `components/Sidebar.jsx` — conversation drawer 🟡
Props: `{ collapsed, onClose, onOpenProfile }`. Searchable, date-bucketed conversation list; an
overlay drawer on mobile, a collapsible rail on desktop; profile footer. **Needs**
`useChatHistory`, `useProfile`, `useLanguage`, `icons`.

## 5.4 Panels & modals (slide-overs)

All use Framer Motion and follow the same backdrop + right-slide pattern — a reusable template.

### `components/OptionsPanel.jsx` — settings 🟡
Props: `{ open, onClose, onOpenGuide }`. Theme, density, language, model info (`/info`), export
chat (.md), clear-all with confirm. **Needs** `useTheme/useDensity/useLanguage/useChatHistory`.

### `components/ProfilePanel.jsx` — account 🟡
Props: `{ open, onClose }`. Create/edit the local profile; sign out. **Needs** `useProfile`.

### `components/DocumentsPanel.jsx` — knowledge-base uploader 🔴
Props: `{ open, onClose }`. Upload (button or drag/drop) with processing/done/error states, and a
document list with delete. **Needs** `useDocuments` (→ backend).

### `components/GuideModal.jsx` — feature walkthrough 🟢
Props: `{ open, onClose }`. Centred modal explaining the app's features. Content lives in a local
`SECTIONS` array — edit for any product. Only needs `framer-motion` + `icons`.

### `components/LanguageMenu.jsx` — language dropdown 🟡
No props (uses `useLanguage`). Grouped globe-button dropdown. (Superseded in-app by the Options
selector, but kept as a standalone.)

## 5.5 Agents tab

### `components/AgentsPage.jsx` — agents layout 🟡
Props: `{ onAskVendorQuestion }`. Composes the three agent cards below.

### `components/agents/IncidentTriageCard.jsx` 🟡
Props: `{ onAsk }`. Input card that hands an incident description to chat.

### `components/agents/VendorComparisonCard.jsx` 🟡
Props: `{ onAsk }`. Input card that hands a vendor-comparison question to chat.

### `components/agents/ReminderAgent.jsx` 🔴
No props. Email-gated reminder manager. **Needs** `useReminders`, `useProfile`, and the two below.

### `components/agents/ReminderForm.jsx` 🟡
Props: `{ onSubmit, initial, onCancel, submitLabel }`. Create/edit form with title, date, optional
time, a **system dropdown**, optional vendor, notes. Works in create and edit modes.

### `components/agents/ReminderList.jsx` 🟡
Props: `{ reminders, onCancel, onUpdate }`. **Tabbed** list (All / Upcoming / Overdue / Sent /
Cancelled) with expand-to-view, inline edit, delete, and per-item "Add to calendar". **Needs**
`CalendarMenu`, `ReminderForm`, `icons`.

---

# 6. Backend — API endpoints (FastAPI routers)

Each router in `app/api/` is self-contained; register with `app.include_router(...)`.

| Router | Endpoints | Purpose |
|---|---|---|
| `api/chat.py` | `POST /chat` (SSE) | Streams the orchestrated answer. Body: `{query, mode, history, owner, bypass_cache}`. |
| `api/suggestions.py` | `GET /suggestions` | Curated questions + cached/category flags. |
| `api/reminders.py` | `POST/GET/DELETE /agents/reminders`, `PATCH /{id}`, `GET /check` | Reminder CRUD + cron-triggered email check. |
| `api/feedback.py` | `POST /feedback` | 👍/👎 logging (best-effort). |
| `api/calendar.py` | `POST /calendar/extract` | SLM event extraction from text. |
| `api/documents.py` | `POST/GET/DELETE /documents` | Upload → ingest → persist; list; delete. |

Request/response shapes live in `app/schemas/` (`chat.py`, `reminders.py`) as Pydantic models.

---

# 7. Backend — Orchestration core

### `core/chat_pipeline.py` — `ChatPipeline.run()` 🔴
The orchestrator generator: Layer-A triage → cache → query analysis → Layer-B scope gate →
agent dispatch **or** retrieval + SLM generation → grounding/rewrite → faithfulness gate →
grounded recovery. Emits the `step`/`token`/`done` SSE protocol. Also owns user-doc precedence
(`_prefer_user_docs`) and context assembly (`_build_user_content`). Wires everything else.

### `core/query_processor.py` — `preprocess()` 🔴
Groq-backed classifier → `ProcessedQuery` (type, rewritten query, entities, in_scope,
action/missing-data flags, clarification). The routing brain.

### `core/capabilities.py` — capability registry 🟢
Declarative `QueryCapability` rows (retrieval strategy, k, token budget, agent binding) +
`passes_agent_precondition()` deterministic guards + `is_temporal_query`. **Reuse:** a clean
pattern for registry-driven routing.

### `core/triage.py` — fast lanes 🟢
`pre_filter()` (instant canned answers for greetings/meta/adversarial/gibberish),
`compose_decline()` (honest scope decline + best-guess), `is_action_request`, `is_draft_request`.
Regex + templates, no model calls.

### `core/validator.py` — grounding gates 🔴
`validate_and_rewrite()` (Groq rewriter that grounds claims), `check_faithfulness()` (flags
unsupported claims), `_rule_check`, `_numeric_grounding_check`. The trust layer.

### `core/recovery.py` — grounded recovery 🔴
Re-synthesises an answer from retrieved context (Groq) when a gate fails, so the user gets a
grounded reply instead of a hallucination.

### `core/verify.py` — `verify_answer()` 🟢
Deterministic post-checks (table/number consistency) on a generated answer.

### `core/cache.py` — `ResponseCache` 🟢
Storage-agnostic response cache; `DiskResponseCache` (SQLite via diskcache), SHA-256 keyed by
query+mode. Swap the backend without touching the pipeline.

### `core/config.py` — `Settings` 🟢
Pydantic-settings central config (model source, retrieval knobs, feature flags, doc/limits,
Supabase/Resend/Groq creds). One import for all tunables.

### `core/llm.py` — `get_llm()` 🔴
Loads the local GGUF via llama-cpp-python, or routes to a remote HF/Groq endpoint. Uniform
`stream_chat(messages, temperature, max_tokens)` interface.

---

# 8. Backend — Retrieval & knowledge

### `core/retrieval.py` — hybrid retriever 🟡
`Retriever` (BM25 + dense bge-small, min-max blend, auto-calibrated dense gate, cross-encoder
rerank) and `EntityAwareRetriever` (entity-anchored). Owner-scoped `retrieve(query, k, owner)`,
runtime `add_documents()`, shared `get_embedder()`, `add_user_documents()`,
`rehydrate_user_documents()`. **Reuse:** a self-contained in-memory hybrid RAG index.

### `core/corpus_index.py` — self-describing facts 🟢
Parses the corpus into schema-versioned, content-hash-gated structured facts (vendor, site,
system, fees, currency, dates, term) with deterministic extraction authoritative over the LLM.
Powers the deterministic agents + doc-class labels.

### `core/entity_registry.py` — entity → doc matching 🟢
Maps vendor/agreement/site mentions in a query to the owning corpus document (drives entity-aware
retrieval).

### `core/suggestions.py` + `suggestion_answers.py` — curated Q&A 🟢
32 categorised starter questions + hand-written answers, seeded into the cache at build time for
instant responses.

---

# 9. Backend — Agents

Each `core/agents/*.py` is a focused unit invoked by the pipeline via the capability registry.

| Agent | Entry point | What it does |
|---|---|---|
| `budget_analysis_agent.py` | `run_budget_analysis()` | Computes all aggregations (system/site/vendor/total/projection) in Python, then a grounded LLM answers the *specific* question — never invents figures. |
| `portfolio_overview_agent.py` | `run_portfolio_overview()` | Portfolio table from corpus_index facts. |
| `contract_timeline_agent.py` | — | Renewal/expiry timing computed deterministically. |
| `vendor_comparison_agent.py` | `run_vendor_comparison_agent()`, `synthesize_comparison()` | Researches current + competitor contracts via targeted tool calls, synthesises a side-by-side. |
| `incident_triage_agent.py` | `run_incident_triage()` | Classify → find vendor → check SLA → draft escalation email (title-as-subject, no "Unknown"). |
| `immediate_actions.py` | `detect_incident_action()`, `build_immediate_actions()` | Occupant safety steps for "what do we do?" follow-ups — LLM-first + curated fallback, vendor-free. |
| `reminder_agent.py` | `check_and_send_due_reminders()` | The daily-cron sender. |
| `email_sender.py` | `send_reminder_email()`, `send_reminder_confirmation_email()` | Resend HTML email (shared `_send`). 🔴 |
| `_common.py` | `provenance_chunks()` | Shared provenance helper for the compute agents. |
| `agents/tools.py` | `_rank_chunks_in_docs()`, … | Targeted retrieval tools used by the agents. |

---

# 10. Backend — Ingestion & persistence

### `core/ingest.py` — document ingestion 🔴
`extract_text` (pypdf / python-docx / **Tesseract OCR** fallback) → `chunk_text` (paragraph-aware)
→ `summarize_doc` + **batched** per-chunk `enrich_chunks` (Groq) → embed. `ingest_document()`
returns chunks ready to persist and index. Decoupled from retrieval, so it never affects chat
timing.

### Persistence stores (Supabase) 🔴
- `core/document_store.py` — `DocumentStore`: docs + chunks (JSON embeddings), per-owner list/delete,
  `all_chunks()` for startup rehydrate.
- `core/agents/reminder_store.py` — `ReminderStore`: durable reminders (create/list/update/cancel/find_due),
  graceful column-migration fallback.
- `core/feedback_store.py` — `FeedbackStore`: append-only 👍/👎 log.

Schemas to create these tables live in `backend/sql/` (`reminders_schema.sql`, `feedback_schema.sql`,
`documents_schema.sql`).

---

# 11. Reuse recipes

**"Just the chat UI."** Take the design tokens + `icons` + `ThemeContext` +
`ChatHistoryContext` + `ProfileContext` + `lib/sse` + `useChat` + `ChatWindow` + `ChatInput` +
`MessageBubble` (+ `ThinkingIndicator`, `WorkflowSteps`). Point `useChat` at any SSE `/chat`
endpoint that speaks the `step`/`token`/`done` protocol.

**"Just the command palette."** `ChatInput`'s slash/⌘K palette + `useSuggestions` — a
categorised, keyboard-navigable picker for any input.

**"Just the RAG engine."** `core/retrieval.py` + `core/corpus_index.py` + `core/cache.py` +
`core/config.py`. In-memory hybrid BM25+dense with reranking, a dense relevance gate, and a
runtime `add_documents` for user uploads.

**"Just the grounding gates."** `core/validator.py` + `core/recovery.py` + `core/verify.py` —
drop into any RAG pipeline to rewrite-ground answers, fact-check them, and recover on failure.

**"Just document ingestion."** `core/ingest.py` + `core/document_store.py` (+ the Dockerfile's
`tesseract-ocr`/`poppler-utils`). Parse/OCR → chunk → enrich → embed → persist.

**"Just reminders/calendar/feedback."** Each is a self-contained slice: an API router + a store
(+ for reminders, the `email_sender` and the GitHub Actions cron) on the backend, and the
matching hook/panel on the frontend.

**"Just the design system."** The `index.css` token block + Tailwind colour extension + the
`icons.jsx` set + the slide-over panel pattern (see `OptionsPanel`) — adopt the whole look.
