import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import {
  AGENTS,
  createUser,
  deleteUser,
  loadUsers,
  ROLE_IDS,
  ROLE_PRESETS,
  TOOLS,
  updateUser,
} from "../lib/auth";
import { useConfirm, useNotify } from "../context/ConfirmContext";
import { logAudit } from "../lib/audit";
import AdminConfig from "./AdminConfig";
import { ChevronDownIcon, PlusIcon, TrashIcon, UserIcon } from "./icons";

const field =
  "w-full rounded-lg border border-nexus-border bg-nexus-bg px-2.5 py-1.5 text-sm text-nexus-text placeholder:text-nexus-muted focus:border-nexus-accent/60 focus:outline-none";

function Toggle({ label, checked, onChange, disabled }) {
  return (
    <label className={`flex items-center gap-2 text-xs ${disabled ? "opacity-50" : "text-nexus-text"}`}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} className="accent-nexus-accent" />
      {label}
    </label>
  );
}

function UserRow({ user, expanded, onToggle, onChanged, isSelf, actor }) {
  const confirm = useConfirm();
  const notify = useNotify();
  const [draft, setDraft] = useState(user);
  const [pw, setPw] = useState("");
  const admin = draft.role === "admin";

  const setTool = (id, v) => setDraft((d) => ({ ...d, perms: { ...d.perms, tools: { ...d.perms.tools, [id]: v } } }));
  const setAgent = (id, v) => setDraft((d) => ({ ...d, perms: { ...d.perms, agents: { ...d.perms.agents, [id]: v } } }));
  const setRem = (k, v) => setDraft((d) => ({ ...d, perms: { ...d.perms, reminder: { ...d.perms.reminder, [k]: v } } }));
  const applyRole = (role) => setDraft((d) => ({ ...d, role, perms: ROLE_PRESETS[role].build() }));

  const save = () => {
    updateUser(user.username, { name: draft.name, role: draft.role, perms: draft.perms, password: pw || undefined });
    logAudit(actor, "Updated user", `${user.username} (${draft.role})`);
    setPw("");
    onChanged();
  };
  const remove = async () => {
    const ok = await confirm({
      title: "Delete user?",
      message: `Remove "${user.username}"? They will lose access. This can't be undone.`,
      confirmLabel: "Delete",
      danger: true,
    });
    if (!ok) return;
    const res = deleteUser(user.username);
    if (res.error) return notify(res.error, "Can't delete");
    logAudit(actor, "Deleted user", user.username);
    onChanged();
  };

  return (
    <div className="rounded-xl border border-nexus-border bg-nexus-panel">
      <button type="button" onClick={onToggle} className="flex w-full items-center gap-3 px-3 py-2.5 text-left">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-nexus-panel2 text-nexus-muted">
          <UserIcon className="h-4 w-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-nexus-text">
            {draft.name} <span className="text-nexus-muted">· {draft.username}</span>
          </span>
          <span className="text-[11px] text-nexus-muted">{ROLE_PRESETS[draft.role]?.label || draft.role}{isSelf && " · you"}</span>
        </span>
        <ChevronDownIcon className={`h-4 w-4 shrink-0 text-nexus-muted transition-transform ${expanded ? "rotate-180" : ""}`} />
      </button>

      {expanded && (
        <div className="border-t border-nexus-border px-3 py-3">
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
            <label className="text-xs text-nexus-muted">
              Name
              <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} className={`${field} mt-1`} />
            </label>
            <label className="text-xs text-nexus-muted">
              Reset password
              <input value={pw} onChange={(e) => setPw(e.target.value)} placeholder="leave blank to keep" className={`${field} mt-1`} />
            </label>
            <label className="text-xs text-nexus-muted">
              Role preset
              <select value={draft.role} onChange={(e) => applyRole(e.target.value)} className={`${field} mt-1`}>
                {ROLE_IDS.map((r) => (
                  <option key={r} value={r}>{ROLE_PRESETS[r].label}</option>
                ))}
              </select>
            </label>
          </div>

          {admin ? (
            <p className="mt-3 rounded-lg bg-nexus-panel2 px-3 py-2 text-xs text-nexus-muted">Admins always have full access to every tool and agent.</p>
          ) : (
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div>
                <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-nexus-muted">Tools</p>
                <div className="space-y-1.5">
                  {TOOLS.map((t) => (
                    <Toggle key={t.id} label={t.label} checked={!!draft.perms.tools[t.id]} onChange={(v) => setTool(t.id, v)} />
                  ))}
                </div>
              </div>
              <div>
                <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-nexus-muted">Agents</p>
                <div className="space-y-1.5">
                  {AGENTS.map((a) => (
                    <Toggle key={a.id} label={a.label} checked={!!draft.perms.agents[a.id]} onChange={(v) => setAgent(a.id, v)} disabled={!draft.perms.tools.agents} />
                  ))}
                </div>
              </div>
              <div>
                <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-nexus-muted">Reminders</p>
                <div className="space-y-1.5">
                  <Toggle label="Create reminders" checked={!!draft.perms.reminder.create} onChange={(v) => setRem("create", v)} disabled={!draft.perms.agents.reminder} />
                  <Toggle label="Edit / cancel reminders" checked={!!draft.perms.reminder.manage} onChange={(v) => setRem("manage", v)} disabled={!draft.perms.agents.reminder} />
                </div>
              </div>
            </div>
          )}

          <div className="mt-4 flex items-center gap-2">
            <button type="button" onClick={save} className="rounded-lg bg-gradient-to-br from-nexus-accent to-nexus-accent2 px-3 py-1.5 text-sm font-medium text-nexus-bg">Save</button>
            {!isSelf && (
              <button type="button" onClick={remove} className="ml-auto flex items-center gap-1.5 rounded-lg border border-nexus-border px-3 py-1.5 text-xs text-nexus-muted hover:border-red-400/50 hover:text-red-400">
                <TrashIcon className="h-3.5 w-3.5" /> Delete
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function AdminPanel() {
  const { user, refresh } = useAuth();
  const [users, setUsers] = useState(loadUsers);
  const [expanded, setExpanded] = useState(null);
  const [form, setForm] = useState({ username: "", name: "", password: "", role: "operator" });
  const [error, setError] = useState(null);
  const [view, setView] = useState("users");

  const reload = () => {
    setUsers(loadUsers());
    refresh();
  };

  const add = () => {
    const res = createUser(form);
    if (res.error) return setError(res.error);
    logAudit(user?.username, "Created user", `${form.username.trim().toLowerCase()} (${form.role})`);
    setForm({ username: "", name: "", password: "", role: "operator" });
    setError(null);
    reload();
  };

  return (
    <div className="scroll-thin flex-1 overflow-y-auto px-4 py-6 sm:px-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-5">
        <div>
          <h1 className="font-display text-xl font-semibold text-nexus-text">Admin</h1>
          <p className="mt-1 text-sm text-nexus-muted">Manage users and configure the app.</p>
        </div>

        {/*
          Implementation note (repo-only, not shown to users): this is currently a
          UI-level gate — accounts, permissions and app config live in localStorage on
          this device and are not server-enforced. Harden with a backend when ready.
        */}

        <div className="inline-flex w-fit items-center gap-0.5 rounded-full border border-nexus-border bg-nexus-panel2 p-0.5">
          {[["users", "Users"], ["settings", "Settings"]].map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setView(id)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${view === id ? "bg-gradient-to-br from-nexus-accent to-nexus-accent2 text-nexus-bg" : "text-nexus-muted hover:text-nexus-text"}`}
            >
              {label}
            </button>
          ))}
        </div>

        {view === "settings" && <AdminConfig />}

        {view === "users" && (
        <>
        {/* Create user */}
        <div className="rounded-2xl border border-nexus-border bg-nexus-panel p-4">
          <p className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-nexus-muted">New user</p>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-4">
            <input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} placeholder="username" className={field} />
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="display name" className={field} />
            <input value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="password" className={field} />
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} className={field}>
              {ROLE_IDS.map((r) => (
                <option key={r} value={r}>{ROLE_PRESETS[r].label}</option>
              ))}
            </select>
          </div>
          {error && <p className="mt-2 text-xs text-red-400">{error}</p>}
          <button type="button" onClick={add} className="mt-3 flex items-center gap-1.5 rounded-lg bg-gradient-to-br from-nexus-accent to-nexus-accent2 px-3 py-1.5 text-sm font-medium text-nexus-bg">
            <PlusIcon className="h-3.5 w-3.5" /> Add user
          </button>
        </div>

        {/* User list */}
        <div className="flex flex-col gap-2">
          {users.map((u) => (
            <UserRow
              key={u.username}
              user={u}
              isSelf={u.username === user?.username}
              actor={user?.username}
              expanded={expanded === u.username}
              onToggle={() => setExpanded(expanded === u.username ? null : u.username)}
              onChanged={reload}
            />
          ))}
        </div>
        </>
        )}
      </div>
    </div>
  );
}
