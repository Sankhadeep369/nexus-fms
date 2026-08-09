import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { initials, useProfile } from "../context/ProfileContext";
import { LogOutIcon, LogoIcon, UserIcon, XIcon } from "./icons";

const FIELD =
  "w-full rounded-xl border border-nexus-border bg-nexus-bg px-3 py-2 text-sm text-nexus-text placeholder:text-nexus-muted focus:border-nexus-accent/60 focus:outline-none";

export default function ProfilePanel({ open, onClose }) {
  const { profile, saveProfile, signOut } = useProfile();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");

  // Sync the form to the current profile whenever the panel opens.
  useEffect(() => {
    if (open) {
      setName(profile?.name ?? "");
      setEmail(profile?.email ?? "");
    }
  }, [open, profile]);

  const submit = () => {
    if (!name.trim()) return;
    saveProfile({ name, email });
    onClose();
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-30 bg-black/40"
            onClick={onClose}
          />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="fixed right-0 top-0 z-40 flex h-full w-80 max-w-[85vw] flex-col border-l border-nexus-border bg-nexus-panel p-4 shadow-2xl"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-nexus-text">
                {profile ? "Your profile" : "Sign in"}
              </h2>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="rounded-lg p-1.5 text-nexus-muted transition-colors hover:bg-nexus-panel2 hover:text-nexus-text"
              >
                <XIcon className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-5 flex flex-col items-center text-center">
              <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-nexus-accent to-nexus-accent2 text-xl font-semibold text-nexus-bg shadow-glow">
                {profile ? initials(profile.name) : <UserIcon className="h-7 w-7" />}
              </span>
              {profile ? (
                <>
                  <p className="mt-3 text-sm font-medium text-nexus-text">{profile.name}</p>
                  {profile.email && <p className="text-xs text-nexus-muted">{profile.email}</p>}
                </>
              ) : (
                <p className="mt-3 max-w-[15rem] text-xs leading-relaxed text-nexus-muted">
                  Create a profile to personalise NEXUS. It is optional — everything works without it.
                </p>
              )}
            </div>

            <div className="mt-5 space-y-2.5">
              <label className="block text-[11px] font-medium text-nexus-muted">
                Name
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && submit()}
                  placeholder="Your name"
                  className={`mt-1 ${FIELD}`}
                />
              </label>
              <label className="block text-[11px] font-medium text-nexus-muted">
                Email <span className="text-nexus-muted/70">(optional — used for reminders)</span>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && submit()}
                  placeholder="you@example.com"
                  className={`mt-1 ${FIELD}`}
                />
              </label>
            </div>

            <button
              type="button"
              onClick={submit}
              disabled={!name.trim()}
              className="mt-4 w-full rounded-xl bg-gradient-to-br from-nexus-accent to-nexus-accent2 px-3.5 py-2 text-sm font-medium text-nexus-bg transition-all hover:shadow-glow-sm active:scale-[0.99] disabled:opacity-30"
            >
              {profile ? "Save changes" : "Create profile"}
            </button>

            {profile && (
              <button
                type="button"
                onClick={() => {
                  signOut();
                  onClose();
                }}
                className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-xl border border-nexus-border px-3.5 py-2 text-sm font-medium text-nexus-muted transition-colors hover:border-red-400/40 hover:text-red-400"
              >
                <LogOutIcon className="h-3.5 w-3.5" />
                Sign out
              </button>
            )}

            <div className="mt-auto flex items-center gap-1.5 border-t border-nexus-border pt-3 text-[11px] text-nexus-muted">
              <LogoIcon className="h-3.5 w-3.5 shrink-0" />
              Local account — saved on this device only. No password, no server.
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
