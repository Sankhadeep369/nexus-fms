import { fmtValue, latestValue, loadKpis, seriesOf, STATUS_META, statusOf } from "../../lib/kpis";
import { Sparkline } from "../dashboard/charts";
import { ArrowRightIcon, BellIcon, BotIcon, ChartIcon, SearchIcon, SparkleIcon } from "../icons";

const SHORTCUTS = {
  chat: { label: "Chat", icon: SparkleIcon },
  agents: { label: "Agents", icon: BotIcon },
  analysis: { label: "Analysis", icon: SearchIcon },
  dashboard: { label: "Dashboard", icon: ChartIcon },
  reminder: { label: "Reminders", icon: BellIcon },
};

const cfgInput =
  "w-full rounded-md border border-nexus-border bg-nexus-bg px-2 py-1 text-xs text-nexus-text focus:border-nexus-accent/60 focus:outline-none";

function Greeting({ userName }) {
  const h = new Date().getHours();
  const part = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  const date = new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
  return (
    <div className="flex h-full flex-col justify-center px-4">
      <p className="font-display text-lg font-semibold text-nexus-text">
        {part}, {userName}
      </p>
      <p className="text-xs text-nexus-muted">{date}</p>
    </div>
  );
}

function Shortcut({ widget, editing, onConfig, onNavigate }) {
  const target = widget.config.target || "chat";
  const meta = SHORTCUTS[target] || SHORTCUTS.chat;
  const Icon = meta.icon;
  if (editing) {
    return (
      <div className="flex h-full flex-col justify-center gap-1.5 px-3">
        <input value={widget.config.label || ""} onChange={(e) => onConfig({ label: e.target.value })} placeholder="Label" className={cfgInput} />
        <select value={target} onChange={(e) => onConfig({ target: e.target.value })} className={cfgInput}>
          {Object.entries(SHORTCUTS).map(([k, v]) => (
            <option key={k} value={k}>{v.label}</option>
          ))}
        </select>
      </div>
    );
  }
  return (
    <button
      type="button"
      onClick={() => onNavigate?.(target === "reminder" ? "agents" : target)}
      className="group flex h-full w-full items-center gap-2.5 px-3.5 text-left"
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-nexus-accent to-nexus-accent2 text-nexus-bg">
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1 truncate text-sm font-medium text-nexus-text">{widget.config.label || meta.label}</span>
      <ArrowRightIcon className="h-4 w-4 shrink-0 text-nexus-muted transition-transform group-hover:translate-x-0.5" />
    </button>
  );
}

function KpiTile({ widget, editing, onConfig }) {
  const kpis = loadKpis();
  const kpi = kpis.find((k) => k.id === widget.config.kpiId);
  if (editing || !kpi) {
    return (
      <div className="flex h-full flex-col justify-center gap-2 px-3 text-center">
        <p className="text-xs text-nexus-muted">{kpis.length ? "Pick a KPI to show" : "No KPIs yet — add some in the Dashboard"}</p>
        {kpis.length > 0 && (
          <select value={widget.config.kpiId || ""} onChange={(e) => onConfig({ kpiId: e.target.value })} className={cfgInput}>
            <option value="">Select…</option>
            {kpis.map((k) => (
              <option key={k.id} value={k.id}>{k.name}</option>
            ))}
          </select>
        )}
      </div>
    );
  }
  const meta = STATUS_META[statusOf(kpi)];
  return (
    <div className="flex h-full flex-col p-3.5">
      <div className="flex items-center justify-between gap-2">
        <p className="truncate text-xs font-medium text-nexus-text">{kpi.name}</p>
        <span className={`h-2 w-2 shrink-0 rounded-full ${meta.dot}`} />
      </div>
      <p className="mt-1 font-mono text-2xl font-semibold tracking-tight text-nexus-text">{fmtValue(kpi, latestValue(kpi))}</p>
      <div className="mt-auto">
        <Sparkline series={seriesOf(kpi)} />
      </div>
    </div>
  );
}

function Note({ widget, onConfig }) {
  return (
    <textarea
      value={widget.config.text || ""}
      onChange={(e) => onConfig({ text: e.target.value })}
      placeholder="Write a note…"
      className="h-full w-full resize-none rounded-xl bg-amber-200/10 p-3 text-sm text-nexus-text placeholder:text-nexus-muted focus:outline-none"
    />
  );
}

export default function Widget({ widget, editing, onConfig, onNavigate, userName }) {
  switch (widget.type) {
    case "greeting":
      return <Greeting userName={userName} />;
    case "shortcut":
      return <Shortcut widget={widget} editing={editing} onConfig={onConfig} onNavigate={onNavigate} />;
    case "kpi":
      return <KpiTile widget={widget} editing={editing} onConfig={onConfig} />;
    case "note":
      return <Note widget={widget} onConfig={onConfig} />;
    default:
      return null;
  }
}
