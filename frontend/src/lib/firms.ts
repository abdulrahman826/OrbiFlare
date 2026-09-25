// Presentation helpers for raw NASA FIRMS attributes. No intelligence here: only labelling and counting of fields NASA returned.
import type { ThermalObservation } from "@/types/domain";

export const SATELLITE_NAMES: Record<string, string> = { N: "Suomi NPP", N20: "NOAA-20", N21: "NOAA-21" };
/** FIRMS VIIRS confidence flag -> word. This is a per-detection satellite attribute, NOT OrbiFlare severity or risk. */
export const FIRMS_CONFIDENCE: Record<string, string> = { l: "low", n: "nominal", h: "high" };

export function satelliteName(code: string | null | undefined): string {
  return code ? SATELLITE_NAMES[code] ?? code : "unknown";
}

/** "NASA FIRMS · VIIRS NOAA-21 NRT" built from the products/satellites actually present on the observations. */
export function firmsSourceLabel(observations: ThermalObservation[]): string {
  const live = observations.filter((o) => o.source === "FIRMS");
  if (live.length === 0) return "";
  const products = Array.from(new Set(live.map((o) => o.source_product).filter((p): p is string => !!p)));
  const sats = Array.from(new Set(live.map((o) => o.satellite).filter((s): s is string => !!s)));
  if (products.length) {
    // VIIRS_NOAA21_NRT -> "VIIRS NOAA-21 NRT"
    const pretty = products.map((p) => p.replace(/NOAA(\d+)/, "NOAA-$1").replace(/_/g, " "));
    return `NASA FIRMS · ${pretty.join(" + ")}`;
  }
  return `NASA FIRMS · VIIRS ${sats.map(satelliteName).join(" + ")}`.trim();
}

export function confidenceCounts(observations: ThermalObservation[]): string {
  const c: Record<string, number> = {};
  for (const o of observations) {
    const k = FIRMS_CONFIDENCE[o.confidence ?? ""] ?? "n/a";
    c[k] = (c[k] ?? 0) + 1;
  }
  return Object.entries(c).map(([k, n]) => `${k} ×${n}`).join(", ") || "n/a";
}

export function acqUtc(iso: string): string {
  const m = iso.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
  return m ? `${m[1]} ${m[2]}Z` : iso;
}
