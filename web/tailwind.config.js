/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Plan §A.6 — Industrial Precision Dark tokens
        // Applied progressively per UI phase via gaspol-design.
        "bg-deep": "#020617",
        "bg-base": "#0B1120",
        "bg-elevated": "#111827",
        "bg-hover": "#1A2236",
        "bg-active": "#1E293B",
        primary: "#22C55E",
        "primary-hover": "#16A34A",
        secondary: "#3B82F6",
        warning: "#F59E0B",
        danger: "#EF4444",
        success: "#10B981",
        "text-primary": "#F1F5F9",
        "text-secondary": "#94A3B8",
        "text-tertiary": "#64748B",
        "text-disabled": "#475569",
        "border-default": "#1E293B",
        "border-hover": "#334155",
        "border-active": "#22C55E",
        "border-focus": "#3B82F6",
      },
      fontFamily: {
        sans: ["IBM Plex Sans", "system-ui", "sans-serif"],
        mono: ["Fira Code", "JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
