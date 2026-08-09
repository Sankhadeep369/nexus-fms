import { createContext, useContext, useEffect, useState } from "react";

// Compact mode simply scales the root font size down; because the UI is built on
// rem-based Tailwind sizing, everything (text, padding, gaps) shrinks together.
// Purely visual and local — no effect on the backend or response timing.
const KEY = "nexus-density";
const DensityContext = createContext(null);

export function DensityProvider({ children }) {
  const [density, setDensity] = useState(() => localStorage.getItem(KEY) || "comfortable");

  useEffect(() => {
    document.documentElement.style.fontSize = density === "compact" ? "14px" : "";
    localStorage.setItem(KEY, density);
  }, [density]);

  return (
    <DensityContext.Provider
      value={{ density, setDensity, toggleDensity: () => setDensity((d) => (d === "compact" ? "comfortable" : "compact")) }}
    >
      {children}
    </DensityContext.Provider>
  );
}

export function useDensity() {
  return useContext(DensityContext);
}
