// Builds a clean, self-contained HTML KPI report and opens it in a new window for
// printing / saving as PDF. No dependencies, no backend.

import { fmtValue, latestValue, statsOf, statusOf, STATUS_META } from "./kpis";

const STATUS_COLOR = { green: "#10b981", amber: "#f59e0b", red: "#ef4444", neutral: "#64748b" };

const esc = (s) =>
  String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

export function openKpiReport(kpis, brandName = "NEXUS") {
  const now = new Date();
  const counts = { green: 0, amber: 0, red: 0, neutral: 0 };
  kpis.forEach((k) => (counts[statusOf(k)] += 1));
  const atRisk = kpis.filter((k) => ["red", "amber"].includes(statusOf(k)));

  const row = (k) => {
    const st = statusOf(k);
    const s = statsOf(k);
    return `<tr>
      <td><span class="dot" style="background:${STATUS_COLOR[st]}"></span>${esc(k.name)}</td>
      <td>${esc(k.category)}</td>
      <td class="num">${esc(fmtValue(k, latestValue(k)))}</td>
      <td class="num">${k.target == null ? "—" : esc(k.target)}</td>
      <td class="num">${s && s.changePct != null ? `${s.changePct > 0 ? "+" : ""}${s.changePct}%` : "—"}</td>
      <td style="color:${STATUS_COLOR[st]}">${STATUS_META[st].label}</td>
    </tr>`;
  };

  const html = `<!doctype html><html><head><meta charset="utf-8"><title>${esc(brandName)} KPI Report</title>
  <style>
    *{box-sizing:border-box}
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#0f172a;margin:40px;font-size:13px}
    h1{font-size:20px;margin:0}
    .sub{color:#64748b;margin:4px 0 20px}
    .cards{display:flex;gap:10px;margin-bottom:22px;flex-wrap:wrap}
    .card{border:1px solid #e2e8f0;border-radius:10px;padding:10px 14px;min-width:96px}
    .card .n{font-size:22px;font-weight:600}
    .card .l{color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.04em}
    table{width:100%;border-collapse:collapse;margin-top:8px}
    th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #e2e8f0}
    th{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#64748b}
    td.num,th.num{text-align:right}
    .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:8px;vertical-align:middle}
    .section{font-size:12px;font-weight:600;margin:22px 0 6px}
    .muted{color:#64748b}
    @media print{body{margin:16px}}
  </style></head><body>
    <h1>${esc(brandName)} — KPI Report</h1>
    <div class="sub">Generated ${now.toLocaleString()}</div>
    <div class="cards">
      <div class="card"><div class="n">${kpis.length}</div><div class="l">Tracked</div></div>
      <div class="card"><div class="n" style="color:${STATUS_COLOR.green}">${counts.green}</div><div class="l">On target</div></div>
      <div class="card"><div class="n" style="color:${STATUS_COLOR.amber}">${counts.amber}</div><div class="l">At risk</div></div>
      <div class="card"><div class="n" style="color:${STATUS_COLOR.red}">${counts.red}</div><div class="l">Off target</div></div>
    </div>
    ${atRisk.length ? `<div class="section">Needs attention</div><div class="muted">${atRisk.map((k) => esc(k.name)).join(" · ")}</div>` : ""}
    <div class="section">All KPIs</div>
    <table>
      <thead><tr><th>KPI</th><th>Category</th><th class="num">Latest</th><th class="num">Target</th><th class="num">Δ prev</th><th>Status</th></tr></thead>
      <tbody>${kpis.map(row).join("") || `<tr><td colspan="6" class="muted">No KPIs yet.</td></tr>`}</tbody>
    </table>
  </body></html>`;

  const w = window.open("", "_blank");
  if (!w) return;
  w.document.write(html);
  w.document.close();
  w.focus();
  setTimeout(() => w.print(), 250);
}
