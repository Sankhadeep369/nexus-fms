import { useEffect } from "react";

// Close-on-Escape for modals, drawers and menus. `active` lets always-mounted
// components (e.g. a modal gated by an `open` prop) only listen while visible.
export function useEscapeKey(handler, active = true) {
  useEffect(() => {
    if (!active) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") handler();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handler, active]);
}
