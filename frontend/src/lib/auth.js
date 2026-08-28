// Frontend access-control layer (v1). Accounts + permissions live in localStorage
// so this is a UI gate, not server-enforced security — see the note in the admin
// panel. Everything funnels through this module so it can later be swapped for a
// Supabase-backed, token-enforced implementation without touching the UI.

export const TOOLS = [
  { id: "chat", label: "Chat" },
  { id: "agents", label: "Agents" },
  { id: "analysis", label: "Analysis" },
  { id: "dashboard", label: "Dashboard" },
  { id: "documents", label: "Documents" },
];

// The agents actually surfaced in the Agents tab.
export const AGENTS = [
  { id: "incident_triage", label: "Incident Triage" },
  { id: "vendor_comparison", label: "Vendor Comparison" },
  { id: "reminder", label: "Reminder Agent" },
];

const mapAll = (items, v) => Object.fromEntries(items.map((i) => [i.id, v]));

export function emptyPerms() {
  return { tools: mapAll(TOOLS, false), agents: mapAll(AGENTS, false), reminder: { create: false, manage: false } };
}

// Role presets — a starting point the admin can then fine-tune per user.
export const ROLE_PRESETS = {
  admin: {
    label: "Admin",
    build: () => ({ tools: mapAll(TOOLS, true), agents: mapAll(AGENTS, true), reminder: { create: true, manage: true } }),
  },
  manager: {
    label: "Manager",
    build: () => ({ tools: mapAll(TOOLS, true), agents: mapAll(AGENTS, true), reminder: { create: true, manage: true } }),
  },
  operator: {
    label: "Operator",
    build: () => ({
      tools: { chat: true, agents: true, analysis: true, dashboard: false, documents: false },
      agents: { incident_triage: true, vendor_comparison: true, reminder: true },
      reminder: { create: true, manage: false },
    }),
  },
  viewer: {
    label: "Viewer",
    build: () => ({
      tools: { chat: true, agents: false, analysis: false, dashboard: true, documents: false },
      agents: mapAll(AGENTS, false),
      reminder: { create: false, manage: false },
    }),
  },
};

export const ROLE_IDS = Object.keys(ROLE_PRESETS);

const USERS_KEY = "nexus-users";
const SESSION_KEY = "nexus-session";

const DEFAULT_ADMIN = {
  username: "admin",
  password: "admin123",
  name: "Administrator",
  role: "admin",
  perms: ROLE_PRESETS.admin.build(),
  createdAt: 0,
};

// Fill any newly-added tool/agent keys so older saved users stay valid.
function normalisePerms(p) {
  const base = emptyPerms();
  return {
    tools: { ...base.tools, ...(p?.tools || {}) },
    agents: { ...base.agents, ...(p?.agents || {}) },
    reminder: { ...base.reminder, ...(p?.reminder || {}) },
  };
}

export function loadUsers() {
  let list;
  try {
    list = JSON.parse(localStorage.getItem(USERS_KEY));
  } catch {
    list = null;
  }
  if (!Array.isArray(list) || !list.length) {
    list = [DEFAULT_ADMIN];
    localStorage.setItem(USERS_KEY, JSON.stringify(list));
  }
  // Guarantee at least one admin exists (never lock the product out).
  if (!list.some((u) => u.role === "admin")) list.unshift(DEFAULT_ADMIN);
  return list.map((u) => ({ ...u, perms: normalisePerms(u.perms) }));
}

function saveUsers(list) {
  localStorage.setItem(USERS_KEY, JSON.stringify(list));
  return list;
}

export function createUser({ username, password, name, role }) {
  const users = loadUsers();
  const uname = (username || "").trim().toLowerCase();
  if (!uname) return { error: "Username is required." };
  if (!password) return { error: "Password is required." };
  if (users.some((u) => u.username === uname)) return { error: "That username already exists." };
  const preset = ROLE_PRESETS[role] ? role : "viewer";
  users.push({
    username: uname,
    password,
    name: (name || "").trim() || uname,
    role: preset,
    perms: ROLE_PRESETS[preset].build(),
    createdAt: Date.now(),
  });
  saveUsers(users);
  return { users };
}

export function updateUser(username, patch) {
  const users = loadUsers();
  const u = users.find((x) => x.username === username);
  if (!u) return { error: "User not found." };
  if (patch.name != null) u.name = patch.name.trim() || u.username;
  if (patch.password) u.password = patch.password;
  if (patch.role && ROLE_PRESETS[patch.role]) u.role = patch.role;
  if (patch.perms) u.perms = normalisePerms(patch.perms);
  // An admin's permissions are always full, regardless of edits.
  if (u.role === "admin") u.perms = ROLE_PRESETS.admin.build();
  saveUsers(users);
  return { users };
}

export function deleteUser(username) {
  const users = loadUsers();
  const target = users.find((u) => u.username === username);
  if (!target) return { error: "User not found." };
  if (target.role === "admin" && users.filter((u) => u.role === "admin").length <= 1)
    return { error: "Can't delete the only admin." };
  return { users: saveUsers(users.filter((u) => u.username !== username)) };
}

export function login(username, password) {
  const uname = (username || "").trim().toLowerCase();
  const u = loadUsers().find((x) => x.username === uname && x.password === password);
  if (!u) return null;
  localStorage.setItem(SESSION_KEY, uname);
  return sanitize(u);
}

export function logout() {
  localStorage.removeItem(SESSION_KEY);
}

export function currentUser() {
  const uname = localStorage.getItem(SESSION_KEY);
  if (!uname) return null;
  const u = loadUsers().find((x) => x.username === uname);
  return u ? sanitize(u) : null;
}

// Never hand the password around the app.
function sanitize(u) {
  const { password, ...rest } = u; // eslint-disable-line no-unused-vars
  return rest;
}
