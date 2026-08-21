// Hand-rolled SVG charts — no chart library, ~0 bundle cost, theme-aware via CSS vars.

// Tiny inline trend line for a KPI card.
export function Sparkline({ series, className = "" }) {
  const pts = (series || []).map((s) => Number(s.value)).filter((n) => !isNaN(n));
  if (pts.length < 2) return <div className={`h-8 ${className}`} />;
  const W = 120, H = 32, pad = 3;
  const min = Math.min(...pts), max = Math.max(...pts);
  const span = max - min || 1;
  const x = (i) => pad + (i * (W - 2 * pad)) / (pts.length - 1);
  const y = (v) => H - pad - ((v - min) / span) * (H - 2 * pad);
  const d = pts.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={`w-full ${className}`} preserveAspectRatio="none">
      <path d={d} fill="none" stroke="rgb(var(--nexus-accent))" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(pts.length - 1)} cy={y(pts[pts.length - 1])} r="2.5" fill="rgb(var(--nexus-accent))" />
    </svg>
  );
}

// Full history chart with an optional target line and value/period labels.
export function LineChart({ series, target, unit }) {
  const data = (series || []).map((s) => ({ period: s.period, value: Number(s.value) })).filter((s) => !isNaN(s.value));
  if (data.length < 2) {
    return (
      <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-nexus-border text-xs text-nexus-muted">
        Add at least two data points to see a trend.
      </div>
    );
  }
  const W = 640, H = 200, L = 44, R = 12, T = 14, B = 30;
  const vals = data.map((d) => d.value);
  const lo = Math.min(...vals, target ?? Infinity);
  const hi = Math.max(...vals, target ?? -Infinity);
  const pad = (hi - lo) * 0.12 || 1;
  const min = lo - pad, max = hi + pad, span = max - min || 1;
  const x = (i) => L + (i * (W - L - R)) / (data.length - 1);
  const y = (v) => T + (1 - (v - min) / span) * (H - T - B);
  const line = data.map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(d.value).toFixed(1)}`).join(" ");
  const area = `${line} L${x(data.length - 1).toFixed(1)},${H - B} L${x(0).toFixed(1)},${H - B} Z`;
  const ticks = [max, (max + min) / 2, min];
  const every = Math.ceil(data.length / 6);

  return (
    <div className="scroll-thin overflow-x-auto rounded-xl border border-nexus-border bg-nexus-panel p-2">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ minWidth: 420 }}>
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={L} y1={y(t)} x2={W - R} y2={y(t)} stroke="rgb(var(--nexus-border))" strokeWidth="1" opacity="0.5" />
            <text x={L - 6} y={y(t) + 3} textAnchor="end" style={{ fill: "rgb(var(--nexus-muted))" }} className="text-[9px]">
              {Math.round(t * 10) / 10}
            </text>
          </g>
        ))}
        {target != null && (
          <>
            <line x1={L} y1={y(target)} x2={W - R} y2={y(target)} stroke="rgb(var(--nexus-accent))" strokeWidth="1.2" strokeDasharray="4 3" opacity="0.8" />
            <text x={W - R} y={y(target) - 4} textAnchor="end" style={{ fill: "rgb(var(--nexus-accent))" }} className="text-[9px] font-semibold">
              target {target}{unit === "%" ? "%" : ""}
            </text>
          </>
        )}
        <path d={area} fill="rgb(var(--nexus-accent))" opacity="0.08" />
        <path d={line} fill="none" stroke="rgb(var(--nexus-accent))" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        {data.map((d, i) => (
          <circle key={i} cx={x(i)} cy={y(d.value)} r="2.5" fill="rgb(var(--nexus-accent))" />
        ))}
        {data.map((d, i) =>
          i % every === 0 || i === data.length - 1 ? (
            <text key={i} x={x(i)} y={H - 10} textAnchor="middle" style={{ fill: "rgb(var(--nexus-muted))" }} className="text-[9px]">
              {d.period}
            </text>
          ) : null
        )}
      </svg>
    </div>
  );
}
