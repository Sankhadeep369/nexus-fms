import { useState } from "react";
import { BotIcon, CheckIcon, ChevronDownIcon } from "./icons";

// Renders a short, human-readable detail line under a completed step, pulled
// from the SSE event's `detail` payload (shape varies by step name).
const STEP_DETAIL = {
  cache_lookup: (d) => (d?.hit ? "Found in cache -- instant answer" : "Not cached -- generating fresh"),
  query_analysis: (d) =>
    d?.type ? `Classified as "${d.type}"${d.entities?.length ? ` -- ${d.entities.join(", ")}` : ""}` : null,
  agent_research: (d) =>
    d?.tool_calls?.length
      ? `${d.tool_calls.length} lookup${d.tool_calls.length > 1 ? "s" : ""}: ${d.tool_calls
          .map((t) => t.tool.replace(/_/g, " "))
          .join(", ")}`
      : "No matching documents found",
  retrieval: (d) =>
    d?.sources?.length ? `${d.sources.length} source${d.sources.length > 1 ? "s" : ""} found` : "No matching sources",
  generation: (d) => (d?.ms != null ? `Generated in ${(d.ms / 1000).toFixed(1)}s` : null),
  refinement: (d) => (d?.valid != null ? (d.valid ? "Passed quality check" : "Failed quality check") : null),
};

function StepRow({ step }) {
  const isDone = step.status === "done";
  const detailText = isDone ? STEP_DETAIL[step.name]?.(step.detail) : null;

  return (
    <div className="flex items-start gap-2 py-1 text-xs">
      {isDone ? (
        <span className="mt-0.5 flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full bg-emerald-500/15">
          <CheckIcon className="h-2.5 w-2.5 text-emerald-400" />
        </span>
      ) : (
        <span className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-nexus-accent border-t-transparent" />
      )}
      <div className="min-w-0 flex-1">
        <span className={isDone ? "text-nexus-muted" : "font-medium text-nexus-text"}>{step.label}</span>
        {detailText && <p className="mt-0.5 text-[11px] leading-relaxed text-nexus-muted">{detailText}</p>}
      </div>
    </div>
  );
}

// Live view: shown while the assistant message is still streaming with no
// content yet -- replaces the plain "thinking..." text with the actual
// pipeline steps as they happen (cache check, query analysis, agent
// research/retrieval, generation, refinement).
export function WorkflowStepsLive({ steps }) {
  if (!steps || steps.length === 0) return null;
  return (
    <div className="space-y-0.5">
      {steps.map((step) => (
        <StepRow key={step.name} step={step} />
      ))}
    </div>
  );
}

// Collapsed disclosure: shown under a completed answer so the user can review
// what the pipeline did (especially useful for agent-driven queries) without
// it cluttering the chat by default.
export function WorkflowStepsDisclosure({ steps }) {
  const [open, setOpen] = useState(false);
  if (!steps || steps.length === 0) return null;

  const hasAgentStep = steps.some((s) => s.name === "agent_research");

  return (
    <div className="mt-2 overflow-hidden rounded-xl border border-nexus-border bg-nexus-panel2/60">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-[11px] font-medium text-nexus-muted transition-colors hover:text-nexus-text"
      >
        <BotIcon className={`h-3.5 w-3.5 shrink-0 ${hasAgentStep ? "text-nexus-violet" : ""}`} />
        <span className="flex-1">{hasAgentStep ? "Agent workflow" : "Pipeline steps"}</span>
        <ChevronDownIcon className={`h-3.5 w-3.5 shrink-0 transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="border-t border-nexus-border px-3 pb-2 pt-1.5">
          {steps.map((step) => (
            <StepRow key={step.name} step={step} />
          ))}
        </div>
      )}
    </div>
  );
}
