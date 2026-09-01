import { fmtValue, latestValue, seriesOf, STATUS_META, statusOf, trendOf } from "../../lib/kpis";
import { Sparkline } from "./charts";

export default function KpiCard({ kpi, onOpen }) {
  const status = statusOf(kpi);
  const meta = STATUS_META[status];
  const v = latestValue(kpi);
  const trend = trendOf(kpi);

  return (
    <button
      type="button"
      onClick={() => onOpen(kpi)}
      className={`group flex flex-col rounded-2xl border ${meta.ring} bg-nexus-panel p-4 text-left transition-all hover:border-nexus-accent/50 hover:shadow-glow-sm`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-nexus-text">{kpi.name}</p>
          <p className="text-[11px] text-nexus-muted">{kpi.category}</p>
        </div>
        <span className="flex shrink-0 items-center gap-1.5">
          {kpi.source === "derived" && (
            <span className="rounded bg-nexus-accent/10 px-1 py-0.5 text-[9px] font-medium text-nexus-accent">live</span>
          )}
          <span className={`h-2.5 w-2.5 rounded-full ${meta.dot}`} title={meta.label} />
        </span>
      </div>

      <div className="mt-3 flex items-end justify-between gap-2">
        <div className="min-w-0">
          <span className="font-mono text-2xl font-semibold tracking-tight text-nexus-text">{fmtValue(kpi, v)}</span>
          {kpi.target != null && (
            <span className="ml-1 text-[11px] text-nexus-muted">
              / {kpi.target}
              {kpi.unit === "%" ? "%" : ""}
            </span>
          )}
        </div>
        {trend && !trend.flat && (
          <span className={`shrink-0 font-mono text-[11px] font-medium ${trend.improving ? "text-emerald-400" : "text-red-400"}`}>
            {trend.improving ? "▲" : "▼"} {Math.abs(Math.round(trend.delta * 10) / 10)}
          </span>
        )}
      </div>

      <div className="mt-2">
        <Sparkline series={seriesOf(kpi)} />
      </div>
      <span className={`mt-1.5 text-[10px] font-medium ${meta.text}`}>{meta.label}</span>
    </button>
  );
}
