import { useEffect, useState } from "react";
import { HELP_SECTIONS } from "../lib/help";
import { CheckIcon, SparkleIcon, XIcon } from "./icons";

export default function HelpCenter({ open, section, onClose, onStartTour }) {
  const [active, setActive] = useState(section || "getting-started");

  useEffect(() => {
    if (open && section) setActive(section);
  }, [open, section]);

  if (!open) return null;
  const current = HELP_SECTIONS.find((s) => s.id === active) || HELP_SECTIONS[0];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm" onClick={onClose}>
      <div
        className="flex h-[80vh] w-full max-w-3xl overflow-hidden rounded-2xl border border-nexus-border bg-nexus-panel shadow-glow"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Nav */}
        <div className="scroll-thin hidden w-52 shrink-0 overflow-y-auto border-r border-nexus-border bg-nexus-panel2/50 p-2 sm:block">
          <p className="px-2.5 py-2 text-[11px] font-semibold uppercase tracking-wider text-nexus-muted">Help Center</p>
          {HELP_SECTIONS.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => setActive(s.id)}
              className={`block w-full rounded-lg px-2.5 py-1.5 text-left text-sm transition-colors ${
                active === s.id ? "bg-nexus-accent/10 font-medium text-nexus-accent" : "text-nexus-muted hover:text-nexus-text"
              }`}
            >
              {s.title}
            </button>
          ))}
          {onStartTour && (
            <button type="button" onClick={onStartTour} className="mt-2 flex w-full items-center gap-1.5 rounded-lg border border-nexus-border px-2.5 py-1.5 text-left text-xs text-nexus-text hover:border-nexus-accent/50">
              <SparkleIcon className="h-3.5 w-3.5 text-nexus-accent" /> Take the tour
            </button>
          )}
        </div>

        {/* Content */}
        <div className="scroll-thin flex-1 overflow-y-auto">
          <div className="flex items-start justify-between gap-3 border-b border-nexus-border px-5 py-4">
            <div>
              {/* Mobile section picker */}
              <select value={active} onChange={(e) => setActive(e.target.value)} className="mb-2 rounded-lg border border-nexus-border bg-nexus-bg px-2 py-1 text-xs text-nexus-text sm:hidden">
                {HELP_SECTIONS.map((s) => (
                  <option key={s.id} value={s.id}>{s.title}</option>
                ))}
              </select>
              <h2 className="font-display text-lg font-semibold text-nexus-text">{current.title}</h2>
              <p className="mt-1 text-sm text-nexus-muted">{current.blurb}</p>
            </div>
            <button type="button" onClick={onClose} className="rounded-lg p-1.5 text-nexus-muted hover:bg-nexus-panel2 hover:text-nexus-text">
              <XIcon className="h-4 w-4" />
            </button>
          </div>

          <div className="px-5 py-4">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-nexus-muted">How to use it</p>
            <ol className="space-y-2">
              {current.steps.map((step, i) => (
                <li key={i} className="flex gap-2.5 text-sm text-nexus-text">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-nexus-accent/10 text-[11px] font-semibold text-nexus-accent">{i + 1}</span>
                  <span className="leading-relaxed">{step}</span>
                </li>
              ))}
            </ol>

            {current.example && (
              <div className="mt-4 rounded-xl border border-nexus-border bg-nexus-panel2/50 p-3.5">
                <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-nexus-muted">Example</p>
                <p className="text-sm text-nexus-text">“{current.example.input}”</p>
                <p className="mt-1.5 flex items-start gap-1.5 text-xs text-nexus-muted">
                  <CheckIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
                  {current.example.note}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
