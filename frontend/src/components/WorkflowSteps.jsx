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
  incident_triage: (d) =>
    d?.domain ? `${d.domain.replace(/_/g, " ")} · ${d.severity} · vendor: ${d.vendor} · ${d.sla_status}` : null,
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
// what the pipeline did. Auto-expanded for agent-driven answers so the research
// process is immediately visible without needing to click.
export function WorkflowStepsDisclosure({ steps, agentToolCalls = [] }) {
  const hasAgentStep = steps?.some((s) =>
    ["agent_research", "synthesis", "incident_triage"].includes(s.name)
  );
  const [open, setOpen] = useState(hasAgentStep); // auto-expand for agent answers
  if (!steps || steps.length === 0) return null;

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
          {agentToolCalls.length > 0 && (
            <div className="mt-2 space-y-1 border-t border-nexus-border pt-2">
              <p className="text-[10px] font-medium uppercase tracking-wider text-nexus-muted">
                Tools used
              </p>
              {agentToolCalls.map((tc, i) => (
                <div key={i} className="flex items-center gap-2 text-[11px]">
                  <span className="shrink-0 rounded bg-nexus-violet/10 px-1.5 py-0.5 font-mono text-[10px] text-nexus-violet">
                    {tc.tool.replace(/_/g, " ")}
                  </span>
                  <span className="text-nexus-muted">
                    {tc.args && Object.values(tc.args)[0]
                      ? `"${Object.values(tc.args)[0]}"`
                      : ""}
                    {tc.results_found != null ? ` → ${tc.results_found} section${tc.results_found !== 1 ? "s" : ""}` : ""}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
