import type { Config } from "tailwindcss";

export default {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        ember: {
          300: "#f0b089",
          400: "#e39161",
          500: "#d97745",
        },
        steel: {
          50: "#f4f7fb",
          200: "#c9d4e3",
          300: "#9aa8bc",
          500: "#667890",
          700: "#2a3648",
          800: "#1a2330",
          900: "#121821",
          950: "#0b1016",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "system-ui", "sans-serif"],
        body: ["var(--font-body)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
