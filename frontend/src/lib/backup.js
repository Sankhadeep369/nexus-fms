// Full data backup/restore. Everything the app stores lives in this browser's
// localStorage, so a JSON export lets a user move their whole setup (users, config,
// KPIs, home layouts, chats, analyses) to another browser or device. No backend.

export function exportData() {
  const data = {};
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (k && k.startsWith("nexus")) data[k] = localStorage.getItem(k);
  }
  return JSON.stringify({ _nexus_backup: 1, version: 1, exportedAt: new Date().toISOString(), data }, null, 2);
}

export function downloadBackup() {
  const stamp = new Date().toISOString().slice(0, 10);
  const url = URL.createObjectURL(new Blob([exportData()], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `nexus-backup-${stamp}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

// Returns { count } on success or { error }. Only writes nexus* keys, so an
// unrelated file can't scribble over arbitrary storage.
export function importData(json) {
  let parsed;
  try {
    parsed = JSON.parse(json);
  } catch {
    return { error: "That file isn't valid JSON." };
  }
  const data = parsed?.data && typeof parsed.data === "object" ? parsed.data : parsed;
  if (!data || typeof data !== "object") return { error: "Unrecognised backup file." };
  let count = 0;
  for (const [k, v] of Object.entries(data)) {
    if (typeof k === "string" && k.startsWith("nexus") && typeof v === "string") {
      localStorage.setItem(k, v);
      count++;
    }
  }
  if (!count) return { error: "No NEXUS data found in that file." };
  return { count };
}
