// KPI dashboard data layer. Manually-tracked KPIs live in localStorage; auto-derived
// KPIs are fetched live from the backend. Access is funnelled through this module so a
// later swap to Supabase touches nothing in the UI.

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const KEY = "nexus-kpis";

export const CATEGORIES = [
  "Maintenance",
  "Vendor / SLA",
  "Energy / cost",
  "Compliance",
  "Incidents",
  "Service quality",
];

// One-click starting points — realistic FM KPIs with sensible targets/direction.
// direction "up" = higher is better, "down" = lower is better.
export const FM_TEMPLATES = [
  { name: "PPM Compliance", category: "Maintenance", unit: "%", target: 95, direction: "up", frequency: "monthly" },
  { name: "Reactive vs Planned", category: "Maintenance", unit: "%", target: 30, direction: "down", frequency: "monthly" },
  { name: "Mean Time To Repair", category: "Maintenance", unit: "hrs", target: 24, direction: "down", frequency: "monthly" },
  { name: "First-Time Fix Rate", category: "Maintenance", unit: "%", target: 85, direction: "up", frequency: "monthly" },
  { name: "Work Order Backlog", category: "Maintenance", unit: "", target: 10, direction: "down", frequency: "weekly" },
  { name: "SLA Adherence", category: "Vendor / SLA", unit: "%", target: 98, direction: "up", frequency: "monthly" },
  { name: "Cost per Work Order", category: "Vendor / SLA", unit: "₹", target: null, direction: "down", frequency: "monthly" },
  { name: "Energy Consumption", category: "Energy / cost", unit: "kWh", target: null, direction: "down", frequency: "monthly" },
  { name: "Maintenance Cost / m²", category: "Energy / cost", unit: "₹", target: null, direction: "down", frequency: "monthly" },
  { name: "Audit Pass Rate", category: "Compliance", unit: "%", target: 100, direction: "up", frequency: "quarterly" },
  { name: "Incident Count", category: "Incidents", unit: "", target: null, direction: "down", frequency: "monthly" },
  { name: "System Breaches", category: "Incidents", unit: "", target: 0, warn: 1, direction: "down", frequency: "monthly" },
  { name: "Compliance Breaches", category: "Compliance", unit: "", target: 0, warn: 1, direction: "down", frequency: "monthly" },
  { name: "Tenant Satisfaction", category: "Service quality", unit: "/5", target: 4.2, direction: "up", frequency: "quarterly" },
];

export const FREQUENCIES = ["weekly", "monthly", "quarterly"];

// ---- localStorage CRUD (manual KPIs) ----
export function loadKpis() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || [];
  } catch {
    return [];
  }
}
function persist(list) {
  localStorage.setItem(KEY, JSON.stringify(list));
  return list;
}
export function upsertKpi(kpi) {
  const all = loadKpis();
  const i = all.findIndex((k) => k.id === kpi.id);
  if (i >= 0) all[i] = kpi;
  else all.unshift(kpi);
  return persist(all);
}
export function deleteKpi(id) {
  return persist(loadKpis().filter((k) => k.id !== id));
}
export function newKpi(base) {
  return {
    id: crypto.randomUUID(),
    name: "",
    category: "Maintenance",
    unit: "",
    target: null,
    warn: null,
    direction: "up",
    frequency: "monthly",
    values: [],
    source: "manual",
    createdAt: Date.now(),
    ...base,
  };
}
export function addValue(id, period, value, note = "") {
  const all = loadKpis();
  const k = all.find((x) => x.id === id);
  if (!k) return all;
  k.values = (k.values || []).filter((v) => v.period !== period);
  k.values.push({ period, value: Number(value), note });
  k.values.sort((a, b) => (a.period < b.period ? -1 : 1));
  return persist(all);
}
export function removeValue(id, period) {
  const all = loadKpis();
  const k = all.find((x) => x.id === id);
  if (k) k.values = (k.values || []).filter((v) => v.period !== period);
  return persist(all);
}

// ---- Accessors that work for both manual (values[]) and derived (value + series) ----
export function seriesOf(kpi) {
  if (kpi.source === "derived") return kpi.series || [];
  return kpi.values || [];
}
export function latestValue(kpi) {
  if (kpi.source === "derived") return kpi.value ?? null;
  const s = seriesOf(kpi);
  return s.length ? s[s.length - 1].value : null;
}
function prevValue(kpi) {
  const s = seriesOf(kpi);
  return s.length >= 2 ? s[s.length - 2].value : null;
}

export function statusOf(kpi) {
  const v = latestValue(kpi);
  if (v == null || kpi.target == null) return "neutral";
  const t = kpi.target;
  // Optional explicit warning threshold; otherwise fall back to a ±10% band.
  if (kpi.direction === "up") {
    const warn = kpi.warn ?? 0.9 * t;
    return v >= t ? "green" : v >= warn ? "amber" : "red";
  }
  const warn = kpi.warn ?? 1.1 * t;
  return v <= t ? "green" : v <= warn ? "amber" : "red";
}

// Summary statistics over a KPI's history — powers the detail view.
export function statsOf(kpi) {
  const series = seriesOf(kpi);
  const vals = series.map((s) => Number(s.value)).filter((n) => !isNaN(n));
  if (!vals.length) return null;
  const last = vals[vals.length - 1];
  const prev = vals.length >= 2 ? vals[vals.length - 2] : null;
  const sum = vals.reduce((a, b) => a + b, 0);
  return {
    count: vals.length,
    min: Math.min(...vals),
    max: Math.max(...vals),
    avg: Math.round((sum / vals.length) * 10) / 10,
    last,
    changePct: prev != null && prev !== 0 ? Math.round(((last - prev) / Math.abs(prev)) * 1000) / 10 : null,
    pctToTarget: kpi.target ? Math.round((last / kpi.target) * 1000) / 10 : null,
    lastPeriod: series[series.length - 1].period,
  };
}
export function trendOf(kpi) {
  const v = latestValue(kpi);
  const p = prevValue(kpi);
  if (v == null || p == null) return null;
  const delta = v - p;
  const improving = kpi.direction === "up" ? delta > 0 : delta < 0;
  return { delta, improving, flat: delta === 0 };
}

export const STATUS_META = {
  green: { label: "On target", dot: "bg-emerald-400", text: "text-emerald-400", ring: "border-emerald-400/40" },
  amber: { label: "At risk", dot: "bg-amber-400", text: "text-amber-400", ring: "border-amber-400/40" },
  red: { label: "Off target", dot: "bg-red-400", text: "text-red-400", ring: "border-red-400/40" },
  neutral: { label: "Tracking", dot: "bg-nexus-muted", text: "text-nexus-muted", ring: "border-nexus-border" },
};

export function fmtValue(kpi, v) {
  if (v == null) return "—";
  const n = Number(v);
  const rounded = Math.abs(n) >= 100 ? Math.round(n) : Math.round(n * 10) / 10;
  const num = rounded.toLocaleString();
  return kpi.unit === "%" ? `${num}%` : kpi.unit ? `${num} ${kpi.unit}` : num;
}

// ---- Derived KPIs (backend) ----
export async function fetchDerived(email) {
  try {
    const url = new URL(`${API_BASE}/kpis/derived`);
    if (email) url.searchParams.set("email", email);
    const res = await fetch(url);
    if (!res.ok) return [];
    const data = await res.json();
    return data.kpis || [];
  } catch {
    return [];
  }
}

// ---- CSV import / export ----
const CSV_COLS = ["KPI", "Category", "Unit", "Target", "Direction", "Frequency", "Period", "Value", "Note"];

function csvCell(s) {
  const v = s == null ? "" : String(s);
  return /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
}
export function exportCsv(kpis) {
  const rows = [CSV_COLS.join(",")];
  kpis.forEach((k) => {
    const meta = [k.name, k.category, k.unit, k.target ?? "", k.direction, k.frequency];
    const vals = k.values || [];
    if (!vals.length) rows.push([...meta, "", "", ""].map(csvCell).join(","));
    else vals.forEach((v) => rows.push([...meta, v.period, v.value, v.note || ""].map(csvCell).join(",")));
  });
  return rows.join("\n");
}

function parseCsv(text) {
  const rows = [];
  let row = [], cell = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (c === '"') q = false;
      else cell += c;
    } else if (c === '"') q = true;
    else if (c === ",") { row.push(cell); cell = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(cell); rows.push(row); row = []; cell = "";
    } else cell += c;
  }
  if (cell.length || row.length) { row.push(cell); rows.push(row); }
  return rows.filter((r) => r.some((x) => x.trim() !== ""));
}

// Returns { kpis, error }. Groups rows by KPI name, rebuilding definitions + values.
export function importCsv(text) {
  const rows = parseCsv(text);
  if (!rows.length) return { kpis: [], error: "Empty file." };
  const head = rows[0].map((h) => h.trim().toLowerCase());
  const idx = (name) => head.indexOf(name.toLowerCase());
  if (idx("kpi") < 0 || idx("period") < 0 || idx("value") < 0)
    return { kpis: [], error: "CSV needs at least KPI, Period and Value columns." };

  const byName = new Map();
  for (const r of rows.slice(1)) {
    const name = (r[idx("kpi")] || "").trim();
    if (!name) continue;
    if (!byName.has(name)) {
      byName.set(
        name,
        newKpi({
          name,
          category: (r[idx("category")] || "Maintenance").trim() || "Maintenance",
          unit: (r[idx("unit")] || "").trim(),
          target: r[idx("target")] && !isNaN(Number(r[idx("target")])) ? Number(r[idx("target")]) : null,
          direction: (r[idx("direction")] || "up").trim() === "down" ? "down" : "up",
          frequency: (r[idx("frequency")] || "monthly").trim() || "monthly",
        })
      );
    }
    const period = (r[idx("period")] || "").trim();
    const value = r[idx("value")];
    if (period && value !== "" && !isNaN(Number(value))) {
      const k = byName.get(name);
      k.values.push({ period, value: Number(value), note: idx("note") >= 0 ? (r[idx("note")] || "").trim() : "" });
    }
  }
  const kpis = [...byName.values()];
  kpis.forEach((k) => k.values.sort((a, b) => (a.period < b.period ? -1 : 1)));
  return { kpis, error: kpis.length ? null : "No KPI rows found." };
}

export function downloadCsv(filename, text) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const todayISO = () => new Date().toISOString().slice(0, 10);

// Convert a plain calendar date into the KPI's period bucket, so users can just
// pick a date instead of typing "2026-08" / "2026-Q3".
export function periodFromDate(dateStr, frequency) {
  const d = dateStr ? new Date(dateStr) : new Date();
  if (isNaN(d)) return "";
  const y = d.getFullYear();
  if (frequency === "weekly") {
    const oneJan = new Date(y, 0, 1);
    const week = Math.ceil(((d - oneJan) / 86400000 + oneJan.getDay() + 1) / 7);
    return `${y}-W${String(week).padStart(2, "0")}`;
  }
  if (frequency === "quarterly") return `${y}-Q${Math.floor(d.getMonth() / 3) + 1}`;
  return `${y}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

// Default period label for a new data point, given the KPI's frequency.
export function defaultPeriod(frequency) {
  return periodFromDate(todayISO(), frequency);
}

// ---- Breach quick-logging (simple one-click tracking) ----
const BREACH = {
  system: { name: "System Breaches", category: "Incidents" },
  compliance: { name: "Compliance Breaches", category: "Compliance" },
};

// Find (or create) the breach counter, then increment this period's count by one.
export function logBreach(kind, note = "") {
  const spec = BREACH[kind];
  if (!spec) return null;
  let kpi = loadKpis().find((k) => k.name === spec.name);
  if (!kpi) {
    kpi = newKpi({ name: spec.name, category: spec.category, unit: "", target: 0, warn: 1, direction: "down", frequency: "monthly" });
    upsertKpi(kpi);
  }
  const period = defaultPeriod("monthly");
  const current = (loadKpis().find((k) => k.id === kpi.id)?.values || []).find((v) => v.period === period);
  addValue(kpi.id, period, (current?.value || 0) + 1, note);
  return kpi.id;
}
