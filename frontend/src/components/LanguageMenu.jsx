import { useEffect, useRef, useState } from "react";
import { LANGUAGES, useLanguage } from "../context/LanguageContext";
import { CheckIcon, GlobeIcon } from "./icons";

// Renders the language list grouped (Default / International / Indian).
const GROUPS = ["Default", "International", "Indian"];

export default function LanguageMenu() {
  const { lang, setLang, t } = useLanguage();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  // Close on outside click / Escape.
  useEffect(() => {
    if (!open) return;
    const onDown = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        title={t("language")}
        aria-label={t("language")}
        aria-expanded={open}
        className="rounded-lg p-2 text-nexus-muted transition-colors hover:bg-nexus-panel2 hover:text-nexus-text"
      >
        <GlobeIcon className="h-4 w-4" />
      </button>

      {open && (
        <div className="scroll-thin absolute right-0 top-full z-50 mt-1.5 max-h-[70vh] w-56 overflow-y-auto rounded-xl border border-nexus-border bg-nexus-panel p-1 shadow-lg">
          <div className="px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-nexus-muted/80">
            {t("language")}
          </div>
          {GROUPS.map((group) => (
            <div key={group}>
              <div className="px-2.5 pb-0.5 pt-1.5 text-[10px] font-medium uppercase tracking-wider text-nexus-muted/60">
                {group}
              </div>
              {LANGUAGES.filter((l) => l.group === group).map((l) => (
                <button
                  key={l.code}
                  type="button"
                  onClick={() => {
                    setLang(l.code);
                    setOpen(false);
                  }}
                  className={`flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm transition-colors ${
                    lang === l.code ? "bg-nexus-panel2 text-nexus-text" : "text-nexus-muted hover:bg-nexus-panel2 hover:text-nexus-text"
                  }`}
                >
                  <span dir={l.dir}>{l.native}</span>
                  {lang === l.code && <CheckIcon className="h-3.5 w-3.5 shrink-0 text-nexus-accent" />}
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
