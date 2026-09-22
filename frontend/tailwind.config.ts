import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        base: {
          950: "#0a0c0f",
          900: "#0e1116",
          850: "#12151b",
          800: "#171b22",
          700: "#1f242c",
          600: "#2a3038",
          500: "#3a4149",
          400: "#5a6169",
          300: "#7d848c",
          200: "#a8adb3",
          100: "#d4d7da",
        },
        accent: {
          DEFAULT: "#3fd0e0",
          dim: "#1f8f9e",
          bright: "#7ce8f2",
        },
        sev: {
          low: "#4a9a6a",
          medium: "#c9a227",
          high: "#d97b3f",
          critical: "#d1453f",
        },
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      boxShadow: {
        panel: "0 0 0 1px rgba(255,255,255,0.04), 0 2px 8px rgba(0,0,0,0.4)",
      },
    },
  },
  plugins: [],
};

export default config;
