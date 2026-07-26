import { useState } from "react";
import { PlusIcon } from "../icons";

// Facility systems/categories for the dropdown. "General" is the default for
// reminders that aren't tied to a specific system.
const SYSTEM_OPTIONS = [
  "General",
  "HVAC",
  "Electrical",
  "Fire & Life Safety",
  "Plumbing",
  "Lifts & Escalators",
  "Security & CCTV",
  "Access Control",
  "Housekeeping",
  "Landscaping",
  "Pest Control",
  "Waste Management",
  "Generator & UPS",
  "Building Automation (BMS)",
  "Water Systems",
  "Parking",
  "Vendor Contracts",
];

const FIELD_CLASS =
  "rounded-lg border border-nexus-border bg-nexus-bg px-3 py-2 text-sm text-nexus-text placeholder:text-nexus-muted focus:border-nexus-accent/60 focus:outline-none";

export default function ReminderForm({ onCreate }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [dueTime, setDueTime] = useState("");
  const [system, setSystem] = useState("General");
  const [notes, setNotes] = useState("");
  const [relatedVendor, setRelatedVendor] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const reset = () => {
    setTitle("");
    setDueDate("");
    setDueTime("");
    setSystem("General");
    setNotes("");
    setRelatedVendor("");
  };

  const submit = async () => {
    if (!title.trim() || !dueDate) return;
    setSubmitting(true);
    setError(null);
    try {
      await onCreate({
        title: title.trim(),
        dueDate,
        dueTime: dueTime || null,
        system,
        notes: notes.trim(),
        relatedVendor: relatedVendor.trim(),
      });
      reset();
      setOpen(false);
    } catch {
      setError("Couldn't create reminder. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-dashed border-nexus-border py-3 text-sm font-medium text-nexus-muted transition-colors hover:border-nexus-accent/50 hover:text-nexus-text"
      >
        <PlusIcon className="h-4 w-4" />
        New reminder
      </button>
    );
  }

  return (
    <div className="rounded-xl border border-nexus-border bg-nexus-panel p-4">
      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Reminder title, e.g. Summit Lift AMC renewal"
          className={`sm:col-span-2 ${FIELD_CLASS}`}
        />

        <label className="flex flex-col gap-1 text-[11px] font-medium text-nexus-muted">
          Due date
          <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} className={FIELD_CLASS} />
        </label>
        <label className="flex flex-col gap-1 text-[11px] font-medium text-nexus-muted">
          Time <span className="text-nexus-muted/70">(optional)</span>
          <input type="time" value={dueTime} onChange={(e) => setDueTime(e.target.value)} className={FIELD_CLASS} />
        </label>

        <label className="flex flex-col gap-1 text-[11px] font-medium text-nexus-muted">
          System
          <select value={system} onChange={(e) => setSystem(e.target.value)} className={FIELD_CLASS}>
            {SYSTEM_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[11px] font-medium text-nexus-muted">
          Related vendor <span className="text-nexus-muted/70">(optional)</span>
          <input
            type="text"
            value={relatedVendor}
            onChange={(e) => setRelatedVendor(e.target.value)}
            placeholder="e.g. Summit Lifts"
            className={FIELD_CLASS}
          />
        </label>

        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Notes (optional)"
          rows={2}
          className={`sm:col-span-2 resize-none ${FIELD_CLASS}`}
        />
      </div>

      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}

      <div className="mt-3 flex justify-end gap-2">
        <button
          type="button"
          onClick={() => {
            setOpen(false);
            reset();
          }}
          className="rounded-lg px-3 py-1.5 text-xs font-medium text-nexus-muted hover:bg-nexus-panel2"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={!title.trim() || !dueDate || submitting}
          className="rounded-lg bg-gradient-to-br from-nexus-accent to-nexus-accent2 px-3.5 py-1.5 text-xs font-medium text-nexus-bg disabled:opacity-30"
        >
          {submitting ? "Creating..." : "Create reminder"}
        </button>
      </div>
    </div>
  );
}
