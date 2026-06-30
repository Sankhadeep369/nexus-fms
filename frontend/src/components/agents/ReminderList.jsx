import { BellIcon, TrashIcon } from "../icons";

function daysUntil(dueDate) {
  const diff = Math.ceil((new Date(dueDate) - new Date().setHours(0, 0, 0, 0)) / 86400000);
  if (diff < 0) return "overdue";
  if (diff === 0) return "due today";
  if (diff === 1) return "due tomorrow";
  return `in ${diff} days`;
}

const STATUS_STYLES = {
  pending: "bg-nexus-accent/10 text-nexus-accent",
  sent: "bg-emerald-500/10 text-emerald-400",
  cancelled: "bg-nexus-muted/10 text-nexus-muted line-through",
};

export default function ReminderList({ reminders, onCancel }) {
  if (reminders.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-nexus-border py-8 text-center">
        <BellIcon className="h-5 w-5 text-nexus-muted" />
        <p className="text-xs text-nexus-muted">No reminders yet. Create one above.</p>
      </div>
    );
  }

  return (
    <ul className="space-y-2">
      {reminders.map((r) => (
        <li
          key={r.id}
          className="flex items-start justify-between gap-3 rounded-xl border border-nexus-border bg-nexus-panel px-3.5 py-3"
        >
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-medium text-nexus-text">{r.title}</span>
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${STATUS_STYLES[r.status]}`}>
                {r.status}
              </span>
            </div>
            <p className="mt-0.5 text-xs text-nexus-muted">
              {r.due_date} · {daysUntil(r.due_date)}
              {r.related_vendor ? ` · ${r.related_vendor}` : ""}
            </p>
            {r.notes && <p className="mt-1 text-xs text-nexus-muted">{r.notes}</p>}
          </div>
          {r.status === "pending" && (
            <button
              type="button"
              onClick={() => onCancel(r.id)}
              title="Cancel reminder"
              className="shrink-0 rounded-lg p-1.5 text-nexus-muted transition-colors hover:bg-nexus-panel2 hover:text-red-400"
            >
              <TrashIcon className="h-3.5 w-3.5" />
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
