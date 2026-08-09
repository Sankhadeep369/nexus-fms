import { useEffect, useRef, useState } from "react";
import { useLanguage } from "../context/LanguageContext";
import { useSuggestions } from "../hooks/useSuggestions";
import { ChevronDownIcon, LogoIcon, SparkleIcon, ZapIcon } from "./icons";
import MessageBubble from "./MessageBubble";

// How close to the bottom (px) still counts as "following" the conversation.
const NEAR_BOTTOM_PX = 120;

// Starter prompts that PRE-FILL the input (so a first-timer can edit before
// sending), distinct from the one-tap cached suggestion chips above.
const EXAMPLE_STARTERS = [
  "Draft an email to a vendor about an overdue AMC renewal",
  "Compare a comprehensive vs non-comprehensive HVAC contract",
  "What's our total facilities spend, broken down by site?",
];

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

export default function ChatWindow({ messages, onSend, onClarify, onRegenerate, onEditResend, onFeedback, onOpenGuide, onExample, mode, disabled }) {
  const endRef = useRef(null);
  const scrollRef = useRef(null);
  const [atBottom, setAtBottom] = useState(true);
  const suggestions = useSuggestions();
  const chips = pickChips(suggestions);
  const { t } = useLanguage();

  const scrollToBottom = (behavior = "smooth") =>
    endRef.current?.scrollIntoView({ behavior, block: "end" });

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    setAtBottom(distance <= NEAR_BOTTOM_PX);
  };

  // Auto-follow new content only while the user is already at the bottom, so we
  // don't yank them down when they've scrolled up to read earlier messages.
  useEffect(() => {
    if (atBottom) scrollToBottom();
  }, [messages, atBottom]);

  return (
    <div className="relative flex-1 overflow-hidden">
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="scroll-thin absolute inset-0 overflow-y-auto px-4 py-6"
      >
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
              Tip: type <span className="rounded bg-nexus-panel2 px-1 py-0.5 font-mono">/</span> or press{" "}
              <span className="rounded bg-nexus-panel2 px-1 py-0.5 font-mono">⌘K</span> for more suggested questions.
            </p>
            {onOpenGuide && (
              <button
                type="button"
                onClick={onOpenGuide}
                className="mt-1.5 text-[11px] font-medium text-nexus-accent underline decoration-dotted underline-offset-2 transition-colors hover:text-nexus-accent2"
              >
                {t("see_how")}
              </button>
            )}

            {onExample && (
              <div className="mt-6 w-full max-w-xl">
                <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-nexus-muted">
                  {t("try_example")}
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  {EXAMPLE_STARTERS.map((ex) => (
                    <button
                      key={ex}
                      type="button"
                      disabled={disabled}
                      onClick={() => onExample(ex)}
                      className="rounded-full border border-nexus-border bg-nexus-panel px-3 py-1.5 text-xs text-nexus-muted transition-all hover:border-nexus-accent/50 hover:text-nexus-text disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {ex}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            message={m}
            disabled={disabled}
            mode={mode}
            onRegenerate={onRegenerate}
            onEditResend={onEditResend}
            onClarify={onClarify}
            onFeedback={onFeedback}
          />
        ))}
        <div ref={endRef} />
        </div>
      </div>
      {!atBottom && messages.length > 0 && (
        <button
          type="button"
          onClick={() => scrollToBottom()}
          aria-label="Scroll to latest message"
          className="absolute bottom-4 left-1/2 flex h-9 w-9 -translate-x-1/2 items-center justify-center rounded-full border border-nexus-border bg-nexus-panel text-nexus-text shadow-lg transition-all hover:border-nexus-accent/60 hover:text-nexus-accent active:scale-95"
        >
          <ChevronDownIcon className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
