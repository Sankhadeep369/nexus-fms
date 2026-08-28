// Global app configuration set by admins (branding, announcement, feature toggles)
// plus config snapshots for rollback. Stored in localStorage on this device — the
// same model as the rest of the admin layer, and swappable to a server later.

const CONFIG_KEY = "nexus-app-config";
const SNAP_KEY = "nexus-config-snapshots";
const USERS_KEY = "nexus-users"; // must match lib/auth.js

// Feature ids that can be toggled app-wide (tools + agents).
export const FEATURE_IDS = [
  "chat",
  "agents",
  "analysis",
  "dashboard",
  "documents",
  "incident_triage",
  "vendor_comparison",
  "reminder",
];

export const FEATURE_LABELS = {
  chat: "Chat",
  agents: "Agents",
  analysis: "Analysis",
  dashboard: "Dashboard",
  documents: "Documents",
  incident_triage: "Incident Triage agent",
  vendor_comparison: "Vendor Comparison agent",
  reminder: "Reminder agent",
};

export function defaultConfig() {
  return {
    branding: { name: "NEXUS", accent: "" },
    announcement: { enabled: false, text: "", level: "info" },
    features: Object.fromEntries(FEATURE_IDS.map((f) => [f, true])),
  };
}

export function loadConfig() {
  const d = defaultConfig();
  try {
    const raw = JSON.parse(localStorage.getItem(CONFIG_KEY));
    if (raw && typeof raw === "object") {
      return {
        branding: { ...d.branding, ...(raw.branding || {}) },
        announcement: { ...d.announcement, ...(raw.announcement || {}) },
        features: { ...d.features, ...(raw.features || {}) },
      };
    }
  } catch {
    /* ignore */
  }
  return d;
}

export function saveConfig(next) {
  localStorage.setItem(CONFIG_KEY, JSON.stringify(next));
  return next;
}

// "#2dd4bf" -> "45 212 191" for the --nexus-accent CSS variable.
export function hexToTriple(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec((hex || "").trim());
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return `${(n >> 16) & 255} ${(n >> 8) & 255} ${n & 255}`;
}

// ---- Snapshots (config + users) for rollback ----
export function listSnapshots() {
  try {
    return JSON.parse(localStorage.getItem(SNAP_KEY)) || [];
  } catch {
    return [];
  }
}

export function saveSnapshot(label) {
  const snap = {
    id: crypto.randomUUID(),
    label: label?.trim() || new Date().toLocaleString(),
    at: Date.now(),
    config: loadConfig(),
    users: localStorage.getItem(USERS_KEY),
  };
  const all = [snap, ...listSnapshots()].slice(0, 20);
  localStorage.setItem(SNAP_KEY, JSON.stringify(all));
  return all;
}

export function deleteSnapshot(id) {
  const all = listSnapshots().filter((s) => s.id !== id);
  localStorage.setItem(SNAP_KEY, JSON.stringify(all));
  return all;
}

// Restore both app config and the user directory, then the caller reloads so the
// whole app re-reads the rolled-back state.
export function restoreSnapshot(id) {
  const snap = listSnapshots().find((s) => s.id === id);
  if (!snap) return false;
  localStorage.setItem(CONFIG_KEY, JSON.stringify(snap.config));
  if (snap.users) localStorage.setItem(USERS_KEY, snap.users);
  return true;
}
