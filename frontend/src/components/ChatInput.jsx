import { useEffect, useRef, useState } from "react";
import { useSuggestions } from "../hooks/useSuggestions";
import { SendIcon, SparkleIcon, StopIcon, ZapIcon } from "./icons";

const MAX_TEXTAREA_HEIGHT = 200;

const MODES = [
  { id: "simple", label: "Simple", icon: ZapIcon, title: "Lower temperature -- faster, focused answers" },
  { id: "thinking", label: "Thinking", icon: SparkleIcon, title: "Higher temperature -- more exploratory reasoning" },
];

export default function ChatInput({ onSend, onStop, isStreaming, mode, onModeChange, prefill }) {
  const [value, setValue] = useState("");
  const [highlight, setHighlight] = useState(0);
  const textareaRef = useRef(null);
  const suggestions = useSuggestions();

  // Agents tab can hand off a draft question (e.g. "Should we renew with X?")
  // -- populate the input and focus it so the user can review/edit before sending.
  useEffect(() => {
    if (!prefill) return;
    setValue(prefill.text);
    requestAnimationFrame(() => {
      resize(textareaRef.current);
      textareaRef.current?.focus();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill]);

  const slashFilter = value.startsWith("/") ? value.slice(1).trim().toLowerCase() : null;
  const slashMatches =
    slashFilter === null
      ? []
      : suggestions.filter((s) => s.text.toLowerCase().includes(slashFilter));
  const showSlashMenu = slashFilter !== null && !isStreaming && slashMatches.length > 0;

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
    <div className="relative z-10 border-t border-nexus-border bg-nexus-panel/80 p-3 backdrop-blur-sm">
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
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="relative mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-nexus-border bg-nexus-bg px-2 py-2 transition-colors focus-within:border-nexus-accent/60 focus-within:shadow-glow-sm">
        {showSlashMenu && (
          <div className="scroll-thin absolute bottom-full left-0 right-0 mb-2 max-h-64 overflow-y-auto rounded-xl border border-nexus-border bg-nexus-panel p-1 shadow-lg">
            {slashMatches.map((s, i) => (
              <button
                key={s.text}
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault();
                  selectSuggestion(s.text);
                }}
                onMouseEnter={() => setHighlight(i)}
                className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm transition-colors ${
                  i === Math.min(highlight, slashMatches.length - 1)
                    ? "bg-nexus-panel2 text-nexus-text"
                    : "text-nexus-muted hover:bg-nexus-panel2 hover:text-nexus-text"
                }`}
              >
                {s.cached ? (
                  <ZapIcon className="h-3.5 w-3.5 shrink-0 text-nexus-accent2" />
                ) : (
                  <SparkleIcon className="h-3.5 w-3.5 shrink-0 text-nexus-accent" />
                )}
                <span className="truncate">{s.text}</span>
              </button>
            ))}
          </div>
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
                selectSuggestion(slashMatches[Math.min(highlight, slashMatches.length - 1)].text);
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
          placeholder="Message NEXUS... (/ for suggestions)"
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
      <p className="mx-auto mt-1.5 max-w-3xl px-1 text-[11px] text-nexus-muted">
        NEXUS can make mistakes. Double-check important details.
      </p>
    </div>
  );
}
