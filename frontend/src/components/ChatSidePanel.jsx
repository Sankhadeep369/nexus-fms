import { useEffect, useState } from "react";
import { useSuggestions } from "../hooks/useSuggestions";
import { CheckIcon, SparkleIcon, ThumbDownIcon, ThumbUpIcon, XIcon } from "./icons";

const COLLAPSE_KEY = "nexus-chat-panel-collapsed";

function Rating({ target, onFeedback }) {
  const [rating, setRating] = useState(null);
  const [comment, setComment] = useState("");
  const [sent, setSent] = useState(false);

  // Reset when the answer being rated changes.
  useEffect(() => {
    setRating(null);
    setComment("");
    setSent(false);
  }, [target?.id]);

  if (!target) return <p className="text-xs text-nexus-muted">Ask something, then rate the answer here.</p>;

  const pick = (r) => {
    setRating(r);
    onFeedback(target.id, r);
  };
  const submitComment = () => {
    if (!rating) return;
    onFeedback(target.id, rating, comment.trim());
    setSent(true);
  };

  return (
    <div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => pick("up")}
          className={`flex h-8 w-8 items-center justify-center rounded-lg border transition-colors ${rating === "up" ? "border-emerald-400/50 bg-emerald-400/10 text-emerald-400" : "border-nexus-border text-nexus-muted hover:text-nexus-text"}`}
        >
          <ThumbUpIcon className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => pick("down")}
          className={`flex h-8 w-8 items-center justify-center rounded-lg border transition-colors ${rating === "down" ? "border-red-400/50 bg-red-400/10 text-red-400" : "border-nexus-border text-nexus-muted hover:text-nexus-text"}`}
        >
          <ThumbDownIcon className="h-4 w-4" />
        </button>
        {rating && <span className="text-[11px] text-nexus-muted">Thanks!</span>}
      </div>
      {rating && !sent && (
        <div className="mt-2">
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={2}
            placeholder="Add a comment (optional)…"
            className="w-full resize-none rounded-lg border border-nexus-border bg-nexus-bg px-2.5 py-1.5 text-xs text-nexus-text placeholder:text-nexus-muted focus:border-nexus-accent/60 focus:outline-none"
          />
          <button type="button" onClick={submitComment} className="mt-1.5 rounded-lg border border-nexus-border px-2.5 py-1 text-xs text-nexus-text hover:border-nexus-accent/50">
            Send comment
          </button>
        </div>
      )}
      {sent && (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-emerald-400">
          <CheckIcon className="h-3.5 w-3.5" /> Feedback sent
        </p>
      )}
    </div>
  );
}

export default function ChatSidePanel({ messages, onSend, onFeedback, disabled }) {
  const suggestions = useSuggestions();
  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant" && m.content);
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSE_KEY) === "1");

  const toggle = () => {
    const v = !collapsed;
    setCollapsed(v);
    localStorage.setItem(COLLAPSE_KEY, v ? "1" : "0");
  };

  if (collapsed) {
    return (
      <div className="hidden w-10 shrink-0 flex-col items-center border-l border-nexus-border bg-nexus-panel/40 py-3 lg:flex">
        <button type="button" onClick={toggle} title="Show suggestions" aria-label="Show suggestions" className="rounded-lg p-1.5 text-nexus-muted transition-colors hover:bg-nexus-panel2 hover:text-nexus-accent">
          <SparkleIcon className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <aside className="scroll-thin hidden w-72 shrink-0 flex-col overflow-y-auto border-l border-nexus-border bg-nexus-panel/40 lg:flex">
      <div className="flex items-center justify-between px-4 pt-3">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-nexus-muted">Assist</span>
        <button type="button" onClick={toggle} title="Hide panel" aria-label="Hide panel" className="rounded-lg p-1 text-nexus-muted transition-colors hover:bg-nexus-panel2 hover:text-nexus-text">
          <XIcon className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="space-y-5 p-4 pt-3">
        <section>
          <h3 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-nexus-muted">
            <SparkleIcon className="h-3.5 w-3.5 text-nexus-accent" /> Suggested
          </h3>
          <div className="space-y-1.5">
            {suggestions.slice(0, 6).map((s, i) => (
              <button
                key={i}
                type="button"
                disabled={disabled}
                onClick={() => onSend(s.text)}
                className="block w-full rounded-lg border border-nexus-border bg-nexus-panel px-2.5 py-2 text-left text-xs leading-snug text-nexus-text transition-colors hover:border-nexus-accent/50 hover:text-nexus-accent disabled:opacity-50"
              >
                {s.text}
              </button>
            ))}
          </div>
        </section>

        <section>
          <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-nexus-muted">Rate the last answer</h3>
          <Rating target={lastAssistant} onFeedback={onFeedback} />
        </section>
      </div>
    </aside>
  );
}
