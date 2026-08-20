import { useEffect, useState } from "react";
import { useLanguage } from "../context/LanguageContext";
import { useTheme } from "../context/ThemeContext";
import { BotIcon, CircleDotIcon, LogoIcon, MenuIcon, MoonIcon, SlidersIcon, SparkleIcon, SunIcon } from "./icons";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

const TABS = [
  { id: "chat", label: "Chat", icon: SparkleIcon },
  { id: "agents", label: "Agents", icon: BotIcon },
];

const TAB_KEY = { chat: "tab_chat", agents: "tab_agents" };

export default function Header({ onToggleSidebar, onToggleOptions, activeTab, onTabChange }) {
  const { theme, toggleTheme } = useTheme();
  const { t } = useLanguage();
  const [status, setStatus] = useState({ online: null, model: null });

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/info`)
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => {
        if (!cancelled) setStatus({ online: true, model: data.model });
      })
      .catch(() => {
        if (!cancelled) setStatus({ online: false, model: null });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <header className="relative z-10 flex h-14 shrink-0 items-center justify-between border-b border-nexus-border bg-nexus-panel/80 px-3 backdrop-blur-sm">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onToggleSidebar}
          className="rounded-lg p-2 text-nexus-muted transition-colors hover:bg-nexus-panel2 hover:text-nexus-text"
          aria-label="Toggle sidebar"
        >
          <MenuIcon className="h-4 w-4" />
        </button>
        <div className="flex items-center gap-1.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-nexus-accent to-nexus-accent2 text-nexus-bg shadow-glow-sm">
            <LogoIcon className="h-4 w-4" />
          </span>
          <span className="font-display text-base font-semibold tracking-tight text-nexus-text">
            NEXUS
          </span>
        </div>
        <span
          className={`ml-2 hidden items-center gap-1.5 rounded-full border border-nexus-border px-2.5 py-1 text-[11px] text-nexus-muted sm:flex ${
            status.online === null ? "opacity-50" : ""
          }`}
        >
          <span className="relative flex h-3 w-3 shrink-0 items-center justify-center">
            {status.online && (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-nexus-accent opacity-40" />
            )}
            <CircleDotIcon
              className={`h-3 w-3 ${
                status.online ? "text-nexus-accent" : status.online === false ? "text-red-400" : "text-nexus-muted"
              }`}
            />
          </span>
          {status.online === null && "Connecting…"}
          {status.online === true && `Online · ${status.model}`}
          {status.online === false && "Backend offline"}
        </span>
      </div>

      <div className="inline-flex items-center gap-0.5 rounded-full border border-nexus-border bg-nexus-panel2 p-0.5">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => onTabChange?.(id)}
            aria-pressed={activeTab === id}
            className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
              activeTab !== id
                ? "text-nexus-muted hover:text-nexus-text"
                : id === "agents"
                ? "bg-gradient-to-br from-nexus-violet to-nexus-accent text-nexus-bg"
                : "bg-gradient-to-br from-nexus-accent to-nexus-accent2 text-nexus-bg"
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">{t(TAB_KEY[id]) ?? label}</span>
          </button>
        ))}
      </div>

      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={toggleTheme}
          className="rounded-lg p-2 text-nexus-muted transition-colors hover:bg-nexus-panel2 hover:text-nexus-text"
          aria-label="Toggle theme"
        >
          {theme === "dark" ? <SunIcon className="h-4 w-4" /> : <MoonIcon className="h-4 w-4" />}
        </button>
        <button
          type="button"
          onClick={onToggleOptions}
          className="rounded-lg p-2 text-nexus-muted transition-colors hover:bg-nexus-panel2 hover:text-nexus-text"
          aria-label="Settings"
          title="Settings"
        >
          <SlidersIcon className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
