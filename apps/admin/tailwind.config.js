/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "ae-base": "#020408",
        "ae-surface": "#070b12",
        "ae-elevated": "#0c1219",
        "ae-panel": "#0f1624",
        "ae-subtle": "#1a2535",
        "ae-border": "rgba(255,255,255,0.06)",
        "ae-border-bright": "rgba(255,255,255,0.12)",
        "ae-cyan": "#00d4ff",
        "ae-cyan-dim": "#0891b2",
        "ae-violet": "#8b5cf6",
        "ae-amber": "#f59e0b",
        "ae-red": "#ef4444",
        "ae-green": "#10b981",
        "ae-text": "#e2e8f0",
        "ae-muted": "#64748b",
        "ae-faint": "#334155",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      backgroundImage: {
        "radial-base":
          "radial-gradient(ellipse at 50% 0%, rgba(0, 212, 255, 0.06) 0%, transparent 55%), radial-gradient(ellipse at 80% 50%, rgba(139, 92, 246, 0.04) 0%, transparent 45%)",
        "radial-panel":
          "radial-gradient(ellipse at 50% 100%, rgba(0, 212, 255, 0.03) 0%, transparent 60%)",
        "grid-lines":
          "linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)",
      },
      backgroundSize: {
        "grid-md": "48px 48px",
      },
      boxShadow: {
        "glow-cyan": "0 0 24px rgba(0, 212, 255, 0.2), 0 0 48px rgba(0, 212, 255, 0.08)",
        "glow-cyan-sm": "0 0 10px rgba(0, 212, 255, 0.25)",
        "glow-green": "0 0 14px rgba(16, 185, 129, 0.3)",
        "glow-red": "0 0 14px rgba(239, 68, 68, 0.3)",
        "glow-amber": "0 0 14px rgba(245, 158, 11, 0.3)",
        "glow-violet": "0 0 14px rgba(139, 92, 246, 0.3)",
        "panel":
          "0 0 0 1px rgba(255,255,255,0.06), 0 4px 24px rgba(0,0,0,0.6)",
        "panel-hover":
          "0 0 0 1px rgba(255,255,255,0.10), 0 4px 24px rgba(0,0,0,0.6)",
      },
      animation: {
        "pulse-slow": "pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "ping-slow": "ping 3s cubic-bezier(0, 0, 0.2, 1) infinite",
        "flow": "flow 3s linear infinite",
        "shimmer": "shimmer 2s linear infinite",
        "scan": "scan 4s linear infinite",
      },
      keyframes: {
        flow: {
          "0%": { "stroke-dashoffset": "100" },
          "100%": { "stroke-dashoffset": "0" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
      },
      transitionDuration: {
        "400": "400ms",
      },
    },
  },
  plugins: [],
};
