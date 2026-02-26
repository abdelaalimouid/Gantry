/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        midnight: "#0f172a",
        panel: "#1e293b",
        border: "#334155",
        accent: "#06b6d4", // cyan-500
        danger: "#ef4444", // red-500
        warning: "#f59e0b", // amber-500
        healthy: "#22d3ee", // cyan-400
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4,0,0.6,1) infinite",
      },
    },
  },
  plugins: [],
};
