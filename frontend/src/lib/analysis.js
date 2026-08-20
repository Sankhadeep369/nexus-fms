// Issue-analysis client: calls the backend engine, extracts root causes per method,
// and handles local history + Markdown export. No app-specific state.

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const HKEY = "nexus-analyses";

export const METHODS = [
  { id: "5whys", name: "5 Whys", blurb: "Ask “why” repeatedly down to the root cause." },
  { id: "ishikawa", name: "Ishikawa (Fishbone)", blurb: "Group candidate causes into 6 categories." },
  { id: "fta", name: "Fault Tree (FTA)", blurb: "Decompose the failure through AND/OR gates." },
  { id: "rca", name: "RCA Report", blurb: "Problem → factors → root causes, structured." },
];

export async function generateAnalysis({ method, issue, grounded, owner }) {
  const res = await fetch(`${API_BASE}/analysis/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ method, issue, grounded, owner }),
  });
  if (!res.ok) throw new Error(`Analysis failed (${res.status})`);
  const data = await res.json();
  if (data.error) throw new Error(data.error);
  return data;
}

export async function generateCapa({ issue, rootCauses }) {
  const res = await fetch(`${API_BASE}/analysis/capa`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ issue, root_causes: rootCauses }),
  });
  if (!res.ok) return { corrective: [], preventive: [] };
  return res.json();
}

// Flatten a fault-tree to its leaf (basic-event) labels.
function leaves(node, out = []) {
  if (!node) return out;
  if (!node.children || node.children.length === 0) out.push(node.label);
  else node.children.forEach((c) => leaves(c, out));
  return out;
}

// The root cause(s) a method has landed on — fed to the CAPA step.
export function rootCausesOf(method, data) {
  if (!data) return [];
  if (method === "5whys") return [data.root_cause].filter(Boolean);
  if (method === "rca") return data.root_causes || [];
  if (method === "ishikawa")
    return Object.values(data.categories || {})
      .flat()
      .filter((c) => c.selected)
      .map((c) => c.text);
  if (method === "fta") return leaves(data.tree);
  return [];
}

// ---- Local history (localStorage) ----
export function loadAnalyses() {
  try {
    return JSON.parse(localStorage.getItem(HKEY)) || [];
  } catch {
    return [];
  }
}
export function saveAnalysis(entry) {
  const all = [entry, ...loadAnalyses().filter((a) => a.id !== entry.id)].slice(0, 50);
  localStorage.setItem(HKEY, JSON.stringify(all));
  return all;
}
export function deleteAnalysis(id) {
  const all = loadAnalyses().filter((a) => a.id !== id);
  localStorage.setItem(HKEY, JSON.stringify(all));
  return all;
}

// ---- Markdown export ----
function treeMd(node, depth = 0) {
  if (!node) return "";
  const pad = "  ".repeat(depth);
  const gate = node.gate ? ` _(${node.gate})_` : "";
  let s = `${pad}- ${node.label}${gate}\n`;
  (node.children || []).forEach((c) => (s += treeMd(c, depth + 1)));
  return s;
}

export function analysisToMarkdown(method, issue, data, capa) {
  const name = METHODS.find((m) => m.id === method)?.name ?? method;
  let md = `# Issue Analysis — ${name}\n\n**Issue:** ${issue}\n\n`;
  if (method === "5whys") {
    (data.whys || []).forEach((w, i) => (md += `**${i + 1}. ${w.why}**\n${w.cause}\n\n`));
    md += `**Root cause:** ${data.root_cause || "—"}\n\n`;
  } else if (method === "ishikawa") {
    Object.entries(data.categories || {}).forEach(([cat, causes]) => {
      const sel = causes.filter((c) => c.selected);
      if (sel.length) md += `**${cat}**\n${sel.map((c) => `- ${c.text}`).join("\n")}\n\n`;
    });
  } else if (method === "fta") {
    md += `**Top event:** ${data.top_event}\n\n${treeMd(data.tree)}\n`;
  } else if (method === "rca") {
    md += `**Impact:** ${data.impact || "—"}\n\n`;
    if (data.timeline?.length) md += `**Timeline**\n${data.timeline.map((t) => `- ${t}`).join("\n")}\n\n`;
    if (data.contributing_factors?.length)
      md += `**Contributing factors**\n${data.contributing_factors.map((t) => `- ${t}`).join("\n")}\n\n`;
    if (data.root_causes?.length) md += `**Root causes**\n${data.root_causes.map((t) => `- ${t}`).join("\n")}\n\n`;
  }
  if (capa && (capa.corrective?.length || capa.preventive?.length)) {
    md += `## Actions\n`;
    if (capa.corrective?.length) md += `**Corrective**\n${capa.corrective.map((t) => `- ${t}`).join("\n")}\n\n`;
    if (capa.preventive?.length) md += `**Preventive**\n${capa.preventive.map((t) => `- ${t}`).join("\n")}\n\n`;
  }
  return md.trim();
}

export function downloadMarkdown(filename, md) {
  const url = URL.createObjectURL(new Blob([md], { type: "text/markdown" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
