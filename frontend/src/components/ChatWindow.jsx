import { useEffect, useRef } from "react";
import { useSuggestions } from "../hooks/useSuggestions";
import { LogoIcon, SparkleIcon, ZapIcon } from "./icons";
import MessageBubble from "./MessageBubble";

const CHIP_COUNT = 4;

// Surfaces already-cached suggestions first so the chips a user sees are most
// likely to answer instantly.
function pickChips(suggestions) {
  const cached = suggestions.filter((s) => s.cached);
  const rest = suggestions.filter((s) => !s.cached);
  return [...cached, ...rest].slice(0, CHIP_COUNT);
}

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 5) return "Working late";
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export default function ChatWindow({ messages, onSend, onClarify, onRegenerate, onEditResend, disabled }) {
  const endRef = useRef(null);
  const suggestions = useSuggestions();
  const chips = pickChips(suggestions);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  return (
    <div className="scroll-thin relative flex-1 overflow-y-auto px-4 py-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center pt-16 text-center sm:pt-24">
            <span className="mb-5 flex h-14 w-14 animate-floatGlow items-center justify-center rounded-2xl bg-gradient-to-br from-nexus-accent to-nexus-accent2 text-nexus-bg shadow-glow">
              <LogoIcon className="h-7 w-7" />
            </span>
            <h1 className="font-display text-2xl font-semibold tracking-tight text-nexus-text sm:text-3xl">
              {getGreeting()}, I'm <span className="text-gradient">NEXUS</span>
            </h1>
            <p className="mt-2 max-w-sm text-sm text-nexus-muted">
              Your facilities-management copilot. Ask me anything about contracts, vendors,
              compliance, or maintenance SOPs — or just need a hand writing something.
            </p>

            <div className="mt-8 grid w-full max-w-xl grid-cols-1 gap-2.5 sm:grid-cols-2">
              {chips.map(({ text, cached }) => (
                <button
                  key={text}
                  type="button"
                  disabled={disabled}
                  onClick={() => onSend?.(text)}
                  title={cached ? "Cached -- answers instantly" : undefined}
                  className="group flex items-start gap-2.5 rounded-xl border border-nexus-border bg-nexus-panel px-3.5 py-3 text-left text-sm text-nexus-text transition-all hover:-translate-y-0.5 hover:border-nexus-accent/50 hover:shadow-glow-sm disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {cached ? (
                    <ZapIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-nexus-accent2 transition-transform group-hover:scale-110" />
                  ) : (
                    <SparkleIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-nexus-accent transition-transform group-hover:scale-110" />
                  )}
                  <span>{text}</span>
                </button>
              ))}
            </div>
            <p className="mt-3 text-[11px] text-nexus-muted">
              Tip: type <span className="rounded bg-nexus-panel2 px-1 py-0.5 font-mono">/</span> for more suggested questions.
            </p>
          </div>
        )}
        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            message={m}
            disabled={disabled}
            onRegenerate={onRegenerate}
            onEditResend={onEditResend}
            onClarify={onClarify}
          />
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}
