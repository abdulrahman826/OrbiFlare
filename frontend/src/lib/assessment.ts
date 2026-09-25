// Presentation rules for the Investigation hierarchy (NASA observation -> context -> behaviour -> assessment -> limitations).
// Pure functions: they only label and order what the backend computed. No risk, baseline or ML logic lives here.
import type { BaselineConfidence, ContextQuality, FacilityContext } from "@/types/domain";

export interface BaselineView {
  label: string;             // short status
  twinTitle: string;         // heading for the Thermal Twin section
  caution: string | null;    // what the status does and does not allow us to infer
  weight: "full" | "discounted" | "none";
}

export function baselineView(status: BaselineConfidence | null | undefined, hasFacility: boolean): BaselineView {
  switch (status) {
    case "ESTABLISHED":
      return { label: "Established baseline", twinTitle: "Thermal Twin — established baseline", caution: "Enough real history to characterise this facility's normal behaviour.", weight: "full" };
    case "LIMITED":
      return {
        label: "Limited baseline", twinTitle: "Thermal Twin — LIMITED BASELINE",
        caution: "Limited baseline — insufficient history for strong behavioural inference. Deviation counts only partially toward risk.", weight: "discounted",
      };
    case "INSUFFICIENT":
      return { label: "Insufficient baseline", twinTitle: "Thermal Twin — insufficient baseline", caution: "Insufficient history: no baseline is asserted, and deviation contributes nothing to risk.", weight: "none" };
    default:
      return hasFacility
        ? { label: "No baseline computed", twinTitle: "Thermal Twin — unavailable", caution: "No baseline could be computed for this facility.", weight: "none" }
        : { label: "No facility baseline", twinTitle: "Thermal Twin — no facility context", caution: "No facility context, so there is nothing to compare against. This is not evidence of a natural fire.", weight: "none" };
  }
}

export interface QualityView { label: string; strong: boolean; caution: string | null; meaning: string | null }

/** What each facility-context grade means. Quality reflects how specific the facility record is; it is never proof of a source. */
export function contextQualityView(q: ContextQuality | null | undefined): QualityView {
  if (q === "HIGH") return { label: "High", strong: true, caution: null, meaning: "High-quality facility context based on available facility metadata." };
  if (q === "MEDIUM") return { label: "Medium", strong: false, caution: "Identifiable site, but less specific metadata.", meaning: "Moderate facility context; source attribution remains uncertain." };
  if (q === "LOW") return {
    label: "Low", strong: false, meaning: "Low-quality spatial context; not treated as strong attribution evidence.",
    caution: "Generic industrial land-use record, not an identified installation. Shown as context; not counted as strong evidence.",
  };
  return { label: "Not classified", strong: false, caution: null, meaning: null };
}

export const ATTRIBUTION_NOTE = "Facility context is spatial association, not source attribution. Nearby does not mean caused by.";
export const ML_ROLE_NOTE = "ML evidence is one component of OrbiFlare's evidence stack and is not presented as confirmation of a fire.";
export const ML_CORRELATION_NOTE = "Evidence sources may be correlated; ML output is treated as one evidence component.";
export const MODEL_EVALUATION_LABEL = "Development-set evaluation (random hold-out)";

/** Badge for a behavioural-deviation dimension. A significant-looking deviation on LIMITED history is qualified, never shown as an established one. */
export function deviationBadge(dim: { is_significant: boolean; is_notable: boolean }, baseline: BaselineConfidence | null | undefined): { text: string; tone: "significant" | "notable" | "normal" | "limited-significant" | "limited-notable" } {
  const limited = baseline === "LIMITED";
  if (dim.is_significant) return limited ? { text: "Significant deviation — LIMITED HISTORY", tone: "limited-significant" } : { text: "Significant", tone: "significant" };
  if (dim.is_notable) return limited ? { text: "Notable deviation — LIMITED HISTORY", tone: "limited-notable" } : { text: "Notable", tone: "notable" };
  return { text: "Normal", tone: "normal" };
}

export const NO_CONTEXT_LIMITATION = "No relevant facility context within the configured radius. Absence of facility context does not indicate a natural fire.";
export const NEARBY_NOTE = "Nearby does not mean caused by. Facility distance is spatial association only.";
export const ML_OVERLAP_NOTE =
  "ML evidence uses proxy-labelled development data and partially overlaps with facility-context features. It should not be interpreted as an independent confirmation.";

export interface FacilityContextView {
  hasContext: boolean;
  headline: string;
  quality: QualityView;
  limitation: string | null;
  meaning: string | null;
  attribution: string;
  rows: { label: string; value: string }[];
}

export function facilityContextView(ctx: FacilityContext | null): FacilityContextView {
  if (!ctx) return { hasContext: false, headline: "Facility context unavailable.", quality: contextQualityView(null), limitation: null, meaning: null, attribution: ATTRIBUTION_NOTE, rows: [] };
  const n = ctx.nearest;
  if (!n) return { hasContext: false, headline: ctx.statement || NO_CONTEXT_LIMITATION, quality: contextQualityView(null), limitation: NO_CONTEXT_LIMITATION, meaning: null, attribution: ATTRIBUTION_NOTE,
    rows: [{ label: "Nearest facility", value: "none within search radius" }, { label: "Nearby facilities", value: `0 within ${ctx.radius_km} km` }] };
  const quality = contextQualityView(n.context_quality);
  return {
    hasContext: true, headline: ctx.statement, quality, limitation: quality.strong ? null : quality.caution, meaning: quality.meaning, attribution: ATTRIBUTION_NOTE,
    rows: [
      { label: "Nearest facility", value: n.name },
      { label: "Facility type", value: n.facility_type.replace(/_/g, " ") },
      { label: "Distance", value: `${n.distance_km.toFixed(2)} km` },
      { label: "Facility source", value: n.source },
      { label: "Facility context quality", value: quality.label },
      { label: "Nearby facilities", value: `${ctx.nearby_count} within ${ctx.radius_km} km` },
    ],
  };
}

/** The limitations an analyst must keep in mind for THIS event, derived from its own evidence state. */
export function limitationsFor(opts: { baseline: BaselineConfidence | null | undefined; hasFacility: boolean; quality: ContextQuality | null | undefined; mlPresent: boolean }): string[] {
  const out: string[] = [];
  const b = baselineView(opts.baseline, opts.hasFacility);
  if (opts.baseline !== "ESTABLISHED") out.push(b.caution ?? b.label);
  if (!opts.hasFacility) out.push(NO_CONTEXT_LIMITATION);
  else if (opts.quality === "LOW") out.push("Weak facility context: " + (contextQualityView("LOW").caution ?? ""));
  if (opts.mlPresent) out.push("Correlated evidence: " + ML_OVERLAP_NOTE + " " + ML_CORRELATION_NOTE);
  out.push("No independent confirmation: a FIRMS detection is a thermal observation, not a confirmed fire.");
  return out;
}
