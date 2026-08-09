import { useMemo, useState } from "react";
import { useChatHistory } from "../context/ChatHistoryContext";
import { useLanguage } from "../context/LanguageContext";
import { initials, useProfile } from "../context/ProfileContext";
import { HistoryIcon, PlusIcon, SearchIcon, TrashIcon, UserIcon } from "./icons";

function relativeTime(ts) {
  const diff = Date.now() - ts;
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (diff < minute) return "just now";
  if (diff < hour) return `${Math.floor(diff / minute)}m ago`;
  if (diff < day) return `${Math.floor(diff / hour)}h ago`;
  return `${Math.floor(diff / day)}d ago`;
}

// Buckets conversations the way most chat apps do, so recent work stays
// visually separated from the long tail of old sessions.
function groupByDate(conversations) {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startOfYesterday = startOfToday - 86_400_000;
  const startOfWeek = startOfToday - 6 * 86_400_000;

  const buckets = [
    { label: "Today", items: [] },
    { label: "Yesterday", items: [] },
    { label: "Previous 7 days", items: [] },
    { label: "Older", items: [] },
  ];
  for (const c of conversations) {
    if (c.updatedAt >= startOfToday) buckets[0].items.push(c);
    else if (c.updatedAt >= startOfYesterday) buckets[1].items.push(c);
    else if (c.updatedAt >= startOfWeek) buckets[2].items.push(c);
    else buckets[3].items.push(c);
  }
  return buckets.filter((b) => b.items.length > 0);
}

export default function Sidebar({ collapsed, onClose, onOpenProfile }) {
  const { conversations, activeId, createConversation, selectConversation, deleteConversation } = useChatHistory();
  const { profile } = useProfile();
  const { t } = useLanguage();
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((c) => c.title.toLowerCase().includes(q));
  }, [conversations, query]);

  const groups = useMemo(() => groupByDate(filtered), [filtered]);

  // On mobile the sidebar is an overlay drawer, so navigating should dismiss it.
  const closeOnMobile = () => {
    if (typeof window !== "undefined" && window.matchMedia("(max-width: 767px)").matches) {
      onClose?.();
    }
  };
  const handleCreate = () => {
    createConversation();
    closeOnMobile();
  };
  const handleSelect = (id) => {
    selectConversation(id);
    closeOnMobile();
  };

  return (
    <>
      {/* Mobile-only backdrop behind the drawer. */}
      <div
        aria-hidden="true"
        onClick={onClose}
        className={`fixed inset-0 z-30 bg-black/50 transition-opacity duration-200 md:hidden ${
          collapsed ? "pointer-events-none opacity-0" : "opacity-100"
        }`}
      />
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col overflow-hidden border-r border-nexus-border bg-nexus-panel transition-[transform,width] duration-200 ease-in-out md:static md:z-auto md:translate-x-0 ${
          collapsed ? "-translate-x-full md:w-14" : "translate-x-0 md:w-64"
        }`}
      >
      <div className="p-2">
        <button
          type="button"
          onClick={handleCreate}
          className={`flex w-full items-center gap-2 rounded-xl border border-nexus-border bg-nexus-panel2 px-3 py-2 text-sm font-medium text-nexus-text transition-colors hover:border-nexus-accent2/50 hover:text-nexus-accent2 ${
            collapsed ? "justify-center" : ""
          }`}
          title={t("new_chat")}
        >
          <PlusIcon className="h-4 w-4 shrink-0" />
          {!collapsed && <span className="whitespace-nowrap">{t("new_chat")}</span>}
        </button>
      </div>

      {!collapsed && (
        <div className="px-2 pb-2">
          <div className="relative">
            <SearchIcon className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-nexus-muted" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("search_chats")}
              className="w-full rounded-lg border border-nexus-border bg-nexus-panel2 py-1.5 pl-8 pr-2.5 text-sm text-nexus-text placeholder:text-nexus-muted transition-colors focus:border-nexus-accent/50 focus:outline-none"
            />
          </div>
        </div>
      )}

      <div className="scroll-thin flex-1 overflow-y-auto px-2">
        {groups.length === 0 && !collapsed && (
          <p className="px-1 py-4 text-center text-xs text-nexus-muted">No chats found.</p>
        )}
        {groups.map((group) => (
          <div key={group.label} className="mb-1">
            {!collapsed && (
              <div className="px-1 py-1.5 text-[11px] font-medium uppercase tracking-wider text-nexus-muted">
                {group.label}
              </div>
            )}
            <ul className="space-y-1">
              {group.items.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    onClick={() => handleSelect(c.id)}
                    className={`group flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm transition-colors ${
                      c.id === activeId
                        ? "bg-nexus-accent2/15 text-nexus-text"
                        : "text-nexus-muted hover:bg-nexus-panel2 hover:text-nexus-text"
                    } ${collapsed ? "justify-center" : ""}`}
                    title={c.title}
                  >
                    {collapsed ? (
                      <HistoryIcon className="h-4 w-4 shrink-0" />
                    ) : (
                      <>
                        <div className="min-w-0 flex-1">
                          <p className="truncate">{c.title}</p>
                          <p className="truncate text-[11px] text-nexus-muted">{relativeTime(c.updatedAt)}</p>
                        </div>
                        <span
                          role="button"
                          tabIndex={0}
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteConversation(c.id);
                          }}
                          className="shrink-0 rounded-md p-1 text-nexus-muted opacity-0 transition-opacity hover:text-red-400 group-hover:opacity-100"
                          aria-label="Delete conversation"
                        >
                          <TrashIcon className="h-3.5 w-3.5" />
                        </span>
                      </>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={onOpenProfile}
        title={profile ? "Your profile" : "Sign in / create a profile"}
        className={`flex items-center gap-2 border-t border-nexus-border p-3 text-left transition-colors hover:bg-nexus-panel2 ${
          collapsed ? "justify-center" : ""
        }`}
      >
        <div
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ${
            profile
              ? "bg-gradient-to-br from-nexus-accent to-nexus-accent2 text-nexus-bg"
              : "bg-nexus-panel2 text-nexus-muted"
          }`}
        >
          {profile ? initials(profile.name) : <UserIcon className="h-4 w-4" />}
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-sm text-nexus-text">{profile ? profile.name : t("sign_in")}</p>
            <p className="truncate text-[11px] text-nexus-muted">
              {profile ? profile.email || "Local account" : "Optional — personalise NEXUS"}
            </p>
          </div>
        )}
      </button>
      </aside>
    </>
  );
}
