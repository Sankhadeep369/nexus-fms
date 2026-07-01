import IncidentTriageCard from "./agents/IncidentTriageCard";
import ReminderAgent from "./agents/ReminderAgent";
import VendorComparisonCard from "./agents/VendorComparisonCard";

export default function AgentsPage({ onAskVendorQuestion }) {
  return (
    <div className="scroll-thin flex-1 overflow-y-auto px-4 py-6">
      <div className="mx-auto flex max-w-2xl flex-col gap-4">
        <div>
          <h1 className="font-display text-xl font-semibold text-nexus-text">Agents</h1>
          <p className="mt-1 text-sm text-nexus-muted">
            Multi-step AI assistants that research, reason, and act — each completing a structured
            workflow rather than answering a single question.
          </p>
        </div>

        <IncidentTriageCard onAsk={onAskVendorQuestion} />
        <VendorComparisonCard onAsk={onAskVendorQuestion} />
        <ReminderAgent />
      </div>
    </div>
  );
}
