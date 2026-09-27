import type { Config } from "tailwindcss";

// ORBIFLARE industrial thermal intelligence theme. Anchors (do not drift from these without a deliberate design decision):
//   #191714 near-black background · #29251E warm graphite surface · #B69A6A desert bronze (secondary accent)
//   #A9573C terracotta (thermal / abnormal / important actions) · #D6C3A0 dust (primary text) · #454737 dark olive (geographic / neutral context)
// Terracotta is reserved for things that deserve attention (thermal activity, high severity, important actions) -- it is never the default
// colour of ordinary chrome. Desert/accent carries routine interactive elements (buttons, links, active nav). Silver is for borders, dividers,
// and technical metadata; it stays subtle -- never a metallic/sci-fi treatment.
// The `base` numeric scale: high numbers = darker surfaces (950 = page bg), low numbers = lighter, more readable text (100 = primary text).
const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        base: {
          950: "#191714", // page background (near-black)
          900: "#201D18", // sidebar / top bar (recessed chrome)
          850: "#29251E", // panels (surface)
          800: "#353027", // hover / input fill
          700: "#2D2A25", // hairline borders (silver, subtle)
          600: "#5A5449", // stronger borders (silver)
          500: "#6E6350",
          400: "#957949", // muted text
          300: "#B69A6A", // secondary text / metadata (desert)
          200: "#C7B18C", // body text
          100: "#D6C3A0", // primary text (dust)
        },
        accent: { DEFAULT: "#B69A6A", dim: "#8A7350", bright: "#C9B489" }, // desert bronze -- routine interactive elements
        desert: { DEFAULT: "#B69A6A", dim: "#8A7350", bright: "#C9B489" },
        terracotta: { DEFAULT: "#A9573C", dim: "#7C402C", bright: "#C5775D" }, // thermal / abnormal / important actions only
        dust: { DEFAULT: "#D6C3A0" },
        olive: { DEFAULT: "#454737", bright: "#637048" }, // geographic / contextual / neutral operational
        silver: { DEFAULT: "#5A5449", dim: "#2D2A25", bright: "#B9B6A8" }, // borders, dividers, technical metadata, system chrome
        info: { DEFAULT: "#5C6A78" }, // muted slate -- historical / reference records only, kept distinct from live-event colours
        sev: { low: "#637048", medium: "#B69A6A", high: "#A9573C", critical: "#CD4E3B" },
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
