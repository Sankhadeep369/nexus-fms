import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { hexToTriple, loadConfig, saveConfig } from "../lib/appconfig";

const AppConfigContext = createContext(null);

export function AppConfigProvider({ children }) {
  const [config, setConfig] = useState(loadConfig);

  // Apply the brand accent as a CSS variable override (falls back to the theme
  // default when cleared).
  useEffect(() => {
    const triple = hexToTriple(config.branding.accent);
    const root = document.documentElement;
    if (triple) {
      root.style.setProperty("--nexus-accent", triple);
      root.style.setProperty("--nexus-accent2", triple);
    } else {
      root.style.removeProperty("--nexus-accent");
      root.style.removeProperty("--nexus-accent2");
    }
  }, [config.branding.accent]);

  const value = useMemo(
    () => ({
      config,
      brandName: config.branding.name || "NEXUS",
      announcement: config.announcement,
      featureEnabled: (id) => config.features?.[id] !== false,
      update: (next) => {
        saveConfig(next);
        setConfig(next);
      },
      reload: () => setConfig(loadConfig()),
    }),
    [config]
  );

  return <AppConfigContext.Provider value={value}>{children}</AppConfigContext.Provider>;
}

export function useAppConfig() {
  return useContext(AppConfigContext);
}
