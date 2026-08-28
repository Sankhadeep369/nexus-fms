import { useEffect, useState } from "react";
import { useProfile } from "../../context/ProfileContext";
import { useReminders } from "../../hooks/useReminders";
import { BellIcon, HelpCircleIcon } from "../icons";
import ReminderForm from "./ReminderForm";
import ReminderList from "./ReminderList";

const STORAGE_KEY = "nexus-reminder-email";

export default function ReminderAgent({ canCreate = true, canManage = true, onHelp }) {
  const { profile } = useProfile();
  const [email, setEmail] = useState(() => localStorage.getItem(STORAGE_KEY) || "");
  const [emailInput, setEmailInput] = useState("");

  // If the user set a profile email and hasn't picked a reminder email yet,
  // adopt it so they don't have to type it again.
  useEffect(() => {
    if (!email && profile?.email) {
      localStorage.setItem(STORAGE_KEY, profile.email);
      setEmail(profile.email);
    }
  }, [profile, email]);
  const { reminders, error, createReminder, updateReminder, cancelReminder } = useReminders(email);

  const saveEmail = () => {
    const trimmed = emailInput.trim();
    if (!trimmed) return;
    localStorage.setItem(STORAGE_KEY, trimmed);
    setEmail(trimmed);
  };

  if (!email) {
    return (
      <div className="rounded-2xl border border-nexus-border bg-nexus-panel p-5">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-nexus-violet to-nexus-accent text-nexus-bg">
            <BellIcon className="h-4.5 w-4.5" />
          </span>
          <div>
            <h3 className="font-display text-sm font-semibold text-nexus-text">Reminder Agent</h3>
            <p className="mt-0.5 text-xs leading-relaxed text-nexus-muted">
              Create custom reminders for renewals, audits, or deadlines — NEXUS emails you when they're due.
            </p>
          </div>
        </div>
        <div className="mt-4 flex items-center gap-2">
          <input
            type="email"
            value={emailInput}
            onChange={(e) => setEmailInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && saveEmail()}
            placeholder="your@email.com"
            className="flex-1 rounded-xl border border-nexus-border bg-nexus-bg px-3 py-2 text-sm text-nexus-text placeholder:text-nexus-muted focus:border-nexus-accent/60 focus:outline-none"
          />
          <button
            type="button"
            onClick={saveEmail}
            disabled={!emailInput.trim()}
            className="rounded-xl bg-gradient-to-br from-nexus-accent to-nexus-accent2 px-3.5 py-2 text-sm font-medium text-nexus-bg disabled:opacity-30"
          >
            Continue
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-nexus-border bg-nexus-panel p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-nexus-violet to-nexus-accent text-nexus-bg">
            <BellIcon className="h-4.5 w-4.5" />
          </span>
          <div>
            <h3 className="font-display text-sm font-semibold text-nexus-text">Reminder Agent</h3>
            <p className="mt-0.5 text-xs leading-relaxed text-nexus-muted">
              Reminders for <span className="text-nexus-text">{email}</span>
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {onHelp && (
            <button type="button" onClick={onHelp} title="How this works" aria-label="Help" className="rounded-lg p-1 text-nexus-muted transition-colors hover:bg-nexus-panel2 hover:text-nexus-accent">
              <HelpCircleIcon className="h-4 w-4" />
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              localStorage.removeItem(STORAGE_KEY);
              setEmail("");
            }}
            className="text-[11px] text-nexus-muted underline decoration-dotted hover:text-nexus-text"
          >
            change email
          </button>
        </div>
      </div>

      {error && (
        <p className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-400">
          {error}
        </p>
      )}

      {canCreate && (
        <div className="mt-4">
          <ReminderForm onSubmit={createReminder} />
        </div>
      )}

      <div className="mt-3">
        <ReminderList
          reminders={reminders}
          onCancel={canManage ? cancelReminder : null}
          onUpdate={canManage ? updateReminder : null}
        />
      </div>
    </div>
  );
}
