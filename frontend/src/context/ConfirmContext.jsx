import { createContext, useCallback, useContext, useState } from "react";
import { useEscapeKey } from "../hooks/useEscapeKey";

const ConfirmContext = createContext(null);

// In-app replacement for window.confirm / window.alert — themed, accessible,
// promise-based: `if (await confirm({...})) { ... }` and `await notify(msg)`.
export function ConfirmProvider({ children }) {
  const [dialog, setDialog] = useState(null);

  const confirm = useCallback(
    (opts) => new Promise((resolve) => setDialog({ ...opts, resolve })),
    []
  );
  const notify = useCallback(
    (message, title = "Notice") => new Promise((resolve) => setDialog({ title, message, alert: true, resolve })),
    []
  );

  const close = (value) => {
    dialog?.resolve(value);
    setDialog(null);
  };

  return (
    <ConfirmContext.Provider value={{ confirm, notify }}>
      {children}
      {dialog && <Dialog dialog={dialog} onResolve={close} />}
    </ConfirmContext.Provider>
  );
}

function Dialog({ dialog, onResolve }) {
  const { title, message, confirmLabel, cancelLabel, danger, alert } = dialog;
  useEscapeKey(() => onResolve(false));

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
      <button type="button" aria-label="Dismiss" onClick={() => onResolve(false)} className="absolute inset-0 cursor-default bg-black/50 backdrop-blur-sm" />
      <div role="dialog" aria-modal="true" className="relative w-full max-w-sm rounded-2xl border border-nexus-border bg-nexus-panel p-5 shadow-glow">
        {title && <h2 className="font-display text-base font-semibold text-nexus-text">{title}</h2>}
        {message && <p className="mt-1.5 text-sm leading-relaxed text-nexus-muted">{message}</p>}
        <div className="mt-5 flex justify-end gap-2">
          {!alert && (
            <button type="button" onClick={() => onResolve(false)} className="rounded-lg border border-nexus-border px-3 py-1.5 text-sm text-nexus-text hover:bg-nexus-panel2">
              {cancelLabel || "Cancel"}
            </button>
          )}
          <button
            type="button"
            onClick={() => onResolve(true)}
            className={`rounded-lg px-3.5 py-1.5 text-sm font-medium ${
              danger
                ? "bg-red-500/90 text-white hover:bg-red-500"
                : "bg-gradient-to-br from-nexus-accent to-nexus-accent2 text-nexus-bg hover:shadow-glow-sm"
            }`}
          >
            {alert ? "OK" : confirmLabel || "Confirm"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function useConfirm() {
  return useContext(ConfirmContext).confirm;
}
export function useNotify() {
  return useContext(ConfirmContext).notify;
}
