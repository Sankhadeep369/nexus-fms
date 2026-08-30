---
name: NEXUS
description: Facilities-management AI assistant — a calm, technical operations console
colors:
  bg: "#080B0F"
  panel: "#0E1218"
  panel-2: "#151A22"
  border: "#232A35"
  text: "#EBEFF4"
  muted: "#8E99A8"
  accent: "#2DD4BF"
  accent-2: "#F59E0B"
  violet: "#A78BFA"
  bg-light: "#FAFBFC"
  panel-light: "#FFFFFF"
  text-light: "#161B20"
  accent-light: "#0D9488"
typography:
  display:
    fontFamily: "Archivo, Hanken Grotesk, system-ui, sans-serif"
    fontSize: "clamp(1.05rem, 1rem + 0.6vw, 1.35rem)"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Hanken Grotesk, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "Hanken Grotesk, system-ui, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 600
    letterSpacing: "0.06em"
rounded:
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.bg}"
    rounded: "{rounded.md}"
    padding: "8px 14px"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "6px 12px"
  card:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text}"
    rounded: "{rounded.xl}"
    padding: "20px"
  input:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    padding: "6px 10px"
---

## Overview

NEXUS is an **Operate**-mode product: a facilities-management console where the visitor completes tasks (ask, triage, analyse, track KPIs, administer). Scanability, consistency and native expectations outrank expression; brand lives in precise details, not decoration. The felt quality is a **calm, technical operations room** — a cool slate-black canvas, one confident teal action color, amber for warmth/warnings, and a restrained violet reserved for AI/agent surfaces. Theme-aware: every token has a light-mode value; nothing is hard-coded to one theme.

## Colors

All colors are CSS variables stored as `R G B` triples and consumed via `rgb(var(--nexus-*) / <alpha>)`, so opacity is always available and theming is a variable swap (`.light` class on the root).

- `accent` (teal `#2DD4BF`, light `#0D9488`) — the single primary action/identity color. Buttons, active tabs, focus, links, sparklines.
- `accent-2` (amber `#F59E0B`) — warmth and warnings: at-risk KPIs, announcement banners, the secondary gradient stop on the hero only.
- `violet` (`#A78BFA`) — **reserved** for AI/agent context (Agents tab active state, workflow step chips). Do not use as a general accent.
- `bg / panel / panel-2 / border` — the four-step neutral elevation ramp.
- `text / muted` — foreground pair; `muted` for secondary/labels.
- Status: emerald `#10B981` (on target), amber (at risk), red `#EF4444` (off target/destructive).

Admins can override `accent` at runtime (branding); keep contrast in mind — the token must stay legible as button text-on-fill in both themes.

## Typography

- **Display — Archivo** (600–800): headings, KPI numbers, wordmark, tab labels. Engineered, slightly technical; signals an operations tool, not a generic SaaS. Use `font-display`, tight tracking (`-0.01em`).
- **Body — Hanken Grotesk** (400–600): all running text, inputs, controls. Set on `body`; inherited everywhere.
- **Label**: 11px, weight 600, uppercase, `0.06em` tracking, `muted` color — section headers ("NEEDS ATTENTION", "SUGGESTED").
- Numeric/metric emphasis uses Archivo weight 600, not a gradient. One display + one body face only; do not add more.

## Layout

- App shell: fixed 56px header, optional announcement strip, then a flex row of sidebar + main. Main surfaces scroll internally (`scroll-thin`), the page body never scrolls horizontally.
- Content max-widths by surface: chat full-bleed, Analysis `max-w-5xl`, Dashboard `max-w-6xl`, forms `max-w-2xl/3xl`.
- Grids: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3` for card collections. Wide content (charts, tables, diagrams) lives in its own `overflow-x-auto` container.
- Mobile: sidebar becomes an overlay drawer; the right-hand chat assist panel is `hidden lg:flex` and collapsible.

## Elevation & Depth

- Four-step surface ramp: `bg` → `panel` → `panel-2` → `border` hairlines. Cards sit on `panel` with a 1px `border` outline, not heavy shadows.
- Signature glow: `shadow-glow` / `shadow-glow-sm` (teal-tinted) on primary buttons and hover, used sparingly.
- Ambient `aurora` (soft teal/amber radial blur) behind the shell and login, plus a subtle 28px dot-grid on canvases. A lazy-loaded **three.js hero object** (rotating point-cloud/wireframe "systems" motif) is allowed on the login/first-run surface only — it must respect `prefers-reduced-motion`, cap DPR, pause when hidden, and never load on the chat/work path.

## Shapes

- Radius language is soft-rectangular: `sm 8px` inputs/chips, `md 12px` buttons/menus, `xl 24px` cards and modals, `full` for pills, dots and avatars.
- Icons: single-weight line icons (1.5–2px stroke), 14–16px in controls. No filled/duotone icon mixing.

## Components

- **button-primary**: teal fill, `bg`-colored text, `md` radius, `glow-sm` on hover, `active:scale-95`. The one loud element per view.
- **card**: `panel` bg, `border` outline, `xl` radius, 16–20px padding. The default container.
- **input/select/textarea**: `bg` fill, `border` outline, teal focus border; multi-line content uses auto-growing textareas so text never scrolls sideways.
- **tabs**: pill row in `panel-2`; active tab teal (violet for Agents). Personal "Home" always present; the rest gated by permission + feature flag.
- **status dot**: 2.5px filled circle in emerald/amber/red/muted with a tooltip; the compact form of any state.
- **modal**: centered, `xl` radius, `bg-black/50` backdrop with blur, close affordance top-right.

## Do's and Don'ts

- **Do** keep one primary action color (teal); reserve violet for AI/agents and amber for warnings.
- **Do** use solid color for text and metrics.
- **Do** hide advanced fields behind disclosures; lead non-technical users with dates/pickers, not format strings.
- **Do** give every async action a loading and error state; prefer in-app messaging over native `alert/confirm` for anything reversible-with-consequence.
- **Don't** use gradient-clipped text (`background-clip: text`) for headings/metrics — it reads as AI slop.
- **Don't** reintroduce Inter, Roboto, Geist, Fraunces, Plus Jakarta Sans or Space Grotesk — they converge with generic AI UIs.
- **Don't** add a third typeface, a second loud accent, or decoration that doesn't encode state.
- **Don't** let the three.js hero or any effect run on the chat/work surfaces or block first input.
