import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useProfile } from "../context/ProfileContext";
import { loadUsers } from "../lib/auth";
import { loadKpis } from "../lib/kpis";
import { CheckIcon, XIcon } from "./icons";

const KEY = "nexus-onboarding-dismissed";

function hasAnyChat() {
  try {
    return (JSON.parse(localStorage.getItem("nexus-conversations")) || []).some((c) => c.messages?.length);
  } catch {
    return false;
  }
}

export default function OnboardingChecklist({ onNavigate, onOpenProfile }) {
  const { isAdmin } = useAuth();
  const { profile } = useProfile();
  const [dismissed, setDismissed] = useState(() => !!localStorage.getItem(KEY));
  if (dismissed) return null;

  const steps = [
    { done: !!(profile?.name && profile?.email), label: "Add your name & email", action: onOpenProfile },
    { done: loadKpis().length > 0, label: "Add your first KPI", action: () => onNavigate("dashboard") },
    { done: hasAnyChat(), label: "Ask NEXUS a question", action: () => onNavigate("chat") },
    ...(isAdmin ? [{ done: loadUsers().length > 1, label: "Create a user", action: () => onNavigate("admin") }] : []),
  ];
  if (steps.every((s) => s.done)) return null;

  const dismiss = () => {
    localStorage.setItem(KEY, "1");
    setDismissed(true);
  };

  return (
    <div className="mb-4 rounded-2xl border border-nexus-border bg-nexus-panel p-4">
      <div className="mb-2.5 flex items-center justify-between">
        <p className="text-sm font-semibold text-nexus-text">Getting started</p>
        <button type="button" onClick={dismiss} className="rounded p-1 text-nexus-muted hover:text-nexus-text" aria-label="Dismiss">
          <XIcon className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        {steps.map((s, i) => (
          <button
            key={i}
            type="button"
            onClick={s.done ? undefined : s.action}
            disabled={s.done}
            className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs transition-colors ${s.done ? "border-emerald-400/40 text-nexus-muted" : "border-nexus-border text-nexus-text hover:border-nexus-accent/50"}`}
          >
            <span className={`flex h-4 w-4 items-center justify-center rounded-full ${s.done ? "bg-emerald-400/20 text-emerald-400" : "border border-nexus-border"}`}>
              {s.done && <CheckIcon className="h-3 w-3" />}
            </span>
            <span className={s.done ? "line-through" : ""}>{s.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
