import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { useChatHistory } from "../context/ChatHistoryContext";
import { useTheme } from "../context/ThemeContext";
import { MoonIcon, SunIcon, TrashIcon, XIcon } from "./icons";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export default function OptionsPanel({ open, onClose }) {
  const { theme, toggleTheme } = useTheme();
  const { clearAll } = useChatHistory();
  const [info, setInfo] = useState(null);

  useEffect(() => {
    if (!open) return;
    fetch(`${API_BASE}/info`)
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then(setInfo)
      .catch(() => setInfo(null));
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-30 bg-black/30"
            onClick={onClose}
          />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="fixed right-0 top-0 z-40 h-full w-80 max-w-[85vw] border-l border-nexus-border bg-nexus-panel p-4 shadow-2xl"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-nexus-text">Options</h2>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg p-1.5 text-nexus-muted transition-colors hover:bg-nexus-panel2 hover:text-nexus-text"
                aria-label="Close options"
              >
                <XIcon className="h-4 w-4" />
              </button>
            </div>

            <section className="mt-6">
              <h3 className="text-[11px] font-medium uppercase tracking-wider text-nexus-muted">Appearance</h3>
              <button
                type="button"
                onClick={toggleTheme}
                className="mt-2 flex w-full items-center justify-between rounded-xl border border-nexus-border bg-nexus-panel2 px-3 py-2.5 text-sm text-nexus-text transition-colors hover:border-nexus-accent2/50"
              >
                <span>{theme === "dark" ? "Dark mode" : "Light mode"}</span>
                {theme === "dark" ? <MoonIcon className="h-4 w-4" /> : <SunIcon className="h-4 w-4" />}
              </button>
            </section>

            <section className="mt-6">
              <h3 className="text-[11px] font-medium uppercase tracking-wider text-nexus-muted">Model</h3>
              <div className="mt-2 space-y-1.5 rounded-xl border border-nexus-border bg-nexus-panel2 px-3 py-2.5 text-sm text-nexus-text">
                <div className="flex justify-between">
                  <span className="text-nexus-muted">Model</span>
                  <span className="truncate">{info?.model ?? "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-nexus-muted">Context</span>
                  <span>{info?.ctx ? `${info.ctx} tokens` : "—"}</span>
                </div>
              </div>
            </section>

            <section className="mt-6">
              <h3 className="text-[11px] font-medium uppercase tracking-wider text-nexus-muted">Chat data</h3>
              <button
                type="button"
                onClick={clearAll}
                className="mt-2 flex w-full items-center justify-between rounded-xl border border-nexus-border bg-nexus-panel2 px-3 py-2.5 text-sm text-red-400 transition-colors hover:border-red-400/50"
              >
                <span>Clear chat history</span>
                <TrashIcon className="h-4 w-4" />
              </button>
            </section>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
