import { useState } from "react";
import { useAppConfig } from "../context/AppConfigContext";
import {
  deleteSnapshot,
  FEATURE_IDS,
  FEATURE_LABELS,
  listSnapshots,
  restoreSnapshot,
  saveSnapshot,
} from "../lib/appconfig";
import { TrashIcon } from "./icons";

const field =
  "w-full rounded-lg border border-nexus-border bg-nexus-bg px-2.5 py-1.5 text-sm text-nexus-text placeholder:text-nexus-muted focus:border-nexus-accent/60 focus:outline-none";
const card = "rounded-2xl border border-nexus-border bg-nexus-panel p-4";
const heading = "mb-3 text-[11px] font-semibold uppercase tracking-wider text-nexus-muted";

export default function AdminConfig() {
  const { config, update } = useAppConfig();
  const [draft, setDraft] = useState(config);
  const [snaps, setSnaps] = useState(listSnapshots);
  const [label, setLabel] = useState("");

  const dirty = JSON.stringify(draft) !== JSON.stringify(config);
  const setBranding = (patch) => setDraft((d) => ({ ...d, branding: { ...d.branding, ...patch } }));
  const setAnnounce = (patch) => setDraft((d) => ({ ...d, announcement: { ...d.announcement, ...patch } }));
  const setFeature = (id, v) => setDraft((d) => ({ ...d, features: { ...d.features, [id]: v } }));

  const restore = (id) => {
    if (!window.confirm("Restore this snapshot? Current settings and users will be replaced, then the app reloads.")) return;
    if (restoreSnapshot(id)) window.location.reload();
  };

  return (
    <div className="space-y-4">
      {/* Branding */}
      <div className={card}>
        <p className={heading}>Branding</p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="text-xs text-nexus-muted">
            App name
            <input value={draft.branding.name} onChange={(e) => setBranding({ name: e.target.value })} className={`${field} mt-1`} placeholder="NEXUS" />
          </label>
          <div className="text-xs text-nexus-muted">
            Accent color
            <div className="mt-1 flex items-center gap-2">
              <input type="color" value={draft.branding.accent || "#2dd4bf"} onChange={(e) => setBranding({ accent: e.target.value })} className="h-8 w-10 shrink-0 rounded border border-nexus-border bg-nexus-bg" />
              <input value={draft.branding.accent} onChange={(e) => setBranding({ accent: e.target.value })} placeholder="#2dd4bf (blank = default)" className={field} />
              {draft.branding.accent && (
                <button type="button" onClick={() => setBranding({ accent: "" })} className="shrink-0 text-[11px] text-nexus-muted underline decoration-dotted hover:text-nexus-text">reset</button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Announcement */}
      <div className={card}>
        <p className={heading}>Announcement banner</p>
        <label className="flex items-center gap-2 text-xs text-nexus-text">
          <input type="checkbox" checked={draft.announcement.enabled} onChange={(e) => setAnnounce({ enabled: e.target.checked })} className="accent-nexus-accent" />
          Show a banner to all users
        </label>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row">
          <input value={draft.announcement.text} onChange={(e) => setAnnounce({ text: e.target.value })} placeholder="e.g. Scheduled maintenance Saturday 9pm" className={field} />
          <select value={draft.announcement.level} onChange={(e) => setAnnounce({ level: e.target.value })} className={`${field} sm:w-32`}>
            <option value="info">Info</option>
            <option value="warn">Warning</option>
          </select>
        </div>
      </div>

      {/* Feature toggles */}
      <div className={card}>
        <p className={heading}>Global feature toggles</p>
        <p className="mb-2 text-xs text-nexus-muted">Turn a tool or agent off for everyone, regardless of individual permissions.</p>
        <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
          {FEATURE_IDS.map((id) => (
            <label key={id} className="flex items-center gap-2 text-xs text-nexus-text">
              <input type="checkbox" checked={draft.features[id] !== false} onChange={(e) => setFeature(id, e.target.checked)} className="accent-nexus-accent" />
              {FEATURE_LABELS[id]}
            </label>
          ))}
        </div>
      </div>

      <button type="button" onClick={() => update(draft)} disabled={!dirty} className="rounded-lg bg-gradient-to-br from-nexus-accent to-nexus-accent2 px-4 py-2 text-sm font-medium text-nexus-bg disabled:opacity-40">
        {dirty ? "Save settings" : "Saved"}
      </button>

      {/* Snapshots / rollback */}
      <div className={card}>
        <p className={heading}>Config snapshots &amp; rollback</p>
        <p className="mb-2.5 text-xs text-nexus-muted">Save a snapshot of the current settings and users, and restore it if a change causes problems.</p>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Snapshot label (optional)" className={field} />
          <button type="button" onClick={() => { setSnaps(saveSnapshot(label)); setLabel(""); }} className="shrink-0 rounded-lg border border-nexus-border px-3 py-1.5 text-sm text-nexus-text hover:border-nexus-accent/50">
            Save snapshot
          </button>
        </div>
        {snaps.length > 0 && (
          <ul className="mt-3 space-y-1.5">
            {snaps.map((s) => (
              <li key={s.id} className="flex items-center gap-2 rounded-lg bg-nexus-panel2 px-2.5 py-1.5 text-xs">
                <span className="min-w-0 flex-1 truncate text-nexus-text">{s.label}</span>
                <span className="shrink-0 text-nexus-muted">{new Date(s.at).toLocaleDateString()}</span>
                <button type="button" onClick={() => restore(s.id)} className="shrink-0 rounded border border-nexus-border px-2 py-0.5 text-nexus-text hover:border-nexus-accent/50">Restore</button>
                <button type="button" onClick={() => setSnaps(deleteSnapshot(s.id))} className="shrink-0 rounded p-1 text-nexus-muted hover:text-red-400">
                  <TrashIcon className="h-3.5 w-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
