import { useAuth } from "../context/AuthContext";
import IncidentTriageCard from "./agents/IncidentTriageCard";
import ReminderAgent from "./agents/ReminderAgent";
import VendorComparisonCard from "./agents/VendorComparisonCard";

export default function AgentsPage({ onAskVendorQuestion, onHelp }) {
  const { canAgent, reminderPerms } = useAuth();
  const anyAgent = canAgent("incident_triage") || canAgent("vendor_comparison") || canAgent("reminder");

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

        {canAgent("incident_triage") && <IncidentTriageCard onAsk={onAskVendorQuestion} onHelp={() => onHelp?.("incident_triage")} />}
        {canAgent("vendor_comparison") && <VendorComparisonCard onAsk={onAskVendorQuestion} onHelp={() => onHelp?.("vendor_comparison")} />}
        {canAgent("reminder") && <ReminderAgent canCreate={reminderPerms.create} canManage={reminderPerms.manage} onHelp={() => onHelp?.("reminder")} />}

        {!anyAgent && (
          <div className="rounded-2xl border border-dashed border-nexus-border py-12 text-center text-sm text-nexus-muted">
            You don’t have access to any agents. Ask an administrator to grant access.
          </div>
        )}
      </div>
    </div>
  );
}
