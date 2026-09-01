import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext";
import {
  CANVAS_W,
  loadLayout,
  MIN_H,
  MIN_W,
  newWidget,
  resetLayout,
  saveLayout,
  snap,
  WIDGET_TYPES,
} from "../lib/home";
import Widget from "./home/widgets";
import { PlusIcon, XIcon } from "./icons";
import OnboardingChecklist from "./OnboardingChecklist";

export default function HomePage({ onNavigate, onOpenProfile }) {
  const { user } = useAuth();
  const username = user?.username;
  const [widgets, setWidgets] = useState(() => loadLayout(username));
  const [editing, setEditing] = useState(false);
  const [gesture, setGesture] = useState(null); // {id, mode, sx, sy, ox, oy, ow, oh}
  const [showAdd, setShowAdd] = useState(false);

  const update = (next) => {
    setWidgets(next);
    saveLayout(username, next);
  };
  const patchConfig = (id, cfg) =>
    update(widgets.map((w) => (w.id === id ? { ...w, config: { ...w.config, ...cfg } } : w)));
  const removeWidget = (id) => update(widgets.filter((w) => w.id !== id));

  const add = (type) => {
    const bottom = widgets.reduce((m, w) => Math.max(m, w.y + w.h), 0);
    update([...widgets, newWidget(type, { x: 32, y: bottom + 16 })]);
    setShowAdd(false);
  };

  // Drag / resize via window-level pointer tracking (works with touch too).
  useEffect(() => {
    if (!gesture) return;
    const onMove = (e) => {
      const dx = e.clientX - gesture.sx;
      const dy = e.clientY - gesture.sy;
      setWidgets((cur) =>
        cur.map((w) => {
          if (w.id !== gesture.id) return w;
          if (gesture.mode === "move") {
            const x = Math.max(0, Math.min(CANVAS_W - w.w, snap(gesture.ox + dx)));
            return { ...w, x, y: Math.max(0, snap(gesture.oy + dy)) };
          }
          return {
            ...w,
            w: Math.min(CANVAS_W, Math.max(MIN_W, snap(gesture.ow + dx))),
            h: Math.max(MIN_H, snap(gesture.oh + dy)),
          };
        })
      );
    };
    const onUp = () => {
      setGesture(null);
      setWidgets((cur) => {
        saveLayout(username, cur);
        return cur;
      });
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [gesture, username]);

  const startMove = (e, w) => {
    e.preventDefault();
    setGesture({ id: w.id, mode: "move", sx: e.clientX, sy: e.clientY, ox: w.x, oy: w.y });
  };
  const startResize = (e, w) => {
    e.preventDefault();
    e.stopPropagation();
    setGesture({ id: w.id, mode: "resize", sx: e.clientX, sy: e.clientY, ow: w.w, oh: w.h });
  };

  const canvasH = useMemo(() => Math.max(560, widgets.reduce((m, w) => Math.max(m, w.y + w.h), 0) + 48), [widgets]);

  return (
    <div className="scroll-thin flex-1 overflow-auto px-4 py-6 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="font-display text-xl font-semibold text-nexus-text">Home</h1>
            <p className="mt-1 text-sm text-nexus-muted">Your personal space — {editing ? "drag, resize, and add widgets." : "arrange it however you like."}</p>
          </div>
          <div className="flex items-center gap-2">
            {editing && (
              <>
                <div className="relative">
                  <button type="button" onClick={() => setShowAdd((v) => !v)} className="flex items-center gap-1.5 rounded-lg border border-nexus-border px-2.5 py-1.5 text-xs text-nexus-text hover:border-nexus-accent/50">
                    <PlusIcon className="h-3.5 w-3.5" /> Add widget
                  </button>
                  {showAdd && (
                    <>
                      <button type="button" aria-label="Close menu" className="fixed inset-0 z-10 cursor-default" onClick={() => setShowAdd(false)} />
                      <div className="absolute right-0 z-20 mt-1.5 w-44 rounded-xl border border-nexus-border bg-nexus-panel p-1.5 shadow-glow">
                        {WIDGET_TYPES.map((t) => (
                          <button key={t.type} type="button" onClick={() => add(t.type)} className="block w-full rounded-lg px-2.5 py-1.5 text-left text-xs text-nexus-text hover:bg-nexus-panel2">
                            {t.label}
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                </div>
                <button type="button" onClick={() => update(resetLayout(username))} className="rounded-lg border border-nexus-border px-2.5 py-1.5 text-xs text-nexus-muted hover:text-nexus-text">
                  Reset
                </button>
              </>
            )}
            <button
              type="button"
              onClick={() => setEditing((v) => !v)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium ${editing ? "bg-gradient-to-br from-nexus-accent to-nexus-accent2 text-nexus-bg" : "border border-nexus-border text-nexus-text hover:border-nexus-accent/50"}`}
            >
              {editing ? "Done" : "Customize"}
            </button>
          </div>
        </div>

        {!editing && <OnboardingChecklist onNavigate={onNavigate} onOpenProfile={onOpenProfile} />}

        <div
          className={`relative rounded-2xl ${editing ? "border border-dashed border-nexus-border bg-nexus-panel2/30 bg-grid" : ""}`}
          style={{ width: "100%", minWidth: editing ? CANVAS_W : undefined, height: canvasH }}
        >
          {widgets.map((w) => (
            <div
              key={w.id}
              className={`absolute overflow-hidden rounded-2xl ${w.type === "note" ? "" : "border border-nexus-border bg-nexus-panel"} ${editing ? "ring-1 ring-nexus-accent/30" : ""} flex flex-col`}
              style={{ left: w.x, top: w.y, width: w.w, height: w.h }}
            >
              {editing && (
                <div
                  onPointerDown={(e) => startMove(e, w)}
                  className="flex h-6 shrink-0 cursor-move items-center justify-between bg-nexus-panel2 px-2 text-[10px] text-nexus-muted"
                >
                  <span className="select-none">⋮⋮ {w.type}</span>
                  <button type="button" onClick={() => removeWidget(w.id)} className="rounded p-0.5 hover:text-red-400">
                    <XIcon className="h-3 w-3" />
                  </button>
                </div>
              )}
              <div className="min-h-0 flex-1">
                <Widget widget={w} editing={editing} onConfig={(cfg) => patchConfig(w.id, cfg)} onNavigate={onNavigate} userName={user?.name || "there"} />
              </div>
              {editing && (
                <div
                  onPointerDown={(e) => startResize(e, w)}
                  className="absolute bottom-0 right-0 h-4 w-4 cursor-nwse-resize"
                  style={{ background: "linear-gradient(135deg, transparent 50%, rgb(var(--nexus-accent)) 50%)" }}
                />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
