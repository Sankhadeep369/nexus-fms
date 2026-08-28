// Personal "Home" canvas layout — per user, stored on this device. A free-form grid
// of draggable/resizable widgets. Funnelled through this module so it could later be
// promoted to server-side (per-account) storage without touching the UI.

export const GRID = 16; // snap size in px
export const CANVAS_W = 1120; // logical canvas width; scrolls on narrow screens
export const MIN_W = 128;
export const MIN_H = 80;

export const WIDGET_TYPES = [
  { type: "greeting", label: "Greeting", w: 400, h: 96 },
  { type: "shortcut", label: "Shortcut", w: 208, h: 96 },
  { type: "kpi", label: "KPI tile", w: 256, h: 160 },
  { type: "note", label: "Sticky note", w: 240, h: 176 },
];

export const snap = (v) => Math.round(v / GRID) * GRID;

const key = (username) => `nexus-home-${username || "guest"}`;

export function newWidget(type, at = {}) {
  const spec = WIDGET_TYPES.find((w) => w.type === type) || WIDGET_TYPES[0];
  const config =
    type === "shortcut"
      ? { target: "chat", label: "Open Chat" }
      : type === "note"
      ? { text: "" }
      : type === "kpi"
      ? { kpiId: null }
      : {};
  return {
    id: crypto.randomUUID(),
    type,
    x: snap(at.x ?? 32),
    y: snap(at.y ?? 32),
    w: spec.w,
    h: spec.h,
    config,
  };
}

export function defaultLayout() {
  return [
    { ...newWidget("greeting", { x: 32, y: 32 }), w: 400 },
    { ...newWidget("shortcut", { x: 32, y: 160 }), config: { target: "chat", label: "Ask NEXUS" } },
    { ...newWidget("shortcut", { x: 256, y: 160 }), config: { target: "agents", label: "Run an agent" } },
    { ...newWidget("shortcut", { x: 480, y: 160 }), config: { target: "dashboard", label: "KPI Dashboard" } },
  ];
}

export function loadLayout(username) {
  try {
    const raw = JSON.parse(localStorage.getItem(key(username)));
    if (Array.isArray(raw)) return raw;
  } catch {
    /* fall through */
  }
  return defaultLayout();
}

export function saveLayout(username, widgets) {
  localStorage.setItem(key(username), JSON.stringify(widgets));
}

export function resetLayout(username) {
  localStorage.removeItem(key(username));
  return defaultLayout();
}
