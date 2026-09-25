import type { Config } from "tailwindcss";

// Light, official palette. The `base` scale keeps its numeric names but is INVERTED relative to the earlier dark theme:
// low numbers = page/panel surfaces (light), high-contrast text = `base-100` (near-black).
const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        base: {
          950: "#F5F1E8", // page background (warm ivory)
          900: "#EDE8DA", // sidebar / top bar
          850: "#FBF9F3", // panels
          800: "#F0EBDF", // hover / input fill
          700: "#DAD3C2", // hairline borders
          600: "#C2BAA5", // stronger borders
          500: "#A39C88",
          400: "#6C7065", // muted text
          300: "#54584E", // secondary text
          200: "#30342F", // body text
          100: "#1F2421", // primary text
        },
        accent: { DEFAULT: "#2F4A3A", dim: "#1F3328", bright: "#3F6350" }, // deep forest green
        ochre: { DEFAULT: "#8A6A1E" },
        info: { DEFAULT: "#3B4F8F" }, // restrained indigo (historical records)
        sev: { low: "#3F7A52", medium: "#96690A", high: "#B4530F", critical: "#A82A24" },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', '"Source Sans 3"', '"Segoe UI"', "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "SFMono-Regular", "Consolas", "Menlo", "monospace"],
      },
      borderRadius: { DEFAULT: "3px", md: "4px" },
    },
  },
  plugins: [],
};

export default config;
