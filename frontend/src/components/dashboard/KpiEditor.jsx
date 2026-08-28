import { useState } from "react";
import {
  addValue,
  CATEGORIES,
  deleteKpi,
  FREQUENCIES,
  fmtValue,
  latestValue,
  loadKpis,
  periodFromDate,
  removeValue,
  seriesOf,
  STATUS_META,
  statsOf,
  statusOf,
  todayISO,
  upsertKpi,
} from "../../lib/kpis";
import { TrashIcon, XIcon } from "../icons";
import { BarChart, LineChart } from "./charts";

const field =
  "w-full rounded-lg border border-nexus-border bg-nexus-bg px-2.5 py-1.5 text-sm text-nexus-text placeholder:text-nexus-muted focus:border-nexus-accent/60 focus:outline-none";

// kpi: an existing KPI (manual or derived) or a fresh unsaved draft (source manual, not yet stored).
export default function KpiEditor({ kpi, isNew, onClose, onChanged, onInvestigate }) {
  const derived = kpi.source === "derived";
  const [draft, setDraft] = useState(kpi);
  const [saved, setSaved] = useState(!isNew);
  const [dateStr, setDateStr] = useState(todayISO());
  const [val, setVal] = useState("");
  const [note, setNote] = useState("");
  const [chart, setChart] = useState("line");
  const stats = statsOf(draft);

  const set = (k, v) => setDraft((d) => ({ ...d, [k]: v }));
  const status = statusOf(draft);
  const meta = STATUS_META[status];

  const saveDef = () => {
    if (!draft.name.trim()) return;
    upsertKpi(draft);
    setSaved(true);
    onChanged();
  };
  const reloadDraft = () => {
    const fresh = loadKpis().find((k) => k.id === draft.id);
    if (fresh) setDraft(fresh);
    onChanged();
  };
  const submitValue = () => {
    const period = periodFromDate(dateStr, draft.frequency);
    if (val === "" || isNaN(Number(val)) || !period) return;
    addValue(draft.id, period, val, note.trim());
    setVal("");
    setNote("");
    reloadDraft();
  };
  const delValue = (p) => {
    removeValue(draft.id, p);
    reloadDraft();
  };
  const remove = () => {
    deleteKpi(draft.id);
    onChanged();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm" onClick={onClose}>
      <div
        className="scroll-thin max-h-[88vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-nexus-border bg-nexus-panel p-5 shadow-glow"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className={`h-2.5 w-2.5 rounded-full ${meta.dot}`} />
              <h2 className="truncate text-base font-semibold text-nexus-text">{draft.name || "New KPI"}</h2>
              {derived && <span className="rounded bg-nexus-accent/10 px-1.5 py-0.5 text-[10px] text-nexus-accent">live · auto-derived</span>}
            </div>
            <p className="mt-0.5 text-xs text-nexus-muted">
              {draft.category} · {fmtValue(draft, latestValue(draft))} {draft.target != null && `· target ${draft.target}${draft.unit === "%" ? "%" : ""}`}
            </p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-1.5 text-nexus-muted hover:bg-nexus-panel2 hover:text-nexus-text">
            <XIcon className="h-4 w-4" />
          </button>
        </div>

        {derived && kpi.hint && <p className="mb-3 rounded-lg bg-nexus-panel2 px-3 py-2 text-xs text-nexus-muted">{kpi.hint}</p>}

        <div className="mb-1.5 flex items-center justify-end gap-1">
          {["line", "bar"].map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setChart(c)}
              className={`rounded-md px-2 py-0.5 text-[11px] capitalize ${chart === c ? "bg-nexus-accent/10 text-nexus-accent" : "text-nexus-muted hover:text-nexus-text"}`}
            >
              {c}
            </button>
          ))}
        </div>
        {chart === "bar" ? (
          <BarChart series={seriesOf(draft)} target={draft.target} unit={draft.unit} />
        ) : (
          <LineChart series={seriesOf(draft)} target={draft.target} unit={draft.unit} />
        )}

        {stats && (
          <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-6">
            {[
              ["Latest", fmtValue(draft, stats.last)],
              ["Avg", fmtValue(draft, stats.avg)],
              ["Min", fmtValue(draft, stats.min)],
              ["Max", fmtValue(draft, stats.max)],
              ["vs prev", stats.changePct == null ? "—" : `${stats.changePct > 0 ? "+" : ""}${stats.changePct}%`],
              ["% target", stats.pctToTarget == null ? "—" : `${stats.pctToTarget}%`],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg border border-nexus-border bg-nexus-panel2/40 px-2 py-1.5 text-center">
                <p className="text-[10px] uppercase tracking-wide text-nexus-muted">{label}</p>
                <p className="mt-0.5 text-sm font-semibold text-nexus-text">{value}</p>
              </div>
            ))}
          </div>
        )}

        {!derived && (
          <>
            {/* Definition */}
            <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-3">
              <label className="col-span-2 sm:col-span-3 text-xs text-nexus-muted">
                Name
                <input value={draft.name} onChange={(e) => set("name", e.target.value)} className={`${field} mt-1`} placeholder="e.g. PPM Compliance" />
              </label>
              <label className="text-xs text-nexus-muted">
                Category
                <select value={draft.category} onChange={(e) => set("category", e.target.value)} className={`${field} mt-1`}>
                  {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                </select>
              </label>
              <label className="text-xs text-nexus-muted">
                Unit
                <input value={draft.unit} onChange={(e) => set("unit", e.target.value)} className={`${field} mt-1`} placeholder="% / hrs / kWh" />
              </label>
              <label className="text-xs text-nexus-muted">
                Target
                <input
                  type="number"
                  value={draft.target ?? ""}
                  onChange={(e) => set("target", e.target.value === "" ? null : Number(e.target.value))}
                  className={`${field} mt-1`}
                  placeholder="optional"
                />
              </label>
            </div>

            <details className="mt-2">
              <summary className="cursor-pointer select-none py-1 text-xs text-nexus-muted hover:text-nexus-text">Advanced options</summary>
              <div className="mt-2 grid grid-cols-2 gap-2.5 sm:grid-cols-3">
                <label className="text-xs text-nexus-muted">
                  Better when
                  <select value={draft.direction} onChange={(e) => set("direction", e.target.value)} className={`${field} mt-1`}>
                    <option value="up">Higher is better</option>
                    <option value="down">Lower is better</option>
                  </select>
                </label>
                <label className="text-xs text-nexus-muted">
                  Warn at
                  <input type="number" value={draft.warn ?? ""} onChange={(e) => set("warn", e.target.value === "" ? null : Number(e.target.value))} className={`${field} mt-1`} placeholder="amber threshold" />
                </label>
                <label className="text-xs text-nexus-muted">
                  Frequency
                  <select value={draft.frequency} onChange={(e) => set("frequency", e.target.value)} className={`${field} mt-1`}>
                    {FREQUENCIES.map((f) => <option key={f}>{f}</option>)}
                  </select>
                </label>
              </div>
            </details>

            <button type="button" onClick={saveDef} disabled={!draft.name.trim()} className="mt-3 w-full rounded-lg bg-gradient-to-br from-nexus-accent to-nexus-accent2 px-3 py-2 text-sm font-medium text-nexus-bg disabled:opacity-40 sm:w-auto sm:px-6">
              {isNew && !saved ? "Create KPI" : "Save changes"}
            </button>

            {/* Values */}
            <div className="mt-4 border-t border-nexus-border pt-4">
              <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-nexus-muted">Data points</p>
              {!saved ? (
                <p className="text-xs text-nexus-muted">Create the KPI first, then add values.</p>
              ) : (
                <>
                  <div className="flex flex-wrap items-end gap-2">
                    <label className="text-xs text-nexus-muted">
                      Date
                      <input type="date" value={dateStr} onChange={(e) => setDateStr(e.target.value)} className={`${field} mt-1 w-40`} />
                    </label>
                    <label className="text-xs text-nexus-muted">
                      Value
                      <input type="number" value={val} onChange={(e) => setVal(e.target.value)} className={`${field} mt-1 w-24`} placeholder="0" onKeyDown={(e) => e.key === "Enter" && submitValue()} />
                    </label>
                    <label className="min-w-[8rem] flex-1 text-xs text-nexus-muted">
                      Note (optional)
                      <input value={note} onChange={(e) => setNote(e.target.value)} className={`${field} mt-1`} onKeyDown={(e) => e.key === "Enter" && submitValue()} />
                    </label>
                    <button type="button" onClick={submitValue} className="rounded-lg bg-gradient-to-br from-nexus-accent to-nexus-accent2 px-4 py-1.5 text-sm font-medium text-nexus-bg">Add</button>
                  </div>
                  <p className="mt-1 text-[11px] text-nexus-muted">Recorded under {periodFromDate(dateStr, draft.frequency)} ({draft.frequency}).</p>
                  {(draft.values || []).length > 0 && (
                    <ul className="mt-3 space-y-1">
                      {[...draft.values].reverse().map((v) => (
                        <li key={v.period} className="flex items-center gap-2 rounded-lg bg-nexus-panel2 px-2.5 py-1.5 text-xs">
                          <span className="w-24 font-mono text-nexus-muted">{v.period}</span>
                          <span className="font-semibold text-nexus-text">{fmtValue(draft, v.value)}</span>
                          {v.note && <span className="truncate text-nexus-muted">— {v.note}</span>}
                          <button type="button" onClick={() => delValue(v.period)} className="ml-auto rounded p-1 text-nexus-muted hover:text-red-400">
                            <TrashIcon className="h-3.5 w-3.5" />
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              )}
            </div>
          </>
        )}

        {/* Footer actions */}
        <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-nexus-border pt-4">
          {status === "red" && (
            <button type="button" onClick={() => onInvestigate(draft)} className="rounded-lg border border-nexus-border px-3 py-1.5 text-xs font-medium text-nexus-text hover:border-nexus-accent/50">
              Investigate in Analysis →
            </button>
          )}
          {!derived && !isNew && (
            <button type="button" onClick={remove} className="ml-auto flex items-center gap-1.5 rounded-lg border border-nexus-border px-3 py-1.5 text-xs text-nexus-muted hover:border-red-400/50 hover:text-red-400">
              <TrashIcon className="h-3.5 w-3.5" /> Delete KPI
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
