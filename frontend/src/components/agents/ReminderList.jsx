import { useState } from "react";
import CalendarMenu from "../CalendarMenu";
import { BellIcon, ChevronDownIcon, EditIcon, TrashIcon } from "../icons";
import ReminderForm from "./ReminderForm";

function startOfToday() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

function isPast(dateStr) {
  return new Date(dateStr) < startOfToday();
}

function daysUntil(dueDate) {
  const diff = Math.ceil((new Date(dueDate) - startOfToday()) / 86400000);
  if (diff < 0) return "overdue";
  if (diff === 0) return "due today";
  if (diff === 1) return "due tomorrow";
  return `in ${diff} days`;
}

function formatTimestamp(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

const STATUS_STYLES = {
  pending: "bg-nexus-accent/10 text-nexus-accent",
  sent: "bg-emerald-500/10 text-emerald-400",
  cancelled: "bg-nexus-muted/10 text-nexus-muted line-through",
};

// Overdue = still pending but the due date has passed (the cron hasn't delivered it).
function isOverdue(r) {
  return r.status === "pending" && isPast(r.due_date);
}

const TABS = [
  { id: "all", label: "All", match: () => true },
  { id: "upcoming", label: "Upcoming", match: (r) => r.status === "pending" && !isPast(r.due_date) },
  { id: "overdue", label: "Overdue", match: isOverdue },
  { id: "sent", label: "Sent", match: (r) => r.status === "sent" },
  { id: "cancelled", label: "Cancelled", match: (r) => r.status === "cancelled" },
];

const EMPTY_LABEL = {
  all: "No reminders yet. Create one above.",
  upcoming: "No upcoming reminders.",
  overdue: "No overdue reminders.",
  sent: "No reminders have been sent yet.",
  cancelled: "No cancelled reminders.",
};

function DetailRow({ label, children }) {
  return (
    <div className="flex gap-2">
      <span className="w-24 shrink-0 text-nexus-muted">{label}</span>
      <span className="min-w-0 flex-1 text-nexus-text">{children}</span>
    </div>
  );
}

export default function ReminderList({ reminders, onCancel, onUpdate }) {
  const [activeTab, setActiveTab] = useState("all");
  const [expandedId, setExpandedId] = useState(null);
  const [editingId, setEditingId] = useState(null);

  const counts = Object.fromEntries(TABS.map((t) => [t.id, reminders.filter(t.match).length]));
  const activeMatch = TABS.find((t) => t.id === activeTab)?.match ?? (() => true);
  const visible = reminders.filter(activeMatch);

  return (
    <div>
      {/* Status tabs */}
      <div className="scroll-thin -mx-1 mb-3 flex gap-1 overflow-x-auto px-1 pb-1">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
              activeTab === tab.id
                ? "bg-nexus-panel2 text-nexus-text"
                : "text-nexus-muted hover:bg-nexus-panel2/60 hover:text-nexus-text"
            }`}
          >
            {tab.label}
            <span
              className={`rounded-full px-1.5 text-[10px] ${
                activeTab === tab.id ? "bg-nexus-accent/15 text-nexus-accent" : "bg-nexus-border/60 text-nexus-muted"
              }`}
            >
              {counts[tab.id]}
            </span>
          </button>
        ))}
      </div>

      {visible.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-nexus-border py-8 text-center">
          <BellIcon className="h-5 w-5 text-nexus-muted" />
          <p className="text-xs text-nexus-muted">{EMPTY_LABEL[activeTab]}</p>
        </div>
      ) : (
        <ul className="space-y-2">
          {visible.map((r) => {
            if (editingId === r.id) {
              return (
                <li key={r.id}>
                  <ReminderForm
                    initial={r}
                    submitLabel="Save changes"
                    onSubmit={(payload) => onUpdate(r.id, payload)}
                    onCancel={() => setEditingId(null)}
                  />
                </li>
              );
            }

            const expanded = expandedId === r.id;
            const overdue = isOverdue(r);

            return (
              <li key={r.id} className="rounded-xl border border-nexus-border bg-nexus-panel">
                <div className="flex items-start justify-between gap-3 px-3.5 py-3">
                  <button
                    type="button"
                    onClick={() => setExpandedId(expanded ? null : r.id)}
                    aria-expanded={expanded}
                    className="min-w-0 flex-1 text-left"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <ChevronDownIcon
                        className={`h-3.5 w-3.5 shrink-0 text-nexus-muted transition-transform ${expanded ? "rotate-180" : ""}`}
                      />
                      <span className="truncate text-sm font-medium text-nexus-text">{r.title}</span>
                      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${STATUS_STYLES[r.status]}`}>
                        {r.status}
                      </span>
                      {overdue && (
                        <span className="shrink-0 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-400">
                          overdue
                        </span>
                      )}
                      {r.system && r.system !== "General" && (
                        <span className="shrink-0 rounded-full bg-nexus-violet/10 px-2 py-0.5 text-[10px] font-medium text-nexus-violet">
                          {r.system}
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 pl-5 text-xs text-nexus-muted">
                      {r.due_date}
                      {r.due_time ? ` at ${r.due_time}` : ""} · {daysUntil(r.due_date)}
                      {r.related_vendor ? ` · ${r.related_vendor}` : ""}
                    </p>
                  </button>

                  <div className="flex shrink-0 items-center gap-1">
                    <CalendarMenu
                      getEvent={() =>
                        Promise.resolve({
                          title: r.title,
                          date: r.due_date,
                          time: r.due_time,
                          notes: r.notes || r.related_vendor || "",
                        })
                      }
                      triggerClassName="rounded-lg p-1.5 text-nexus-muted transition-colors hover:bg-nexus-panel2 hover:text-nexus-accent"
                    />
                    {r.status === "pending" && (
                      <>
                        {onUpdate && (
                          <button
                            type="button"
                            onClick={() => {
                              setEditingId(r.id);
                              setExpandedId(null);
                            }}
                            title="Edit reminder"
                            className="rounded-lg p-1.5 text-nexus-muted transition-colors hover:bg-nexus-panel2 hover:text-nexus-accent"
                          >
                            <EditIcon className="h-3.5 w-3.5" />
                          </button>
                        )}
                        {onCancel && (
                          <button
                            type="button"
                            onClick={() => onCancel(r.id)}
                            title="Cancel reminder"
                            className="rounded-lg p-1.5 text-nexus-muted transition-colors hover:bg-nexus-panel2 hover:text-red-400"
                          >
                            <TrashIcon className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </>
                    )}
                  </div>
                </div>

                {expanded && (
                  <div className="space-y-1.5 border-t border-nexus-border px-3.5 py-3 text-xs">
                    <DetailRow label="System">{r.system || "General"}</DetailRow>
                    <DetailRow label="Due">
                      {r.due_date}
                      {r.due_time ? ` at ${r.due_time}` : ""}
                    </DetailRow>
                    {r.related_vendor && <DetailRow label="Vendor">{r.related_vendor}</DetailRow>}
                    <DetailRow label="Recipient">{r.recipient_email}</DetailRow>
                    <DetailRow label="Notes">
                      {r.notes ? <span className="whitespace-pre-wrap">{r.notes}</span> : <span className="text-nexus-muted">—</span>}
                    </DetailRow>
                    <DetailRow label="Created">{formatTimestamp(r.created_at)}</DetailRow>
                    {r.status === "sent" && <DetailRow label="Sent">{formatTimestamp(r.sent_at)}</DetailRow>}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
