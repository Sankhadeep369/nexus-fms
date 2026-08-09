import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { useChatHistory } from "../context/ChatHistoryContext";
import { useDensity } from "../context/DensityContext";
import { useTheme } from "../context/ThemeContext";
import { CheckIcon, MoonIcon, SunIcon, TrashIcon, XIcon } from "./icons";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

function exportChat(conversation) {
  const lines = [`# ${conversation.title}`, ""];
  for (const m of conversation.messages) {
    if (m.role === "user") lines.push("## You", "", m.content, "");
    else if (m.content) lines.push("## NEXUS", "", m.content, "");
  }
  const blob = new Blob([lines.join("\n")], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${(conversation.title || "nexus-chat").replace(/[^\w-]+/g, "_").slice(0, 40)}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

const rowBtn =
  "flex w-full items-center justify-between rounded-xl border border-nexus-border bg-nexus-panel2 px-3 py-2.5 text-sm text-nexus-text transition-colors";

export default function OptionsPanel({ open, onClose }) {
  const { theme, toggleTheme } = useTheme();
  const { density, setDensity } = useDensity();
  const { clearAll, activeConversation } = useChatHistory();
  const [info, setInfo] = useState(null);
  const [confirmClear, setConfirmClear] = useState(false);

  useEffect(() => {
    if (!open) {
      setConfirmClear(false);
      return;
    }
    fetch(`${API_BASE}/info`)
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then(setInfo)
      .catch(() => setInfo(null));
  }, [open]);

  const hasMessages = (activeConversation?.messages?.length ?? 0) > 0;

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
            className="scroll-thin fixed right-0 top-0 z-40 h-full w-80 max-w-[85vw] overflow-y-auto border-l border-nexus-border bg-nexus-panel p-4 shadow-2xl"
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
              <button type="button" onClick={toggleTheme} className={`mt-2 hover:border-nexus-accent2/50 ${rowBtn}`}>
                <span>{theme === "dark" ? "Dark mode" : "Light mode"}</span>
                {theme === "dark" ? <MoonIcon className="h-4 w-4" /> : <SunIcon className="h-4 w-4" />}
              </button>

              <div className="mt-2 flex items-center justify-between rounded-xl border border-nexus-border bg-nexus-panel2 px-3 py-2">
                <span className="text-sm text-nexus-text">Density</span>
                <div className="inline-flex rounded-lg border border-nexus-border bg-nexus-panel p-0.5 text-xs">
                  {["comfortable", "compact"].map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => setDensity(d)}
                      className={`rounded-md px-2.5 py-1 font-medium capitalize transition-colors ${
                        density === d ? "bg-gradient-to-br from-nexus-accent to-nexus-accent2 text-nexus-bg" : "text-nexus-muted hover:text-nexus-text"
                      }`}
                    >
                      {d}
                    </button>
                  ))}
                </div>
              </div>
              <p className="mt-1 px-1 text-[11px] text-nexus-muted">Compact fits more on smaller screens.</p>
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
                onClick={() => hasMessages && exportChat(activeConversation)}
                disabled={!hasMessages}
                className={`mt-2 hover:border-nexus-accent/50 disabled:cursor-not-allowed disabled:opacity-40 ${rowBtn}`}
              >
                <span>Export this chat (.md)</span>
                <BookIconInline />
              </button>

              {!confirmClear ? (
                <button
                  type="button"
                  onClick={() => setConfirmClear(true)}
                  className={`mt-2 text-red-400 hover:border-red-400/50 ${rowBtn}`}
                >
                  <span>Clear chat history</span>
                  <TrashIcon className="h-4 w-4" />
                </button>
              ) : (
                <div className="mt-2 rounded-xl border border-red-400/30 bg-red-400/10 p-3">
                  <p className="text-xs text-red-300">Delete all chats? This cannot be undone.</p>
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        clearAll();
                        setConfirmClear(false);
                      }}
                      className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-red-500/90 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-500"
                    >
                      <CheckIcon className="h-3.5 w-3.5" /> Delete all
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmClear(false)}
                      className="flex-1 rounded-lg border border-nexus-border px-3 py-1.5 text-xs font-medium text-nexus-muted transition-colors hover:text-nexus-text"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </section>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

// Small inline download glyph (kept local to avoid touching the shared icon set).
function BookIconInline() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <path d="M7 10l5 5 5-5M12 15V3" />
    </svg>
  );
}
