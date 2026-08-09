import { AnimatePresence, motion } from "framer-motion";
import {
  BellIcon,
  BotIcon,
  CommandIcon,
  HistoryIcon,
  PaperclipIcon,
  ScaleIcon,
  SparkleIcon,
  XIcon,
  ZapIcon,
} from "./icons";

const SECTIONS = [
  {
    icon: SparkleIcon,
    title: "Ask anything",
    body: "Ask about contracts, vendors, compliance, SLAs, or maintenance SOPs — or ask NEXUS to draft an email, memo, or report. Answers stream in with the sources it used.",
  },
  {
    icon: CommandIcon,
    title: "Quick suggestions",
    body: (
      <>
        Type <kbd className="rounded bg-nexus-panel2 px-1 font-mono">/</kbd> or press{" "}
        <kbd className="rounded bg-nexus-panel2 px-1 font-mono">⌘K</kbd> to browse ready-made questions by
        category. Ones marked <ZapIcon className="inline h-3 w-3 text-nexus-accent2" /> are cached and answer
        instantly.
      </>
    ),
  },
  {
    icon: ZapIcon,
    title: "Simple vs Thinking",
    body: "Toggle above the message box. Simple is fast and focused; Thinking is more exploratory for open-ended questions.",
  },
  {
    icon: PaperclipIcon,
    title: "Attach documents",
    body: "Attach or drag a PDF/Word file onto the chat. This is a preview for now — documents are not analysed yet.",
  },
  {
    icon: BotIcon,
    title: "Agents",
    body: (
      <>
        Open the <span className="text-nexus-text">Agents</span> tab for multi-step assistants:
        <ul className="mt-1.5 space-y-1">
          <li className="flex gap-2">
            <BellIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-nexus-violet" />
            <span>
              <span className="text-nexus-text">Incident Triage</span> — report a problem; it finds the vendor,
              checks the SLA, gives immediate safety steps, and drafts an escalation email.
            </span>
          </li>
          <li className="flex gap-2">
            <ScaleIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-nexus-violet" />
            <span>
              <span className="text-nexus-text">Vendor Comparison</span> — side-by-side comparison you can send
              into chat as a follow-up.
            </span>
          </li>
          <li className="flex gap-2">
            <BellIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-nexus-violet" />
            <span>
              <span className="text-nexus-text">Reminder Agent</span> — schedule renewal/audit reminders and get
              an email when they are due.
            </span>
          </li>
        </ul>
      </>
    ),
  },
  {
    icon: HistoryIcon,
    title: "History, profile & theme",
    body: "Your chats are saved on this device (left sidebar, searchable). Create an optional profile from the sidebar, switch light/dark from the top bar, and find more in Options (the sliders icon).",
  },
];

export default function GuideModal({ open, onClose }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
            onClick={onClose}
          />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 8 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
              onClick={(e) => e.stopPropagation()}
              className="scroll-thin flex max-h-[85vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-nexus-border bg-nexus-panel shadow-2xl"
            >
              <div className="flex items-center justify-between border-b border-nexus-border px-5 py-3.5">
                <h2 className="font-display text-base font-semibold text-nexus-text">How NEXUS works</h2>
                <button
                  type="button"
                  onClick={onClose}
                  aria-label="Close guide"
                  className="rounded-lg p-1.5 text-nexus-muted transition-colors hover:bg-nexus-panel2 hover:text-nexus-text"
                >
                  <XIcon className="h-4 w-4" />
                </button>
              </div>

              <div className="scroll-thin overflow-y-auto px-5 py-4">
                <ul className="space-y-4">
                  {SECTIONS.map(({ icon: Icon, title, body }) => (
                    <li key={title} className="flex gap-3">
                      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-nexus-panel2 text-nexus-accent">
                        <Icon className="h-4 w-4" />
                      </span>
                      <div>
                        <p className="text-sm font-medium text-nexus-text">{title}</p>
                        <div className="mt-0.5 text-xs leading-relaxed text-nexus-muted">{body}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="border-t border-nexus-border px-5 py-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="w-full rounded-xl bg-gradient-to-br from-nexus-accent to-nexus-accent2 px-3.5 py-2 text-sm font-medium text-nexus-bg transition-all hover:shadow-glow-sm active:scale-[0.99]"
                >
                  Got it
                </button>
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
