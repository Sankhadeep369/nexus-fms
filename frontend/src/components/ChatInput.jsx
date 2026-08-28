import { useEffect, useRef, useState } from "react";
import { useLanguage } from "../context/LanguageContext";
import { useSuggestions } from "../hooks/useSuggestions";
import {
  CommandIcon,
  CornerDownLeftIcon,
  PaperclipIcon,
  SendIcon,
  SparkleIcon,
  StopIcon,
  ZapIcon,
} from "./icons";

const MAX_TEXTAREA_HEIGHT = 200;

const MODES = [
  { id: "simple", label: "Simple", icon: ZapIcon, title: "Lower temperature -- faster, focused answers" },
  { id: "thinking", label: "Thinking", icon: SparkleIcon, title: "Higher temperature -- more exploratory reasoning" },
];

// Turns the flat (already category-ordered) match list into render rows,
// inserting a header row whenever the category changes. Each item row keeps
// its flat index so keyboard highlighting stays a single running counter.
function toPaletteRows(matches) {
  const rows = [];
  let lastCategory = null;
  matches.forEach((s, flatIndex) => {
    const category = s.category ?? "Suggestions";
    if (category !== lastCategory) {
      rows.push({ type: "header", category });
      lastCategory = category;
    }
    rows.push({ type: "item", suggestion: s, flatIndex });
  });
  return rows;
}

export default function ChatInput({ onSend, onStop, isStreaming, mode, onModeChange, prefill, onOpenDocuments, showDocuments = true }) {
  const [value, setValue] = useState("");
  const [highlight, setHighlight] = useState(0);
  const [justArrived, setJustArrived] = useState(false);
  const textareaRef = useRef(null);
  const activeItemRef = useRef(null);
  const suggestions = useSuggestions();
  const { t } = useLanguage();

  // Cmd/Ctrl+K opens the suggestion palette from anywhere (not just typing "/"),
  // matching modern command-palette conventions.
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setValue((v) => (v.startsWith("/") ? v : "/"));
        setHighlight(0);
        requestAnimationFrame(() => textareaRef.current?.focus());
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Agents tab can hand off a draft question (e.g. "Should we renew with X?")
  // -- populate the input, focus it, and briefly glow the input box so it's
  // obvious something just arrived and is ready to review/edit before sending.
  useEffect(() => {
    if (!prefill) return;
    // Agents hand off in a fresh conversation and want the question answered
    // immediately, not just dropped into the composer for review.
    if (prefill.autoSend) {
      onSend(prefill.text);
      return;
    }
    setValue(prefill.text);
    setJustArrived(true);
    requestAnimationFrame(() => {
      resize(textareaRef.current);
      textareaRef.current?.focus();
      textareaRef.current?.select();
    });
    const timer = setTimeout(() => setJustArrived(false), 2200);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill]);

  const slashFilter = value.startsWith("/") ? value.slice(1).trim().toLowerCase() : null;
  const slashMatches =
    slashFilter === null
      ? []
      : suggestions.filter((s) => s.text.toLowerCase().includes(slashFilter));
  const showSlashMenu = slashFilter !== null && !isStreaming && slashMatches.length > 0;
  const activeIndex = Math.min(highlight, Math.max(slashMatches.length - 1, 0));
  const paletteRows = showSlashMenu ? toPaletteRows(slashMatches) : [];

  // Keep the highlighted palette item scrolled into view during arrow-key nav.
  useEffect(() => {
    activeItemRef.current?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, showSlashMenu]);

  const resize = (el) => {
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT)}px`;
  };

  const submit = () => {
    if (!value.trim() || isStreaming) return;
    onSend(value);
    setValue("");
    requestAnimationFrame(() => resize(textareaRef.current));
  };

  const selectSuggestion = (text) => {
    onSend(text);
    setValue("");
    requestAnimationFrame(() => resize(textareaRef.current));
  };

  return (
    <div data-tour="composer" className="relative z-10 border-t border-nexus-border bg-nexus-panel/80 p-3 backdrop-blur-sm">
      <div className="mx-auto mb-1.5 flex max-w-3xl items-center gap-1 px-1">
        <div className="inline-flex items-center gap-0.5 rounded-full border border-nexus-border bg-nexus-panel2 p-0.5">
          {MODES.map(({ id, label, icon: Icon, title }) => (
            <button
              key={id}
              type="button"
              onClick={() => onModeChange?.(id)}
              title={title}
              aria-pressed={mode === id}
              className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                mode === id
                  ? "bg-gradient-to-br from-nexus-accent to-nexus-accent2 text-nexus-bg"
                  : "text-nexus-muted hover:text-nexus-text"
              }`}
            >
              <Icon className="h-3 w-3" />
              {t(`mode_${id}`) ?? label}
            </button>
          ))}
        </div>
      </div>
      {justArrived && (
        <p className="mx-auto mb-1.5 max-w-3xl px-1 text-[11px] font-medium text-nexus-violet">
          Ready to send — review or edit, then press Enter.
        </p>
      )}
      <div
        className={`relative mx-auto flex max-w-3xl flex-col rounded-2xl border bg-nexus-bg px-2 py-2 transition-all focus-within:border-nexus-accent/60 focus-within:shadow-glow-sm ${
          justArrived ? "border-nexus-violet shadow-glow-sm" : "border-nexus-border"
        }`}
      >
        {showSlashMenu && (
          <div className="scroll-thin absolute bottom-full left-0 right-0 mb-2 max-h-72 overflow-y-auto rounded-xl border border-nexus-border bg-nexus-panel shadow-lg">
            <div className="flex items-center justify-between border-b border-nexus-border px-3 py-2">
              <span className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-nexus-muted">
                <CommandIcon className="h-3.5 w-3.5" />
                Suggested questions
              </span>
              <span className="text-[11px] text-nexus-muted">
                {slashMatches.length} match{slashMatches.length === 1 ? "" : "es"}
              </span>
            </div>
            <div className="p-1" role="listbox" id="suggestion-listbox" aria-label="Suggested questions">
              {paletteRows.map((row) =>
                row.type === "header" ? (
                  <div
                    key={`h-${row.category}`}
                    role="presentation"
                    className="px-2.5 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-nexus-muted/80"
                  >
                    {row.category}
                  </div>
                ) : (
                  <button
                    key={row.suggestion.text}
                    ref={row.flatIndex === activeIndex ? activeItemRef : null}
                    type="button"
                    role="option"
                    id={`suggestion-${row.flatIndex}`}
                    aria-selected={row.flatIndex === activeIndex}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      selectSuggestion(row.suggestion.text);
                    }}
                    onMouseEnter={() => setHighlight(row.flatIndex)}
                    className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm transition-colors ${
                      row.flatIndex === activeIndex
                        ? "bg-nexus-panel2 text-nexus-text"
                        : "text-nexus-muted hover:bg-nexus-panel2 hover:text-nexus-text"
                    }`}
                  >
                    {row.suggestion.cached ? (
                      <ZapIcon className="h-3.5 w-3.5 shrink-0 text-nexus-accent2" />
                    ) : (
                      <SparkleIcon className="h-3.5 w-3.5 shrink-0 text-nexus-accent" />
                    )}
                    <span className="flex-1 truncate">{row.suggestion.text}</span>
                    {row.suggestion.cached && (
                      <span className="shrink-0 rounded bg-nexus-accent2/10 px-1.5 py-0.5 text-[10px] font-medium text-nexus-accent2">
                        Instant
                      </span>
                    )}
                  </button>
                )
              )}
            </div>
            <div className="flex items-center gap-3 border-t border-nexus-border px-3 py-1.5 text-[10px] text-nexus-muted">
              <span className="flex items-center gap-1">
                <kbd className="rounded bg-nexus-panel2 px-1 font-mono">↑</kbd>
                <kbd className="rounded bg-nexus-panel2 px-1 font-mono">↓</kbd>
                navigate
              </span>
              <span className="flex items-center gap-1">
                <CornerDownLeftIcon className="h-3 w-3" /> select
              </span>
              <span className="flex items-center gap-1">
                <kbd className="rounded bg-nexus-panel2 px-1 font-mono">esc</kbd> dismiss
              </span>
            </div>
          </div>
        )}

        <div className="flex items-end gap-1.5">
          {showDocuments && (
            <button
              type="button"
              onClick={onOpenDocuments}
              title="Knowledge base — upload documents (admin)"
              aria-label="Knowledge base"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-nexus-border bg-nexus-panel2 text-nexus-muted transition-all hover:border-nexus-accent/60 hover:text-nexus-accent active:scale-95"
            >
              <PaperclipIcon className="h-4 w-4" />
            </button>
          )}
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              setHighlight(0);
              resize(e.target);
            }}
            onKeyDown={(e) => {
              if (showSlashMenu) {
                if (e.key === "ArrowDown") {
                  e.preventDefault();
                  setHighlight((h) => (h + 1) % slashMatches.length);
                  return;
                }
                if (e.key === "ArrowUp") {
                  e.preventDefault();
                  setHighlight((h) => (h - 1 + slashMatches.length) % slashMatches.length);
                  return;
                }
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  selectSuggestion(slashMatches[activeIndex].text);
                  return;
                }
                if (e.key === "Escape") {
                  e.preventDefault();
                  setValue("");
                  return;
                }
              }
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            rows={1}
            placeholder={`${t("input_placeholder")}  ( / · ⌘K )`}
            role="combobox"
            aria-expanded={showSlashMenu}
            aria-controls="suggestion-listbox"
            aria-activedescendant={showSlashMenu ? `suggestion-${activeIndex}` : undefined}
            className="flex-1 resize-none bg-transparent px-2 py-1.5 text-sm leading-relaxed text-nexus-text placeholder:text-nexus-muted focus:outline-none"
            style={{ maxHeight: MAX_TEXTAREA_HEIGHT }}
          />
          {isStreaming ? (
            <button
              type="button"
              onClick={onStop}
              aria-label="Stop generating"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-nexus-border bg-nexus-panel2 text-nexus-text transition-all hover:border-nexus-accent2/60 hover:text-nexus-accent2 active:scale-95"
            >
              <StopIcon className="h-3.5 w-3.5" />
            </button>
          ) : (
            <button
              type="button"
              onClick={submit}
              disabled={!value.trim()}
              aria-label="Send message"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-nexus-accent to-nexus-accent2 text-nexus-bg transition-all hover:shadow-glow-sm active:scale-95 disabled:opacity-30 disabled:shadow-none"
            >
              <SendIcon className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
      <p className="mx-auto mt-1.5 max-w-3xl px-1 text-[11px] text-nexus-muted">
        NEXUS can make mistakes. Double-check important details.
      </p>
    </div>
  );
}
