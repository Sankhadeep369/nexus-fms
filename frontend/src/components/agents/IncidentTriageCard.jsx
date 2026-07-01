import { useState } from "react";
import { ArrowRightIcon, BellIcon } from "../icons";

const SEVERITY_EXAMPLES = [
  "HVAC down on 3rd floor for 2 hours",
  "Water leak in basement restroom, ongoing",
  "Elevator stuck, passengers inside",
  "CCTV camera in parking offline since morning",
];

export default function IncidentTriageCard({ onAsk }) {
  const [incident, setIncident] = useState("");

  const submit = () => {
    const text = incident.trim();
    if (!text) return;
    onAsk(text);
    setIncident("");
  };

  return (
    <div className="rounded-2xl border border-nexus-border bg-nexus-panel p-5">
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-nexus-violet to-nexus-accent text-nexus-bg">
          <BellIcon className="h-4.5 w-4.5" />
        </span>
        <div>
          <h3 className="font-display text-sm font-semibold text-nexus-text">Incident Triage Agent</h3>
          <p className="mt-0.5 text-xs leading-relaxed text-nexus-muted">
            Report a facilities problem in plain language. The agent classifies it, identifies
            the responsible vendor, checks the SLA response window, and drafts an escalation
            email — all in under 5 seconds.
          </p>
        </div>
      </div>

      <div className="mt-4">
        <textarea
          value={incident}
          onChange={(e) => setIncident(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder="Describe the issue, e.g. AC not cooling on floor 3 since 8am"
          rows={2}
          className="w-full resize-none rounded-xl border border-nexus-border bg-nexus-bg px-3 py-2 text-sm text-nexus-text placeholder:text-nexus-muted focus:border-nexus-violet/60 focus:outline-none"
        />
        <div className="mt-2 flex items-center justify-between">
          <div className="flex flex-wrap gap-1.5">
            {SEVERITY_EXAMPLES.slice(0, 2).map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => setIncident(ex)}
                className="rounded-lg border border-nexus-border px-2 py-0.5 text-[11px] text-nexus-muted transition-colors hover:border-nexus-violet/40 hover:text-nexus-text"
              >
                {ex.length > 30 ? ex.slice(0, 30) + "…" : ex}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={submit}
            disabled={!incident.trim()}
            className="flex shrink-0 items-center gap-1.5 rounded-xl bg-gradient-to-br from-nexus-violet to-nexus-accent px-3.5 py-2 text-sm font-medium text-nexus-bg transition-all hover:shadow-glow-sm active:scale-95 disabled:opacity-30"
          >
            Triage
            <ArrowRightIcon className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
