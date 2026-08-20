import { useState } from "react";
import { ownerId, useProfile } from "../context/ProfileContext";
import {
  METHODS,
  analysisToMarkdown,
  deleteAnalysis,
  downloadMarkdown,
  generateAnalysis,
  generateCapa,
  loadAnalyses,
  rootCausesOf,
  saveAnalysis,
} from "../lib/analysis";
import { FaultTree, FiveWhys, Ishikawa, ListEditor, RcaReport } from "./analysis/methods";
import { HistoryIcon, ScaleIcon, SparkleIcon, TrashIcon } from "./icons";

const CATS = ["Manpower", "Method", "Machine", "Material", "Measurement", "Environment"];

// Backend returns ishikawa causes as plain strings; make them selectable objects.
function normalize(method, data) {
  if (method === "ishikawa") {
    data.categories = Object.fromEntries(
      CATS.map((c) => [c, (data.categories?.[c] || []).map((t) => ({ text: String(t), selected: true }))])
    );
  }
  return data;
}

const RENDERERS = { "5whys": FiveWhys, ishikawa: Ishikawa, fta: FaultTree, rca: RcaReport };

export default function AnalysisPage() {
  const { profile } = useProfile();
  const [method, setMethod] = useState("5whys");
  const [issue, setIssue] = useState("");
  const [grounded, setGrounded] = useState(false);
  const [data, setData] = useState(null);
  const [capa, setCapa] = useState(null);
  const [loading, setLoading] = useState(false);
  const [capaLoading, setCapaLoading] = useState(false);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState(loadAnalyses);
  const [showHistory, setShowHistory] = useState(false);

  const Renderer = data ? RENDERERS[data.method] : null;

  const analyze = async () => {
    if (!issue.trim() || loading) return;
    setLoading(true);
    setError(null);
    setData(null);
    setCapa(null);
    try {
      const raw = await generateAnalysis({ method, issue: issue.trim(), grounded, owner: ownerId(profile) });
      setData(normalize(method, raw));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const suggestCapa = async () => {
    setCapaLoading(true);
    const rc = rootCausesOf(data.method, data);
    const res = await generateCapa({ issue: issue.trim(), rootCauses: rc.length ? rc : [issue.trim()] });
    setCapa({ corrective: res.corrective || [], preventive: res.preventive || [] });
    setCapaLoading(false);
  };

  const save = () => {
    const entry = { id: crypto.randomUUID(), method: data.method, issue: issue.trim(), data, capa, date: Date.now() };
    setHistory(saveAnalysis(entry));
  };
  const exportMd = () =>
    downloadMarkdown(`analysis-${data.method}.md`, analysisToMarkdown(data.method, issue, data, capa));

  const openHistory = (h) => {
    setMethod(h.method);
    setIssue(h.issue);
    setData(h.data);
    setCapa(h.capa);
    setShowHistory(false);
  };
  const reset = () => {
    setData(null);
    setCapa(null);
    setIssue("");
    setError(null);
  };

  return (
    <div className="scroll-thin flex-1 overflow-y-auto px-4 py-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="font-display text-xl font-semibold text-nexus-text">Issue Analysis</h1>
            <p className="mt-1 text-sm text-nexus-muted">
              Structured root-cause tools — the model proposes, you refine, it renders the result.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowHistory((v) => !v)}
            className="flex shrink-0 items-center gap-1.5 rounded-lg border border-nexus-border px-2.5 py-1.5 text-xs text-nexus-muted transition-colors hover:text-nexus-text"
          >
            <HistoryIcon className="h-3.5 w-3.5" /> History ({history.length})
          </button>
        </div>

        {showHistory && (
          <div className="rounded-xl border border-nexus-border bg-nexus-panel p-2">
            {history.length === 0 ? (
              <p className="px-2 py-3 text-center text-xs text-nexus-muted">No saved analyses.</p>
            ) : (
              <ul className="space-y-1">
                {history.map((h) => (
                  <li key={h.id} className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-nexus-panel2">
                    <button type="button" onClick={() => openHistory(h)} className="min-w-0 flex-1 text-left">
                      <span className="truncate text-sm text-nexus-text">{h.issue}</span>
                      <span className="ml-1.5 text-[10px] uppercase text-nexus-muted">
                        {METHODS.find((m) => m.id === h.method)?.name}
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setHistory(deleteAnalysis(h.id))}
                      className="shrink-0 rounded p-1 text-nexus-muted hover:text-red-400"
                    >
                      <TrashIcon className="h-3.5 w-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* Setup */}
        <div className="rounded-2xl border border-nexus-border bg-nexus-panel p-4">
          <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-nexus-muted">Method</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {METHODS.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => setMethod(m.id)}
                title={m.blurb}
                className={`rounded-xl border px-2.5 py-2 text-left text-xs transition-all ${
                  method === m.id
                    ? "border-nexus-accent/60 bg-nexus-accent/10 text-nexus-text"
                    : "border-nexus-border bg-nexus-panel2 text-nexus-muted hover:text-nexus-text"
                }`}
              >
                <span className="font-semibold">{m.name}</span>
                <span className="mt-0.5 block leading-tight text-nexus-muted">{m.blurb}</span>
              </button>
            ))}
          </div>

          <textarea
            value={issue}
            onChange={(e) => setIssue(e.target.value)}
            rows={3}
            placeholder="Describe the issue or failure to analyse…"
            className="mt-3 w-full resize-none rounded-xl border border-nexus-border bg-nexus-bg px-3 py-2 text-sm text-nexus-text placeholder:text-nexus-muted focus:border-nexus-accent/60 focus:outline-none"
          />
          <div className="mt-2 flex items-center justify-between">
            <label className="flex items-center gap-2 text-xs text-nexus-muted">
              <input type="checkbox" checked={grounded} onChange={(e) => setGrounded(e.target.checked)} className="accent-nexus-accent" />
              Use my contracts &amp; uploaded documents
            </label>
            <button
              type="button"
              onClick={analyze}
              disabled={!issue.trim() || loading}
              className="flex items-center gap-1.5 rounded-xl bg-gradient-to-br from-nexus-accent to-nexus-accent2 px-3.5 py-2 text-sm font-medium text-nexus-bg transition-all hover:shadow-glow-sm active:scale-95 disabled:opacity-40"
            >
              <SparkleIcon className="h-3.5 w-3.5" />
              {loading ? "Analysing…" : "Analyse"}
            </button>
          </div>
          {error && <p className="mt-2 text-xs text-red-400">{error}</p>}
        </div>

        {/* Result */}
        {data && Renderer && (
          <div className="rounded-2xl border border-nexus-border bg-nexus-panel p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-nexus-text">
                {METHODS.find((m) => m.id === data.method)?.name}
                {data.grounded && <span className="ml-2 rounded bg-nexus-accent/10 px-1.5 py-0.5 text-[10px] text-nexus-accent">grounded</span>}
              </h2>
              <div className="flex items-center gap-1.5 text-xs">
                <button type="button" onClick={save} className="rounded-lg border border-nexus-border px-2 py-1 text-nexus-muted hover:text-nexus-text">Save</button>
                <button type="button" onClick={exportMd} className="rounded-lg border border-nexus-border px-2 py-1 text-nexus-muted hover:text-nexus-text">Export .md</button>
                <button type="button" onClick={() => window.print()} className="rounded-lg border border-nexus-border px-2 py-1 text-nexus-muted hover:text-nexus-text">Print</button>
                <button type="button" onClick={reset} className="rounded-lg border border-nexus-border px-2 py-1 text-nexus-muted hover:text-nexus-text">New</button>
              </div>
            </div>

            <Renderer data={data} onChange={setData} />

            {/* CAPA */}
            <div className="mt-4 border-t border-nexus-border pt-4">
              {!capa ? (
                <button
                  type="button"
                  onClick={suggestCapa}
                  disabled={capaLoading}
                  className="flex items-center gap-1.5 rounded-xl border border-nexus-border px-3 py-2 text-sm text-nexus-text transition-colors hover:border-nexus-accent/50 disabled:opacity-50"
                >
                  <ScaleIcon className="h-3.5 w-3.5 text-nexus-accent" />
                  {capaLoading ? "Generating actions…" : "Suggest corrective & preventive actions"}
                </button>
              ) : (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-emerald-400">Corrective</p>
                    <ListEditor items={capa.corrective} onChange={(v) => setCapa({ ...capa, corrective: v })} placeholder="Corrective action…" />
                  </div>
                  <div>
                    <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-nexus-accent2">Preventive</p>
                    <ListEditor items={capa.preventive} onChange={(v) => setCapa({ ...capa, preventive: v })} placeholder="Preventive action…" />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
