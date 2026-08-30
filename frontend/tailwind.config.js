/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        nexus: {
          bg: "rgb(var(--nexus-bg) / <alpha-value>)",
          panel: "rgb(var(--nexus-panel) / <alpha-value>)",
          panel2: "rgb(var(--nexus-panel2) / <alpha-value>)",
          border: "rgb(var(--nexus-border) / <alpha-value>)",
          text: "rgb(var(--nexus-text) / <alpha-value>)",
          muted: "rgb(var(--nexus-muted) / <alpha-value>)",
          accent: "rgb(var(--nexus-accent) / <alpha-value>)",
          accent2: "rgb(var(--nexus-accent2) / <alpha-value>)",
          // Sparing hint color, used only for agent/AI-specific UI accents
          // (e.g. the Agents tab, agent workflow steps) -- not the primary brand color.
          violet: "rgb(var(--nexus-violet) / <alpha-value>)",
        },
      },
      fontFamily: {
        display: ["Archivo", "Hanken Grotesk", "system-ui", "sans-serif"],
        sans: ["Hanken Grotesk", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgb(var(--nexus-accent) / 0.4), 0 8px 24px -8px rgb(var(--nexus-accent) / 0.45)",
        "glow-sm": "0 4px 16px -6px rgb(var(--nexus-accent) / 0.4)",
      },
      keyframes: {
        pulseDot: {
          "0%, 80%, 100%": { transform: "scale(0.6)", opacity: "0.4" },
          "40%": { transform: "scale(1)", opacity: "1" },
        },
        shimmer: {
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
        floatGlow: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-6px)" },
        },
      },
      animation: {
        pulseDot: "pulseDot 1.4s ease-in-out infinite",
        shimmer: "shimmer 2.5s linear infinite",
        floatGlow: "floatGlow 3s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
