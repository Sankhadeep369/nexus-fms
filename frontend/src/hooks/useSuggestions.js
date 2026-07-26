import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

// Fallback shown before the backend responds (or if /suggestions fails) so the
// empty-state chips aren't blank on first paint.
const FALLBACK = [
  { text: "What should I check weekly for the chiller plant?", category: "HVAC & Chiller" },
  { text: "Summarize this month's compliance checklist.", category: "Compliance & Safety" },
  { text: "Compare vendor terms for the HVAC contract.", category: "Vendors & Contracts" },
  { text: "Draft a memo on an upcoming AMC renewal.", category: "Drafting & Templates" },
].map((s) => ({ ...s, cached: false }));

export function useSuggestions() {
  const [suggestions, setSuggestions] = useState(FALLBACK);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/suggestions`)
      .then((res) => (res.ok ? res.json() : Promise.reject(res)))
      .then((data) => {
        if (!cancelled && Array.isArray(data) && data.length > 0) setSuggestions(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  return suggestions;
}
