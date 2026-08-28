import { useLayoutEffect, useState } from "react";

const STEPS = [
  { selector: null, title: "Welcome to NEXUS", body: "Your facilities-management assistant. Here’s a 20-second tour of the essentials." },
  { selector: '[data-tour="tabs"]', title: "Navigate", body: "Switch between Home, Chat, Agents, Analysis and Dashboard here. You only see what you’re allowed to use." },
  { selector: '[data-tour="composer"]', title: "Ask anything", body: "Ask about contracts, systems and vendors — answers are grounded in your documents and cite their sources." },
  { selector: '[data-tour="help"]', title: "Help is always here", body: "Open the Help Center any time for a tutorial on every tool and agent." },
];

const PAD = 6;

export default function GuidedTour({ onClose }) {
  const [idx, setIdx] = useState(0);
  const [rect, setRect] = useState(null);
  const step = STEPS[idx];

  useLayoutEffect(() => {
    const measure = () => {
      const el = step.selector ? document.querySelector(step.selector) : null;
      setRect(el ? el.getBoundingClientRect() : null);
    };
    measure();
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [idx, step.selector]);

  const last = idx === STEPS.length - 1;
  const next = () => (last ? onClose() : setIdx((i) => i + 1));

  // Tooltip placement: under the target if there's room, else above; centered if no target.
  const tip = (() => {
    if (!rect) return { left: "50%", top: "50%", transform: "translate(-50%, -50%)" };
    const below = rect.bottom + 12;
    const above = rect.top - 12;
    const roomBelow = window.innerHeight - rect.bottom > 180;
    const left = Math.min(Math.max(rect.left, 12), window.innerWidth - 300);
    return roomBelow ? { left, top: below } : { left, top: above, transform: "translateY(-100%)" };
  })();

  return (
    <div className="fixed inset-0 z-[60]">
      {/* Spotlight (dims everything except the target) */}
      {rect ? (
        <div
          className="pointer-events-none absolute rounded-xl transition-all"
          style={{
            left: rect.left - PAD,
            top: rect.top - PAD,
            width: rect.width + PAD * 2,
            height: rect.height + PAD * 2,
            boxShadow: "0 0 0 9999px rgba(0,0,0,0.62)",
          }}
        />
      ) : (
        <div className="absolute inset-0 bg-black/62" />
      )}

      {/* Tooltip */}
      <div className="absolute w-72 max-w-[calc(100vw-24px)] rounded-2xl border border-nexus-border bg-nexus-panel p-4 shadow-glow" style={tip}>
        <p className="font-display text-sm font-semibold text-nexus-text">{step.title}</p>
        <p className="mt-1 text-xs leading-relaxed text-nexus-muted">{step.body}</p>
        <div className="mt-3 flex items-center justify-between">
          <button type="button" onClick={onClose} className="text-xs text-nexus-muted hover:text-nexus-text">Skip</button>
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-nexus-muted">{idx + 1}/{STEPS.length}</span>
            {idx > 0 && (
              <button type="button" onClick={() => setIdx((i) => i - 1)} className="rounded-lg border border-nexus-border px-2.5 py-1 text-xs text-nexus-text hover:border-nexus-accent/50">
                Back
              </button>
            )}
            <button type="button" onClick={next} className="rounded-lg bg-gradient-to-br from-nexus-accent to-nexus-accent2 px-3 py-1 text-xs font-medium text-nexus-bg">
              {last ? "Done" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
