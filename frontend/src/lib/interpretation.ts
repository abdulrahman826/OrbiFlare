// Source interpretation presentation. Pure functions: they only label and colour what the backend already computed.
// Source interpretation (what kind of thermal source the evidence is consistent with) and operational severity (priority) are TWO separate
// dimensions: the marker FILL shows the interpretation, the marker RING and letter show the severity. Neither implies a confirmed fire.
import type { SourceInterpretationClass, ThermalEvent } from "@/types/domain";

export const INTERP_ORDER: SourceInterpretationClass[] = [
  "INDUSTRIAL_SOURCE_CANDIDATE", "AGRICULTURAL_VEGETATION_CANDIDATE", "PERSISTENT_THERMAL_SOURCE_CANDIDATE", "NATURAL_OTHER_THERMAL_SOURCE_CANDIDATE", "UNCERTAIN",
];
export const INTERP_LABEL: Record<SourceInterpretationClass, string> = {
  INDUSTRIAL_SOURCE_CANDIDATE: "Industrial-source candidate",
  AGRICULTURAL_VEGETATION_CANDIDATE: "Agricultural / vegetation-fire candidate",
  PERSISTENT_THERMAL_SOURCE_CANDIDATE: "Persistent thermal-source candidate",
  NATURAL_OTHER_THERMAL_SOURCE_CANDIDATE: "Natural / other thermal-source candidate",
  UNCERTAIN: "Uncertain",
};
// Restrained industrial palette (no rainbow): terracotta (thermal/industrial), a darker terracotta-brown (persistent), muted olive
// (vegetation), neutral silver-grey (natural/other), pale neutral (uncertain). None of these is used for priority.
export const INTERP_HEX: Record<SourceInterpretationClass, { fill: string; text: string }> = {
  INDUSTRIAL_SOURCE_CANDIDATE: { fill: "#A9573C", text: "#F5EFE4" },
  AGRICULTURAL_VEGETATION_CANDIDATE: { fill: "#7C8A5A", text: "#191714" },
  PERSISTENT_THERMAL_SOURCE_CANDIDATE: { fill: "#7C402C", text: "#F5EFE4" },
  NATURAL_OTHER_THERMAL_SOURCE_CANDIDATE: { fill: "#7D7A6E", text: "#191714" },
  UNCERTAIN: { fill: "#C9C2B0", text: "#29251E" },
};
export const SEVERITY_TEXT: Record<string, string> = { LOW: "Low", MEDIUM: "Medium", HIGH: "High", CRITICAL: "Critical" };

export function interpretationOf(e: Pick<ThermalEvent, "source_interpretation">): { cls: SourceInterpretationClass; label: string; strength: string } {
  const si = e.source_interpretation;
  const cls = (si && INTERP_ORDER.includes(si.classification) ? si.classification : "UNCERTAIN") as SourceInterpretationClass;
  return { cls, label: INTERP_LABEL[cls], strength: si?.strength ?? "UNCERTAIN" };
}

export function strengthText(strength: string): string {
  return strength === "UNCERTAIN" ? "evidence insufficient or conflicting" : `${strength.toLowerCase()} evidence`;
}

/** Compact hover text: interpretation, priority, FRP, persistence. */
export function tooltipText(e: ThermalEvent): string {
  const i = interpretationOf(e);
  return [i.label, `${SEVERITY_TEXT[e.severity ?? "LOW"] ?? "Low"} priority`, `FRP ${e.peak_frp != null ? e.peak_frp.toFixed(1) : "--"} MW`, `Persistence ${e.observation_count} obs`].join("\n");
}

export const esc = (s: unknown): string => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] as string));

/** Marker popup (HTML string, every dynamic value escaped). Only data already on the event; nothing is inferred or invented. */
export function popupHtml(e: ThermalEvent, facilityName?: string): string {
  const i = interpretationOf(e);
  const row = (k: string, v: string) => `<div style="display:flex;justify-content:space-between;gap:10px"><span style="opacity:.65">${k}</span><span>${v}</span></div>`;
  const head = (t: string) => `<div style="margin:7px 0 2px;font-size:9px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;opacity:.6">${t}</div>`;
  const fac = e.facility_id
    ? row("Facility", esc(facilityName ?? e.facility_id)) + row("Facility type", esc((e.facility_type ?? "n/a").replace(/_/g, " "))) +
      row("Distance", e.facility_distance_km != null ? `${e.facility_distance_km.toFixed(2)} km` : "—") + row("Context quality", esc(e.facility_context_quality ? e.facility_context_quality.toLowerCase() : "not classified"))
    : row("Facility", "no usable facility context");
  const dev = e.baseline_confidence === "INSUFFICIENT" ? "insufficient baseline" : e.baseline_confidence == null ? "no facility baseline" : e.overall_deviation_score != null ? `${Math.round(e.overall_deviation_score)}/100${e.baseline_confidence === "LIMITED" ? " (limited history)" : ""}` : "n/a";
  const ml = e.classification === "PERSISTENT_INDUSTRIAL_THERMAL_SOURCE" ? "Class A" : e.classification === "NATURAL_AGRICULTURAL_FIRE_CANDIDATE" ? "Class B candidate" : "not assessed (no usable facility)";
  return `<div style="font-size:11px;min-width:210px;max-width:260px">
    <div style="font-size:9px;font-weight:700;letter-spacing:.09em;opacity:.6">THERMAL EVENT</div>
    <div style="font-family:ui-monospace,monospace;font-size:12px"><b>${esc(e.event_id)}</b> ${e.is_demo ? "· DEMO" : "· LIVE"}</div>
    ${head("Source interpretation")}<div><b>${esc(i.label.toUpperCase())}</b></div><div style="opacity:.75">${esc(strengthText(i.strength))}</div>
    ${row("Operational priority", esc(SEVERITY_TEXT[e.severity ?? "LOW"] ?? "Low") + ` (risk ${Math.round(e.risk_score || 0)})`)}
    ${head("Thermal evidence")}${row("FRP", `${e.peak_frp != null ? e.peak_frp.toFixed(1) : "--"} MW`)}${row("Persistence", `${e.observation_count} obs`)}${row("Duration", `${e.duration_hours.toFixed(1)} h`)}${row("Recurrence", "see investigation")}
    ${head("Spatial context")}${fac}
    ${head("Behaviour")}${row("Baseline state", esc((e.baseline_confidence ?? "none").toString().toLowerCase()))}${row("Deviation", esc(dev))}
    ${head("ML evidence")}${row("Class", ml)}
    <div style="margin-top:7px;border-top:1px solid rgba(0,0,0,.15);padding-top:5px;opacity:.75;line-height:1.35">Source interpretation is evidence-based and not a confirmed fire classification. Operational priority, not fire probability. A FIRMS detection is a thermal observation, not a confirmed fire.${e.facility_id ? " Facility association is spatial context, not source attribution." : ""}</div>
    <div style="margin-top:5px"><a href="/investigation/${esc(e.event_id)}" style="font-weight:700;text-decoration:underline">Open investigation &rarr;</a></div></div>`;
}

/** Operational priority = the OUTER RING only (colour + thickness, never a letter): olive thin (LOW), desert-bronze medium (MEDIUM), bright
 * terracotta thick (HIGH), warm red thick (CRITICAL). HIGH uses the *bright* terracotta tint rather than the base tone so its ring never
 * disappears into an Industrial-candidate fill, which uses the base tone -- fill and ring must stay two visibly separate channels. */
export const SEVERITY_RING: Record<string, { color: string; px: number; rank: number; radius: number }> = {
  LOW: { color: "#5C5F49", px: 1.5, rank: 0, radius: 3.75 }, MEDIUM: { color: "#B69A6A", px: 2.5, rank: 1, radius: 4 },
  HIGH: { color: "#C5775D", px: 3, rank: 2, radius: 5 }, CRITICAL: { color: "#CD4E3B", px: 3, rank: 3, radius: 5 },
};

/** Event marker encoding: FILL comes only from the source interpretation; RING (colour, thickness) only from the operational priority. No text in markers. */
export function markerStyle(e: Pick<ThermalEvent, "source_interpretation" | "severity">): { fill: string; ringColor: string; ringPx: number; rank: number; radius: number; faint: boolean } {
  const cls = interpretationOf(e).cls;
  const c = INTERP_HEX[cls];
  const r = SEVERITY_RING[e.severity || "LOW"] ?? SEVERITY_RING.LOW;
  // An uncertain LOW event is a faint background dot (no ring, no colour). Uncertain MEDIUM/HIGH keep their priority ring around the neutral centre.
  return { fill: c.fill, ringColor: r.color, ringPx: r.px, rank: r.rank, radius: r.radius, faint: cls === "UNCERTAIN" && (e.severity || "LOW") === "LOW" };
}
