import { useEffect, useMemo, useRef, useState } from "react";
import { useProfile } from "../context/ProfileContext";
import {
  downloadCsv,
  exportCsv,
  fetchDerived,
  fmtValue,
  FM_TEMPLATES,
  importCsv,
  latestValue,
  loadKpis,
  logBreach,
  newKpi,
  STATUS_META,
  statusOf,
  upsertKpi,
} from "../lib/kpis";
import KpiCard from "./dashboard/KpiCard";
import KpiEditor from "./dashboard/KpiEditor";
import { PlusIcon, UploadIcon } from "./icons";

export default function DashboardPage({ onInvestigate }) {
  const { profile } = useProfile();
  const [manual, setManual] = useState(loadKpis);
  const [derived, setDerived] = useState([]);
  const [active, setActive] = useState(null); // { kpi, isNew }
  const [showAdd, setShowAdd] = useState(false);
  const [showBreach, setShowBreach] = useState(false);
  const [flash, setFlash] = useState(null);
  const [importErr, setImportErr] = useState(null);
  const fileRef = useRef(null);

  const recordBreach = (kind) => {
    logBreach(kind);
    setShowBreach(false);
    reloadManual();
    setFlash(`${kind === "system" ? "System" : "Compliance"} breach logged for this month.`);
    setTimeout(() => setFlash(null), 2500);
  };

  const email = profile?.email || "";
  const reloadManual = () => setManual(loadKpis());

  useEffect(() => {
    let alive = true;
    fetchDerived(email).then((d) => alive && setDerived(d));
    return () => {
      alive = false;
    };
  }, [email]);

  const all = useMemo(() => [...derived, ...manual], [derived, manual]);
  const counts = useMemo(() => {
    const c = { green: 0, amber: 0, red: 0, neutral: 0 };
    all.forEach((k) => (c[statusOf(k)] += 1));
    return c;
  }, [all]);
  const atRisk = useMemo(() => {
    const rank = { red: 0, amber: 1 };
    return all.filter((k) => rank[statusOf(k)] != null).sort((a, b) => rank[statusOf(a)] - rank[statusOf(b)]);
  }, [all]);

  const openNew = (template) => {
    setShowAdd(false);
    setActive({ kpi: newKpi(template || {}), isNew: true });
  };
  const investigate = (kpi) => {
    setActive(null);
    onInvestigate?.(`KPI off target: ${kpi.name} is at ${kpi.value ?? "its latest value"}${kpi.unit === "%" ? "%" : ""}, target ${kpi.target}. Why?`);
  };

  const onImport = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const { kpis, error } = importCsv(await file.text());
    if (error) return setImportErr(error);
    kpis.forEach(upsertKpi);
    reloadManual();
    setImportErr(null);
  };

  return (
    <div className="scroll-thin flex-1 overflow-y-auto px-4 py-6 sm:px-6">
      <div className="mx-auto flex max-w-6xl flex-col gap-5">
        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="font-display text-xl font-semibold text-nexus-text">KPI Dashboard</h1>
            <p className="mt-1 text-sm text-nexus-muted">
              Track facilities metrics against targets. Live cards are derived from your reminders &amp; feedback; the rest you track yourself.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => downloadCsv("nexus-kpis.csv", exportCsv(manual))} className="rounded-lg border border-nexus-border px-2.5 py-1.5 text-xs text-nexus-muted hover:text-nexus-text">
              Export CSV
            </button>
            <button type="button" onClick={() => fileRef.current?.click()} className="flex items-center gap-1.5 rounded-lg border border-nexus-border px-2.5 py-1.5 text-xs text-nexus-muted hover:text-nexus-text">
              <UploadIcon className="h-3.5 w-3.5" /> Import
            </button>
            <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={onImport} />
            <div className="relative">
              <button type="button" onClick={() => setShowBreach((v) => !v)} className="rounded-lg border border-red-400/40 px-2.5 py-1.5 text-xs font-medium text-red-400 hover:bg-red-400/5">
                Log breach
              </button>
              {showBreach && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setShowBreach(false)} />
                  <div className="absolute right-0 z-20 mt-1.5 w-48 rounded-xl border border-nexus-border bg-nexus-panel p-1.5 shadow-glow">
                    <p className="px-2.5 pb-1 pt-1.5 text-[10px] font-medium uppercase tracking-wider text-nexus-muted">Record a breach</p>
                    <button type="button" onClick={() => recordBreach("system")} className="block w-full rounded-lg px-2.5 py-1.5 text-left text-sm text-nexus-text hover:bg-nexus-panel2">System breach</button>
                    <button type="button" onClick={() => recordBreach("compliance")} className="block w-full rounded-lg px-2.5 py-1.5 text-left text-sm text-nexus-text hover:bg-nexus-panel2">Compliance breach</button>
                  </div>
                </>
              )}
            </div>
            <div className="relative">
              <button type="button" onClick={() => setShowAdd((v) => !v)} className="flex items-center gap-1.5 rounded-lg bg-gradient-to-br from-nexus-accent to-nexus-accent2 px-3 py-1.5 text-sm font-medium text-nexus-bg hover:shadow-glow-sm">
                <PlusIcon className="h-3.5 w-3.5" /> Add KPI
              </button>
              {showAdd && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setShowAdd(false)} />
                  <div className="scroll-thin absolute right-0 z-20 mt-1.5 max-h-80 w-64 overflow-y-auto rounded-xl border border-nexus-border bg-nexus-panel p-1.5 shadow-glow">
                    <button type="button" onClick={() => openNew()} className="w-full rounded-lg px-2.5 py-2 text-left text-sm font-medium text-nexus-accent hover:bg-nexus-panel2">
                      + Blank custom KPI
                    </button>
                    <p className="px-2.5 pb-1 pt-2 text-[10px] font-medium uppercase tracking-wider text-nexus-muted">From template</p>
                    {FM_TEMPLATES.map((t) => (
                      <button key={t.name} type="button" onClick={() => openNew(t)} className="flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs text-nexus-text hover:bg-nexus-panel2">
                        <span>{t.name}</span>
                        <span className="text-[10px] text-nexus-muted">{t.target != null ? `${t.target}${t.unit === "%" ? "%" : ` ${t.unit}`}` : t.unit || "—"}</span>
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {importErr && <p className="rounded-lg border border-red-400/40 bg-red-400/5 px-3 py-2 text-xs text-red-400">{importErr}</p>}
        {flash && <p className="rounded-lg border border-emerald-400/40 bg-emerald-400/5 px-3 py-2 text-xs text-emerald-400">{flash}</p>}

        {/* Needs attention */}
        {atRisk.length > 0 && (
          <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-3.5">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-amber-400">Needs attention ({atRisk.length})</p>
            <div className="flex flex-wrap gap-2">
              {atRisk.map((k) => (
                <button
                  key={k.id}
                  type="button"
                  onClick={() => setActive({ kpi: k, isNew: false })}
                  className={`flex items-center gap-1.5 rounded-lg border bg-nexus-panel px-2.5 py-1.5 text-xs text-nexus-text transition-colors hover:border-nexus-accent/50 ${STATUS_META[statusOf(k)].ring}`}
                >
                  <span className={`h-2 w-2 rounded-full ${STATUS_META[statusOf(k)].dot}`} />
                  {k.name}
                  <span className="text-nexus-muted">{fmtValue(k, latestValue(k))}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Status summary */}
        {all.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {["green", "amber", "red", "neutral"].map((s) =>
              counts[s] ? (
                <span key={s} className="flex items-center gap-1.5 rounded-full border border-nexus-border bg-nexus-panel px-3 py-1 text-xs text-nexus-muted">
                  <span className={`h-2 w-2 rounded-full ${STATUS_META[s].dot}`} />
                  {counts[s]} {STATUS_META[s].label}
                </span>
              ) : null
            )}
          </div>
        )}

        {/* Grid */}
        {all.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-nexus-border py-16 text-center">
            <p className="text-sm font-medium text-nexus-text">No KPIs yet</p>
            <p className="mt-1 max-w-sm text-xs text-nexus-muted">
              Add one from a facilities template, create a custom metric, or import a CSV. Reminder-based KPIs appear automatically once you set your email in your profile.
            </p>
            <button type="button" onClick={() => setShowAdd(true)} className="mt-4 rounded-lg bg-gradient-to-br from-nexus-accent to-nexus-accent2 px-4 py-2 text-sm font-medium text-nexus-bg">
              Add your first KPI
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {all.map((kpi) => (
              <KpiCard key={kpi.id} kpi={kpi} onOpen={(k) => setActive({ kpi: k, isNew: false })} />
            ))}
          </div>
        )}
      </div>

      {active && (
        <KpiEditor
          key={active.kpi.id}
          kpi={active.kpi}
          isNew={active.isNew}
          onClose={() => setActive(null)}
          onChanged={reloadManual}
          onInvestigate={investigate}
        />
      )}
    </div>
  );
}
