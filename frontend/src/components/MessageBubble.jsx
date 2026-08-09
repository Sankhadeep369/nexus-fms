import { motion } from "framer-motion";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import CalendarMenu from "./CalendarMenu";
import { BookIcon, BotIcon, CheckIcon, ChevronDownIcon, CopyIcon, EditIcon, LogoIcon, RegenerateIcon, ThumbDownIcon, ThumbUpIcon, UserIcon } from "./icons";
import { extractEvent } from "../lib/calendar";
import ThinkingIndicator from "./ThinkingIndicator";
import { WorkflowStepsDisclosure, WorkflowStepsLive } from "./WorkflowSteps";

function flattenText(node) {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(flattenText).join("");
  if (node?.props?.children != null) return flattenText(node.props.children);
  return "";
}

// Renders fenced code blocks with a ChatGPT-style header bar: detected
// language on the left, a copy-to-clipboard button on the right.
function CodeBlock({ children }) {
  const [copied, setCopied] = useState(false);
  const codeEl = Array.isArray(children) ? children[0] : children;
  const lang = /language-(\w+)/.exec(codeEl?.props?.className ?? "")?.[1] ?? "text";
  const text = flattenText(codeEl?.props?.children).replace(/\n$/, "");

  const handleCopy = () => {
    navigator.clipboard?.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="mb-2.5 overflow-hidden rounded-xl border border-nexus-border last:mb-0">
      <div className="flex items-center justify-between bg-nexus-panel2 px-3 py-1.5">
        <span className="text-[11px] font-medium uppercase tracking-wider text-nexus-muted">{lang}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] text-nexus-muted transition-colors hover:bg-nexus-bg hover:text-nexus-text"
        >
          {copied ? <CheckIcon className="h-3 w-3 text-emerald-400" /> : <CopyIcon className="h-3 w-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="overflow-x-auto bg-nexus-panel p-3">{children}</pre>
    </div>
  );
}

const markdownComponents = {
  p: ({ children }) => <p className="mb-2.5 text-sm leading-relaxed last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-nexus-text">{children}</strong>,
  em: ({ children }) => <em className="italic text-nexus-text">{children}</em>,
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-nexus-accent underline decoration-nexus-accent/40 underline-offset-2 hover:decoration-nexus-accent"
    >
      {children}
    </a>
  ),
  h1: ({ children }) => (
    <h1 className="mb-2 mt-1 font-display text-base font-semibold text-nexus-text first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-2 mt-3 font-display text-sm font-semibold text-nexus-text first:mt-0">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-1.5 mt-2.5 text-sm font-semibold text-nexus-text first:mt-0">{children}</h3>
  ),
  ul: ({ children }) => <ul className="mb-2.5 ml-4 list-disc space-y-1 text-sm leading-relaxed last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2.5 ml-4 list-decimal space-y-1 text-sm leading-relaxed last:mb-0">{children}</ol>,
  li: ({ children }) => <li className="pl-1">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="mb-2.5 border-l-2 border-nexus-accent/50 pl-3 text-sm italic text-nexus-muted last:mb-0">
      {children}
    </blockquote>
  ),
  code: ({ className, children }) => {
    if (/language-/.test(className ?? "")) {
      return <code className={`${className} font-mono text-[0.85em] leading-relaxed`}>{children}</code>;
    }
    return (
      <code className="rounded bg-nexus-panel2 px-1.5 py-0.5 font-mono text-[0.85em] text-nexus-accent">{children}</code>
    );
  },
  pre: CodeBlock,
  hr: () => <hr className="my-3 border-nexus-border" />,
  table: ({ children }) => (
    <div className="mb-2.5 overflow-x-auto rounded-xl border border-nexus-border last:mb-0">
      <table className="w-full border-collapse text-left text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-nexus-panel2">{children}</thead>,
  th: ({ children }) => (
    <th className="border-b border-nexus-border px-3 py-2 font-semibold text-nexus-text">{children}</th>
  ),
  td: ({ children }) => (
    <td className="border-b border-nexus-border px-3 py-2 align-top text-nexus-text last:border-b-0">{children}</td>
  ),
  tr: ({ children }) => <tr className="last:[&>td]:border-b-0">{children}</tr>,
};

// Converts raw source paths like "current_contracts/13_PrimeEdge_Electrical_HQ.txt"
// into a readable label and category badge.
function formatSource(path) {
  const folder = path.split("/")[0];
  const filename = path.split("/").pop().replace(".txt", "").replace(/^\d+_/, "");
  const name = filename.replace(/_/g, " ");
  const category =
    folder === "current_contracts"
      ? "Current Contract"
      : folder === "competitor_contracts"
      ? "Market Reference"
      : "Domain Reference";
  return { name, category };
}

function SourcesPanel({ sources }) {
  const [open, setOpen] = useState(false);
  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-2 overflow-hidden rounded-xl border border-nexus-border bg-nexus-panel2/60">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-[11px] font-medium text-nexus-muted transition-colors hover:text-nexus-text"
      >
        <BookIcon className="h-3.5 w-3.5 shrink-0" />
        <span className="flex-1">{sources.length} source{sources.length > 1 ? "s" : ""} referenced</span>
        <ChevronDownIcon
          className={`h-3.5 w-3.5 shrink-0 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div className="border-t border-nexus-border px-3 pb-2.5 pt-2">
          <ul className="space-y-1.5">
            {sources.map((src) => {
              const { name, category } = formatSource(src);
              return (
                <li key={src} className="flex items-start gap-2">
                  <span className="mt-0.5 shrink-0 rounded bg-nexus-accent/10 px-1.5 py-0.5 text-[10px] font-medium text-nexus-accent">
                    {category}
                  </span>
                  <span className="text-[11px] leading-relaxed text-nexus-text">{name}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

const toolbarBtn =
  "rounded-md p-1.5 text-nexus-muted transition-colors hover:bg-nexus-panel2 hover:text-nexus-text disabled:cursor-not-allowed disabled:opacity-40";
const labelBtn =
  "flex items-center gap-1 rounded-md px-1.5 py-1 text-[11px] font-medium text-nexus-muted transition-colors hover:bg-nexus-panel2 hover:text-nexus-text disabled:cursor-not-allowed disabled:opacity-40";

export default function MessageBubble({ message, disabled, mode, onRegenerate, onEditResend, onClarify, onFeedback }) {
  const otherMode = mode === "thinking" ? "simple" : "thinking";
  const otherModeLabel = otherMode === "thinking" ? "Thinking" : "Simple";
  const [feedback, setFeedback] = useState(null); // null | "up" | "down"

  const rate = (rating) => {
    setFeedback(rating);
    onFeedback?.(message.id, rating);
  };
  const isUser = message.role === "user";
  const showThinking = !isUser && message.isStreaming && message.content === "";
  const showCursor = !isUser && message.isStreaming && message.content !== "";

  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(message.content);
  const [copied, setCopied] = useState(false);

  const startEdit = () => {
    setEditValue(message.content);
    setEditing(true);
  };

  const saveEdit = () => {
    const trimmed = editValue.trim();
    setEditing(false);
    if (!trimmed || trimmed === message.content) return;
    onEditResend?.(message.id, trimmed);
  };

  const handleCopy = () => {
    navigator.clipboard?.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={`group flex items-start gap-2.5 ${isUser ? "justify-end" : "justify-start"}`}
    >
      {!isUser && (
        <span
          className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-nexus-bg transition-shadow ${
            message.agentSynthesized
              ? "bg-gradient-to-br from-nexus-violet to-nexus-accent"
              : "bg-gradient-to-br from-nexus-accent to-nexus-accent2"
          } ${message.isStreaming ? "shadow-glow-sm animate-pulse" : ""}`}
        >
          {message.agentSynthesized ? <BotIcon className="h-4 w-4" /> : <LogoIcon className="h-4 w-4" />}
        </span>
      )}

      <div className={`flex max-w-[80%] flex-col ${isUser ? "items-end" : "items-start"}`}>
        {!isUser && message.agentSynthesized && !message.isStreaming && (
          <div className="mb-1 flex items-center gap-1.5 text-[11px] font-medium text-nexus-violet">
            <BotIcon className="h-3 w-3" />
            {message.steps?.some((s) => s.name === "incident_triage")
              ? "Agent · Incident Triage"
              : (message.agentToolCalls ?? []).some((t) => t.tool === "retrieve_financial_chunks")
              ? "Agent · Budget Analysis"
              : (message.agentToolCalls ?? []).some((t) => t.tool === "retrieve_contract_headers")
              ? "Agent · Portfolio Overview"
              : "Agent · Vendor Comparison"}
          </div>
        )}
        <div
          className={`w-full rounded-2xl px-4 py-3 ${
            isUser
              ? "bg-gradient-to-br from-nexus-accent to-nexus-accent2 text-nexus-bg"
              : message.agentSynthesized && !message.isStreaming
              ? "border border-nexus-violet/30 bg-nexus-panel text-nexus-text"
              : "border border-nexus-border bg-nexus-panel text-nexus-text"
          }`}
        >
          {editing ? (
            <div className="flex flex-col gap-2">
              <textarea
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    saveEdit();
                  } else if (e.key === "Escape") {
                    setEditing(false);
                  }
                }}
                rows={Math.min(8, Math.max(2, editValue.split("\n").length))}
                autoFocus
                className="w-full resize-none rounded-lg bg-black/10 px-2 py-1.5 text-sm leading-relaxed text-inherit placeholder:text-current focus:outline-none"
              />
              <div className="flex justify-end gap-1.5 text-xs font-medium">
                <button
                  type="button"
                  onClick={() => setEditing(false)}
                  className="rounded-md px-2.5 py-1 transition-colors hover:bg-black/10"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={saveEdit}
                  className="rounded-md bg-black/15 px-2.5 py-1 transition-colors hover:bg-black/25"
                >
                  Save &amp; resend
                </button>
              </div>
            </div>
          ) : showThinking ? (
            message.steps && message.steps.length > 0 ? (
              <WorkflowStepsLive steps={message.steps} />
            ) : (
              <ThinkingIndicator />
            )
          ) : isUser ? (
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
          ) : (
            <div className="markdown-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {message.content}
              </ReactMarkdown>
              {showCursor && (
                <span className="inline-block h-3.5 w-[3px] animate-pulse rounded-sm bg-nexus-accent align-text-bottom" />
              )}
            </div>
          )}

          {/* Clarification quick-reply chips — shown when backend needs scope resolved */}
          {!isUser && !message.isStreaming && message.clarificationOptions?.length > 0 && (
            <div className="mt-3 border-t border-nexus-border/60 pt-3">
              <p className="mb-2 text-[11px] font-medium text-nexus-muted">Choose an option or type your answer below:</p>
              <div className="flex flex-wrap gap-2">
                {message.clarificationOptions.map((option) => (
                  <button
                    key={option}
                    type="button"
                    disabled={disabled}
                    onClick={() => onClarify?.(message.originalQuery, option)}
                    className="rounded-lg border border-nexus-accent/40 bg-nexus-accent/8 px-3 py-1.5 text-xs font-medium text-nexus-accent transition-all hover:border-nexus-accent/70 hover:bg-nexus-accent/15 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>
          )}

          {!isUser && message.error && (
            <div className="mt-2 flex items-start gap-2 rounded-lg border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-300">
              <span>{message.error}</span>
            </div>
          )}

          {!isUser && message.stopped && (
            <p className="mt-2 text-xs text-nexus-muted">Stopped generating.</p>
          )}

          {!isUser && message.validationFailed && (
            <div className="mt-2 flex items-center gap-1.5 rounded-lg border border-amber-500/20 bg-amber-500/10 px-2.5 py-1.5 text-[11px] text-amber-400">
              Answer withheld — quality check detected unreliable content.
            </div>
          )}

          {!isUser && message.latencyMs != null && (
            <div className="mt-1.5 text-[10px] text-nexus-muted">
              {message.cacheHit ? `cached` : "generated"} · {message.latencyMs} ms
            </div>
          )}
        </div>

        {!isUser && !message.isStreaming && message.sources?.length > 0 && (
          <div className="mt-1 w-full">
            <SourcesPanel sources={message.sources} />
          </div>
        )}

        {!isUser && !message.isStreaming && message.cacheHit !== "exact" && message.steps?.length > 0 && (
          <div className="mt-1 w-full">
            <WorkflowStepsDisclosure steps={message.steps} agentToolCalls={message.agentToolCalls ?? []} />
          </div>
        )}

        {!editing && (
          <div
            className={`mt-1 flex items-center gap-0.5 transition-opacity duration-150 ${
              isUser
                ? "justify-end opacity-0 group-hover:opacity-100"
                : "justify-start opacity-100"
            }`}
          >
            {isUser ? (
              <button type="button" onClick={startEdit} disabled={disabled} title="Edit & resend" className={toolbarBtn}>
                <EditIcon className="h-3.5 w-3.5" />
              </button>
            ) : (
              !message.isStreaming &&
              message.content && (
                <>
                  <button type="button" onClick={handleCopy} title="Copy response" className={labelBtn}>
                    {copied ? (
                      <>
                        <CheckIcon className="h-3.5 w-3.5 text-emerald-400" /> Copied
                      </>
                    ) : (
                      <>
                        <CopyIcon className="h-3.5 w-3.5" /> Copy
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => onRegenerate?.(message.id)}
                    disabled={disabled}
                    title="Regenerate response"
                    className={labelBtn}
                  >
                    <RegenerateIcon className="h-3.5 w-3.5" /> Regenerate
                  </button>
                  <button
                    type="button"
                    onClick={() => onRegenerate?.(message.id, otherMode)}
                    disabled={disabled}
                    title={`Regenerate in ${otherModeLabel} mode`}
                    className={labelBtn}
                  >
                    Try in {otherModeLabel}
                  </button>
                  <CalendarMenu getEvent={() => extractEvent(message.content)} triggerClassName={labelBtn} />
                  <span className="mx-0.5 h-4 w-px bg-nexus-border" />
                  <button
                    type="button"
                    onClick={() => rate("up")}
                    title="Good answer"
                    aria-pressed={feedback === "up"}
                    className={`${toolbarBtn} ${feedback === "up" ? "text-nexus-accent" : ""}`}
                  >
                    <ThumbUpIcon className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => rate("down")}
                    title="Bad answer"
                    aria-pressed={feedback === "down"}
                    className={`${toolbarBtn} ${feedback === "down" ? "text-amber-400" : ""}`}
                  >
                    <ThumbDownIcon className="h-3.5 w-3.5" />
                  </button>
                  {feedback && <span className="ml-0.5 text-[11px] text-nexus-muted">Thanks!</span>}
                </>
              )
            )}
          </div>
        )}
      </div>

      {isUser && (
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-nexus-border bg-nexus-panel2 text-nexus-muted">
          <UserIcon className="h-4 w-4" />
        </span>
      )}
    </motion.div>
  );
}
