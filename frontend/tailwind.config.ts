import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // Primary palette — obsidian + electric amber
        obsidian:  { DEFAULT: "#0a0a0f", 50: "#f5f5ff", 100: "#e8e8f8", 200: "#c4c4e8", 800: "#18181f", 900: "#0a0a0f" },
        amber:     { DEFAULT: "#f59e0b", glow: "#fbbf24" },
        surge:     { DEFAULT: "#ef4444", light: "#fca5a5" },   // Price surge
        discount:  { DEFAULT: "#10b981", light: "#6ee7b7" },   // Price discount
        neutral:   { DEFAULT: "#6b7280" },
        panel:     "#13131a",
        border:    "#1f1f2e",
      },
      fontFamily: {
        display: ["var(--font-display)", "system-ui"],
        body:    ["var(--font-body)", "system-ui"],
        mono:    ["var(--font-mono)", "monospace"],
      },
      animation: {
        "pulse-dot":   "pulse-dot 2s ease-in-out infinite",
        "price-flash": "price-flash 0.6s ease-out",
        "slide-up":    "slide-up 0.4s cubic-bezier(0.16,1,0.3,1)",
        "fade-in":     "fade-in 0.3s ease-out",
        "shimmer":     "shimmer 1.5s infinite",
      },
      keyframes: {
        "pulse-dot": {
          "0%, 100%": { transform: "scale(1)", opacity: "1" },
          "50%":      { transform: "scale(1.4)", opacity: "0.7" },
        },
        "price-flash": {
          "0%":   { backgroundColor: "rgba(245,158,11,0.3)", transform: "scale(1.02)" },
          "100%": { backgroundColor: "transparent", transform: "scale(1)" },
        },
        "slide-up": {
          "0%":   { transform: "translateY(8px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        "fade-in": {
          "0%":   { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "shimmer": {
          "0%":   { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      boxShadow: {
        "glow-amber":    "0 0 20px rgba(245,158,11,0.3)",
        "glow-green":    "0 0 20px rgba(16,185,129,0.3)",
        "glow-red":      "0 0 20px rgba(239,68,68,0.3)",
        "card":          "0 1px 3px rgba(0,0,0,0.4), 0 8px 24px rgba(0,0,0,0.3)",
        "card-hover":    "0 4px 12px rgba(0,0,0,0.5), 0 16px 40px rgba(0,0,0,0.4)",
      },
    },
  },
  plugins: [],
};

export default config;
