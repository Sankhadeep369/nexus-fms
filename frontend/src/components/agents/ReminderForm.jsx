import { useState } from "react";
import { PlusIcon } from "../icons";

export default function ReminderForm({ onCreate }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [notes, setNotes] = useState("");
  const [relatedVendor, setRelatedVendor] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const reset = () => {
    setTitle("");
    setDueDate("");
    setNotes("");
    setRelatedVendor("");
  };

  const submit = async () => {
    if (!title.trim() || !dueDate) return;
    setSubmitting(true);
    setError(null);
    try {
      await onCreate({ title: title.trim(), dueDate, notes: notes.trim(), relatedVendor: relatedVendor.trim() });
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
          className="sm:col-span-2 rounded-lg border border-nexus-border bg-nexus-bg px-3 py-2 text-sm text-nexus-text placeholder:text-nexus-muted focus:border-nexus-accent/60 focus:outline-none"
        />
        <input
          type="date"
          value={dueDate}
          onChange={(e) => setDueDate(e.target.value)}
          className="rounded-lg border border-nexus-border bg-nexus-bg px-3 py-2 text-sm text-nexus-text focus:border-nexus-accent/60 focus:outline-none"
        />
        <input
          type="text"
          value={relatedVendor}
          onChange={(e) => setRelatedVendor(e.target.value)}
          placeholder="Related vendor (optional)"
          className="rounded-lg border border-nexus-border bg-nexus-bg px-3 py-2 text-sm text-nexus-text placeholder:text-nexus-muted focus:border-nexus-accent/60 focus:outline-none"
        />
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Notes (optional)"
          rows={2}
          className="sm:col-span-2 resize-none rounded-lg border border-nexus-border bg-nexus-bg px-3 py-2 text-sm text-nexus-text placeholder:text-nexus-muted focus:border-nexus-accent/60 focus:outline-none"
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
