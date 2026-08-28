import { useState } from "react";
import { ArrowRightIcon, HelpCircleIcon, ScaleIcon } from "../icons";

export default function VendorComparisonCard({ onAsk, onHelp }) {
  const [vendor, setVendor] = useState("");

  const submit = () => {
    const name = vendor.trim();
    if (!name) return;
    onAsk(`Should we renew with ${name} or consider alternatives?`);
    setVendor("");
  };

  return (
    <div className="rounded-2xl border border-nexus-border bg-nexus-panel p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-nexus-violet to-nexus-accent text-nexus-bg">
            <ScaleIcon className="h-4.5 w-4.5" />
          </span>
          <div>
            <h3 className="font-display text-sm font-semibold text-nexus-text">Vendor Comparison Agent</h3>
            <p className="mt-0.5 text-xs leading-relaxed text-nexus-muted">
              Researches the current contract terms and market/competitor benchmarks for a vendor,
              then recommends renew, switch, or negotiate — backed by a table comparison.
            </p>
          </div>
        </div>
        {onHelp && (
          <button type="button" onClick={onHelp} title="How this works" aria-label="Help" className="shrink-0 rounded-lg p-1.5 text-nexus-muted transition-colors hover:bg-nexus-panel2 hover:text-nexus-accent">
            <HelpCircleIcon className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="mt-4 flex items-center gap-2">
        <input
          type="text"
          value={vendor}
          onChange={(e) => setVendor(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Vendor name, e.g. Summit Lift Services"
          className="flex-1 rounded-xl border border-nexus-border bg-nexus-bg px-3 py-2 text-sm text-nexus-text placeholder:text-nexus-muted focus:border-nexus-accent/60 focus:outline-none"
        />
        <button
          type="button"
          onClick={submit}
          disabled={!vendor.trim()}
          className="flex items-center gap-1.5 rounded-xl bg-gradient-to-br from-nexus-accent to-nexus-accent2 px-3.5 py-2 text-sm font-medium text-nexus-bg transition-all hover:shadow-glow-sm active:scale-95 disabled:opacity-30"
        >
          Ask
          <ArrowRightIcon className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
