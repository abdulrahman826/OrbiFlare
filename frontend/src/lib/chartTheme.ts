// Shared chart colours. Recharts/canvas/SVG props take literal colour values, not Tailwind classes, so this is the one place
// non-Tailwind consumers (charts, the map) read the ORBIFLARE industrial palette from -- keep it in sync with tailwind.config.ts.
export const CHART = {
  grid: "#5A5449", // gridlines need to read clearly against a dark chart background, so this uses the *stronger* border tone, not the hairline one
  axisLine: "#5A5449",
  tickText: "#957949",
  tooltipBg: "#29251E",
  tooltipBorder: "#5A5449",
  primary: "#B69A6A", // desert -- the default single-series colour
  secondary: "#A9573C", // terracotta -- used to contrast a second series/category, or to flag escalation/deviation
  normal: "#637048", // olive -- the Thermal Twin's "what was normal" baseline pattern, never deviation
  fallback: "#B69A6A",
} as const;

export const TOOLTIP_STYLE = { background: CHART.tooltipBg, border: `1px solid ${CHART.tooltipBorder}`, fontSize: 11, color: "#D6C3A0" };

export const SEVERITY_COLORS: Record<string, string> = { LOW: "#637048", MEDIUM: "#B69A6A", HIGH: "#A9573C", CRITICAL: "#CD4E3B" };
