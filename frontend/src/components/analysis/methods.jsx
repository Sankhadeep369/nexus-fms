import { PlusIcon, XIcon } from "../icons";

const field =
  "w-full rounded-lg border border-nexus-border bg-nexus-bg px-2.5 py-1.5 text-sm text-nexus-text placeholder:text-nexus-muted focus:border-nexus-accent/60 focus:outline-none";

// ── Editable string list ────────────────────────────────────────────────────
export function ListEditor({ items, onChange, placeholder }) {
  const set = (i, v) => onChange(items.map((x, j) => (j === i ? v : x)));
  const add = () => onChange([...items, ""]);
  const del = (i) => onChange(items.filter((_, j) => j !== i));
  return (
    <div className="space-y-1.5">
      {items.map((it, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <input value={it} onChange={(e) => set(i, e.target.value)} placeholder={placeholder} className={field} />
          <button type="button" onClick={() => del(i)} className="shrink-0 rounded p-1 text-nexus-muted hover:text-red-400" aria-label="Remove">
            <XIcon className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
      <button type="button" onClick={add} className="flex items-center gap-1 text-xs font-medium text-nexus-accent hover:text-nexus-accent2">
        <PlusIcon className="h-3.5 w-3.5" /> Add
      </button>
    </div>
  );
}

// ── 5 Whys — editable vertical chain ────────────────────────────────────────
export function FiveWhys({ data, onChange }) {
  const whys = data.whys || [];
  const setWhy = (i, k, v) => onChange({ ...data, whys: whys.map((w, j) => (j === i ? { ...w, [k]: v } : w)) });
  const addWhy = () => onChange({ ...data, whys: [...whys, { why: "", cause: "" }] });
  const delWhy = (i) => onChange({ ...data, whys: whys.filter((_, j) => j !== i) });

  return (
    <div className="space-y-2">
      <div className="rounded-xl border border-nexus-border bg-nexus-panel2 px-3 py-2 text-sm text-nexus-text">
        <span className="text-[11px] font-medium uppercase tracking-wide text-nexus-muted">Problem</span>
        <p className="mt-0.5">{data.problem}</p>
      </div>
      {whys.map((w, i) => (
        <div key={i} className="relative pl-4">
          <span className="absolute left-1 top-0 h-full w-px bg-nexus-border" />
          <div className="rounded-xl border border-nexus-border bg-nexus-panel px-3 py-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold text-nexus-accent">Why {i + 1}?</span>
              <button type="button" onClick={() => delWhy(i)} className="rounded p-0.5 text-nexus-muted hover:text-red-400"><XIcon className="h-3 w-3" /></button>
            </div>
            <input value={w.why} onChange={(e) => setWhy(i, "why", e.target.value)} className={`${field} mt-1`} placeholder="Why did it happen?" />
            <input value={w.cause} onChange={(e) => setWhy(i, "cause", e.target.value)} className={`${field} mt-1.5`} placeholder="Because…" />
          </div>
        </div>
      ))}
      <button type="button" onClick={addWhy} className="ml-4 flex items-center gap-1 text-xs font-medium text-nexus-accent hover:text-nexus-accent2">
        <PlusIcon className="h-3.5 w-3.5" /> Add a why
      </button>
      <div className="rounded-xl border border-nexus-accent/40 bg-nexus-accent/5 px-3 py-2">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-nexus-accent">Root cause</span>
        <textarea rows={2} value={data.root_cause || ""} onChange={(e) => onChange({ ...data, root_cause: e.target.value })} className={`${field} mt-1 resize-none`} />
      </div>
    </div>
  );
}

// ── Ishikawa — category checklists + fishbone SVG ───────────────────────────
const CATS = ["Manpower", "Method", "Machine", "Material", "Measurement", "Environment"];

export function Ishikawa({ data, onChange }) {
  const cats = data.categories || {};
  const toggle = (cat, i) =>
    onChange({ ...data, categories: { ...cats, [cat]: cats[cat].map((c, j) => (j === i ? { ...c, selected: !c.selected } : c)) } });
  const addCause = (cat, text) => text.trim() && onChange({ ...data, categories: { ...cats, [cat]: [...(cats[cat] || []), { text: text.trim(), selected: true }] } });

  return (
    <div className="space-y-4">
      <Fishbone problem={data.problem} categories={cats} />
      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
        {CATS.map((cat) => (
          <div key={cat} className="rounded-xl border border-nexus-border bg-nexus-panel p-2.5">
            <p className="mb-1.5 text-xs font-semibold text-nexus-violet">{cat}</p>
            <div className="space-y-1">
              {(cats[cat] || []).map((c, i) => (
                <label key={i} className="flex items-start gap-2 text-xs text-nexus-text">
                  <input type="checkbox" checked={c.selected} onChange={() => toggle(cat, i)} className="mt-0.5 accent-nexus-accent" />
                  <span className={c.selected ? "" : "text-nexus-muted line-through"}>{c.text}</span>
                </label>
              ))}
            </div>
            <input
              className={`${field} mt-1.5`}
              placeholder="Add a cause…"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  addCause(cat, e.target.value);
                  e.target.value = "";
                }
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

function Fishbone({ problem, categories }) {
  const W = 720, H = 340, midY = H / 2, spineX0 = 30, spineX1 = W - 150;
  const bones = CATS.map((cat, i) => {
    const up = i < 3;
    const t = (i % 3) + 1; // 1..3 along spine
    const bx = spineX0 + ((spineX1 - spineX0) * t) / 4;
    const endX = bx - 55, endY = up ? midY - 120 : midY + 120;
    return { cat, bx, endX, endY, up, causes: (categories[cat] || []).filter((c) => c.selected).map((c) => c.text) };
  });
  return (
    <div className="scroll-thin overflow-x-auto rounded-xl border border-nexus-border bg-nexus-panel p-2">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ minWidth: 560 }}>
        <line x1={spineX0} y1={midY} x2={spineX1} y2={midY} stroke="rgb(var(--nexus-border))" strokeWidth="2" />
        <polygon points={`${spineX1},${midY - 10} ${spineX1 + 16},${midY} ${spineX1},${midY + 10}`} fill="rgb(var(--nexus-accent))" />
        <foreignObject x={spineX1 + 12} y={midY - 34} width="140" height="68">
          <div className="flex h-full items-center rounded-lg border border-nexus-accent/50 bg-nexus-accent/10 px-2 text-[10px] font-medium leading-tight text-nexus-text">
            {problem}
          </div>
        </foreignObject>
        {bones.map((b) => (
          <g key={b.cat}>
            <line x1={b.bx} y1={midY} x2={b.endX} y2={b.endY} stroke="rgb(var(--nexus-border))" strokeWidth="1.5" />
            <text x={b.endX - 4} y={b.up ? b.endY - 6 : b.endY + 14} textAnchor="end" className="fill-nexus-violet text-[11px] font-semibold" style={{ fill: "rgb(var(--nexus-violet))" }}>
              {b.cat}
            </text>
            {b.causes.slice(0, 4).map((c, j) => (
              <text
                key={j}
                x={b.endX + 20 + j * ((b.bx - b.endX) / 5)}
                y={(b.up ? b.endY : b.endY) + (b.up ? 14 + j * 15 : -6 - j * 15)}
                className="text-[9px]"
                style={{ fill: "rgb(var(--nexus-muted))" }}
              >
                • {c.length > 26 ? c.slice(0, 26) + "…" : c}
              </text>
            ))}
          </g>
        ))}
      </svg>
    </div>
  );
}

// ── Fault Tree — recursive HTML tree ────────────────────────────────────────
export function FaultTree({ data, onChange }) {
  const setTree = (tree) => onChange({ ...data, tree });
  return (
    <div className="scroll-thin overflow-x-auto rounded-xl border border-nexus-border bg-nexus-panel p-4">
      <div className="flex min-w-max justify-center">
        <TreeNode node={data.tree} onChange={setTree} onDelete={null} />
      </div>
    </div>
  );
}

function TreeNode({ node, onChange, onDelete }) {
  if (!node) return null;
  const setLabel = (v) => onChange({ ...node, label: v });
  const setGate = (g) => onChange({ ...node, gate: g });
  const setChild = (i, c) => onChange({ ...node, children: node.children.map((x, j) => (j === i ? c : x)) });
  const delChild = (i) => onChange({ ...node, children: node.children.filter((_, j) => j !== i) });
  const kids = node.children || [];
  return (
    <div className="flex flex-col items-center">
      <div className="group relative flex items-center gap-1 rounded-lg border border-nexus-border bg-nexus-panel2 px-2 py-1">
        <input value={node.label} onChange={(e) => setLabel(e.target.value)} className="w-40 bg-transparent text-center text-[11px] text-nexus-text focus:outline-none" />
        {onDelete && (
          <button type="button" onClick={onDelete} className="rounded p-0.5 text-nexus-muted opacity-0 hover:text-red-400 group-hover:opacity-100"><XIcon className="h-3 w-3" /></button>
        )}
      </div>
      {kids.length > 0 && (
        <>
          <span className="h-3 w-px bg-nexus-border" />
          <select value={node.gate || "OR"} onChange={(e) => setGate(e.target.value)} className="rounded border border-nexus-border bg-nexus-panel px-1 py-0.5 text-[10px] font-semibold text-nexus-accent">
            <option>OR</option>
            <option>AND</option>
          </select>
          <span className="h-3 w-px bg-nexus-border" />
          <div className="flex items-start gap-4">
            {kids.map((c, i) => (
              <TreeNode key={i} node={c} onChange={(nc) => setChild(i, nc)} onDelete={() => delChild(i)} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ── RCA report — editable structured form ───────────────────────────────────
export function RcaReport({ data, onChange }) {
  const set = (k, v) => onChange({ ...data, [k]: v });
  const Section = ({ label, k }) => (
    <div>
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-nexus-muted">{label}</p>
      <ListEditor items={data[k] || []} onChange={(v) => set(k, v)} placeholder={`Add ${label.toLowerCase()}…`} />
    </div>
  );
  return (
    <div className="space-y-4">
      <div>
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-nexus-muted">Impact</p>
        <textarea rows={2} value={data.impact || ""} onChange={(e) => set("impact", e.target.value)} className={`${field} resize-none`} />
      </div>
      <Section label="Timeline" k="timeline" />
      <Section label="Contributing factors" k="contributing_factors" />
      <div className="rounded-xl border border-nexus-accent/40 bg-nexus-accent/5 p-2.5">
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-nexus-accent">Root causes</p>
        <ListEditor items={data.root_causes || []} onChange={(v) => set("root_causes", v)} placeholder="Add root cause…" />
      </div>
    </div>
  );
}
