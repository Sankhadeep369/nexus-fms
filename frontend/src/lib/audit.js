// Lightweight admin audit log (localStorage). Records who did what in the admin
// area so changes are traceable. Frontend-only for now; a server log would replace
// this when the backend lands.

const KEY = "nexus-audit-log";
const MAX = 200;

export function loadAudit() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || [];
  } catch {
    return [];
  }
}

export function logAudit(actor, action, detail = "") {
  const entry = { id: crypto.randomUUID(), at: Date.now(), actor: actor || "unknown", action, detail };
  const all = [entry, ...loadAudit()].slice(0, MAX);
  localStorage.setItem(KEY, JSON.stringify(all));
  return all;
}

export function clearAudit() {
  localStorage.removeItem(KEY);
  return [];
}
