import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { BaselineBanner } from "@/components/BaselineBanner";
import { FirmsSourceBadge, HistoricalBadge } from "@/components/DemoBadge";
import { FacilityContextSection } from "@/components/FacilityContextSection";
import { MlEvidenceNote } from "@/components/MlEvidenceNote";
import { NasaObservationRows } from "@/components/NasaObservationRows";
import { RiskExplanation } from "@/components/RiskExplanation";
import { DeviationTable } from "@/components/DeviationTable";
import { baselineView, contextQualityView, deviationBadge, facilityContextView, limitationsFor, NO_CONTEXT_LIMITATION } from "@/lib/assessment";
import { firmsSourceLabel } from "@/lib/firms";
import type { ContextFacility, Deviation, FacilityContext, Risk, ThermalEvent, ThermalObservation } from "@/types/domain";

const obs = (over: Partial<ThermalObservation> = {}): ThermalObservation => ({
  observation_id: "o1", timestamp: "2026-09-24T06:44:00", latitude: 21.1, longitude: 72.6, sensor: "VIIRS", brightness_temperature: 335.1,
  brightness_temperature_11: 290.1, frp: 4.2, confidence: "n", day_night: "D", source: "FIRMS", source_id: null, quality_flags: [],
  satellite: "N21", instrument: "VIIRS", scan: 0.41, track: 0.39, source_product: "VIIRS_NOAA21_NRT", is_live_firms: true, ...over,
} as ThermalObservation);

const event = { event_id: "EVT-1", peak_frp: 9.9, mean_frp: 5.1, peak_bt: 341.5, mean_bt: 333.0, observation_count: 3, duration_hours: 2, footprint_radius_km: 0.3 } as ThermalEvent;

const fac = (over: Partial<ContextFacility> = {}): ContextFacility => ({
  facility_id: "OSM-1", name: "Reliance Refinery", facility_type: "refinery", latitude: 22.3, longitude: 69.8, distance_km: 0.1,
  source: "OSM", country: "IND", context_quality: "HIGH", ...over,
});
const ctx = (nearest: ContextFacility | null, over: Partial<FacilityContext> = {}): FacilityContext => ({
  event_id: "EVT-1", radius_km: 3, nearest, nearby: nearest ? [nearest] : [], nearby_count: nearest ? 1 : 0,
  statement: nearest ? "Refinery facility within 0.10 km (spatial association; high-quality context)." : "No relevant facility context within the 3 km search radius. Absence of facility context does not indicate a natural fire (facility datasets are incomplete).",
  note: "Nearby does not mean caused by. Facility distance is spatial association only.", ...over,
});
const risk = (over: Partial<Risk> = {}): Risk => ({
  event_id: "EVT-1", risk_score: 12.3, severity: "LOW", risk_factors: [], explanation: "x", caveats: [],
  severity_reason: "LOW: score 12.3 is 22.7 points below the MEDIUM threshold (35). Main limit: insufficient baseline.",
  contributing: ["3 persistent observations (+4)"], limiting: ["insufficient baseline: deviation contributes 0", "no independent incident confirmation (imagery, ground truth)"],
  missing_evidence: ["independent confirmation of an incident"], escalation_evidence: ["more persistent observations (now 3)"], ...over,
} as Risk);
const html = (el: React.ReactElement) => renderToStaticMarkup(el);

describe("live FIRMS source", () => {
  it("a live event shows the NASA FIRMS product(s) actually on its observations", () => {
    const label = firmsSourceLabel([obs(), obs({ source_product: "VIIRS_NOAA20_NRT", satellite: "N20" })]);
    expect(label).toBe("NASA FIRMS · VIIRS NOAA-21 NRT + VIIRS NOAA-20 NRT");
    const h = html(<FirmsSourceBadge label={label} />) + html(<NasaObservationRows event={event} observations={[obs()]} sourceLabel={label} />);
    expect(h).toContain("NASA FIRMS");
    expect(h).not.toMatch(/DEMO|SYNTHETIC/i);
  });
  it("synthetic observations never produce a NASA FIRMS label", () => {
    expect(firmsSourceLabel([obs({ source: "DEMO", is_live_firms: false })])).toBe("");
  });
});

describe("NASA confidence is separate from OrbiFlare risk", () => {
  it("the NASA block shows FIRMS confidence and no OrbiFlare risk/severity", () => {
    const h = html(<NasaObservationRows event={event} observations={[obs({ confidence: "h" })]} sourceLabel="NASA FIRMS · VIIRS NOAA-21 NRT" />);
    expect(h).toContain("FIRMS confidence");
    expect(h).toContain("high ×1");
    expect(h).not.toMatch(/risk|severity/i);
  });
  it("the risk block never mentions NASA confidence, and does not change when the NASA confidence changes", () => {
    const r = html(<RiskExplanation risk={risk()} />);
    expect(r).not.toMatch(/FIRMS confidence|nominal|confidence: /i);
    const low = html(<NasaObservationRows event={event} observations={[obs({ confidence: "l" })]} sourceLabel="s" />);
    const high = html(<NasaObservationRows event={event} observations={[obs({ confidence: "h" })]} sourceLabel="s" />);
    expect(low).not.toEqual(high);
    expect(html(<RiskExplanation risk={risk()} />)).toEqual(r);   // same risk object -> identical markup, whatever NASA reported
  });
  it("risk copy denies rather than asserts a confirmed fire", () => {
    const r = html(<RiskExplanation risk={risk()} />);
    expect(r).toContain("not a confirmed fire");
    expect(r.replace("not a confirmed fire", "")).not.toMatch(/confirmed fire/i);
  });
});

describe("baseline status is displayed honestly", () => {
  it("established", () => {
    const h = html(<BaselineBanner status="ESTABLISHED" hasFacility contribution={12} cap={35} />);
    expect(h).toContain("Established baseline");
    expect(h).toContain("+12.0 pts (max +35.0");
    expect(baselineView("ESTABLISHED", true).weight).toBe("full");
  });
  it("limited is never presented as an established twin", () => {
    const h = html(<BaselineBanner status="LIMITED" hasFacility contribution={5.6} cap={14} />);
    expect(h).toContain("Limited baseline");
    expect(h).toContain("insufficient history for strong behavioural inference");
    expect(h).toContain("+5.6 pts (max +14.0");
    expect(h).not.toContain("Established");
    expect(baselineView("LIMITED", true).twinTitle).toBe("Thermal Twin — LIMITED BASELINE");
    expect(baselineView("LIMITED", true).weight).toBe("discounted");
  });
  it("insufficient asserts no baseline and no contribution", () => {
    const h = html(<BaselineBanner status="INSUFFICIENT" hasFacility contribution={0} cap={0} />);
    expect(h).toContain("Insufficient baseline");
    expect(h).toContain("contributes nothing to risk");
    expect(h).not.toContain("Established");
    expect(baselineView("INSUFFICIENT", true).weight).toBe("none");
  });
  it("no facility context means no facility baseline, and says that is not evidence of a natural fire", () => {
    const v = baselineView(null, false);
    expect(v.label).toBe("No facility baseline");
    expect(v.caution).toContain("not evidence of a natural fire");
  });
});

describe("facility context", () => {
  it("no facility context displays the limitation and never implies a natural fire", () => {
    const h = html(<FacilityContextSection ctx={ctx(null)} />);
    expect(h).toContain("No relevant facility context within the configured radius");
    expect(h).toContain("Absence of facility context does not indicate a natural fire");
    expect(h).toContain("none within search radius");
    expect(facilityContextView(ctx(null)).hasContext).toBe(false);
    expect(NO_CONTEXT_LIMITATION).toMatch(/does not indicate a natural fire/);
  });
  it("identified facility displays distance, type, source and quality — as association only", () => {
    const h = html(<FacilityContextSection ctx={ctx(fac())} />);
    expect(h).toContain("Reliance Refinery");
    expect(h).toContain("0.10 km");
    expect(h).toContain("Refinery");
    expect(h).toContain("OSM");
    expect(h).toContain("Facility context quality");
    expect(h).toContain("High");
    expect(h).toContain("Nearby does not mean caused by");
    expect(h).not.toMatch(/caused the|fire at|refinery fire/i);
  });
  it("a generic land-use record is shown as weak context, not as strong evidence", () => {
    const generic = fac({ name: "Unnamed industrial", facility_type: "industrial", context_quality: "LOW" });
    const h = html(<FacilityContextSection ctx={ctx(generic, { statement: "Generic industrial land-use record within 0.10 km (spatial association; low-quality context, not an identified installation)." })} />);
    expect(h).toContain("Low");
    expect(h).toContain("not counted as strong evidence");
    expect(h).not.toContain(">High<");
    expect(contextQualityView("LOW").strong).toBe(false);
    expect(contextQualityView("HIGH").strong).toBe(true);
    expect(contextQualityView("MEDIUM").strong).toBe(false);
  });
});

describe("ML evidence and limitations", () => {
  it("discloses the overlap with facility features and refuses to call it independent confirmation", () => {
    const h = html(<MlEvidenceNote />);
    expect(h).toContain("ML evidence, not a verdict");
    expect(h).toContain("proxy-labelled development data");
    expect(h).toContain("partially overlaps with facility-context features");
    expect(h).toContain("should not be interpreted as an independent confirmation");
  });
  it("limitations reflect this event's own evidence state", () => {
    const l = limitationsFor({ baseline: "LIMITED", hasFacility: true, quality: "LOW", mlPresent: true }).join(" | ");
    expect(l).toContain("Limited baseline");
    expect(l).toContain("Weak facility context");
    expect(l).toContain("Correlated evidence");
    expect(l).toContain("No independent confirmation");
    const none = limitationsFor({ baseline: null, hasFacility: false, quality: null, mlPresent: false }).join(" | ");
    expect(none).toContain("does not indicate a natural fire");
    const strong = limitationsFor({ baseline: "ESTABLISHED", hasFacility: true, quality: "HIGH", mlPresent: false }).join(" | ");
    expect(strong).not.toContain("Limited baseline");
    expect(strong).not.toContain("Weak facility context");
    expect(strong).toContain("No independent confirmation");
  });
});

describe("historical reference stays separate from live FIRMS", () => {
  it("the historical badge is unmistakably not a live detection", () => {
    const h = html(<HistoricalBadge />);
    expect(h).toContain("NOT A LIVE FIRMS DETECTION");
    expect(h).not.toContain("NASA FIRMS ·");
    expect(html(<HistoricalBadge compact />)).toContain("HISTORICAL");
  });
  it("a live source badge never reads as historical", () => {
    const h = html(<FirmsSourceBadge label="NASA FIRMS · VIIRS NOAA-21 NRT" />);
    expect(h).not.toMatch(/HISTORICAL/i);
  });
});

describe("risk explanation content", () => {
  it("shows why, what supports it, what limits it, what is missing and what would raise it", () => {
    const h = html(<RiskExplanation risk={risk()} />);
    for (const t of ["below the MEDIUM threshold", "Contributing evidence", "Limiting factors", "Missing evidence", "What would raise this score if observed"]) expect(h).toContain(t);
    expect(h).toContain("no independent incident confirmation");
  });
});

describe("hardening: facility-context meaning, limited-history deviation, ML role", () => {
  it("each context quality explains what it means without over-claiming", () => {
    expect(contextQualityView("HIGH").meaning).toBe("High-quality facility context based on available facility metadata.");
    expect(contextQualityView("MEDIUM").meaning).toBe("Moderate facility context; source attribution remains uncertain.");
    expect(contextQualityView("LOW").meaning).toBe("Low-quality spatial context; not treated as strong attribution evidence.");
  });
  it("the facility section states the meaning and that context is not attribution", () => {
    const low = html(<FacilityContextSection ctx={ctx(fac({ context_quality: "LOW", name: "Unnamed industrial", facility_type: "industrial" }))} />);
    expect(low).toContain("Low-quality spatial context; not treated as strong attribution evidence.");
    expect(low).toContain("Facility context is spatial association, not source attribution.");
    expect(html(<FacilityContextSection ctx={ctx(null)} />)).toContain("not source attribution");
  });
  it("a significant deviation on LIMITED history is qualified; on established history it is not", () => {
    const sig = { is_significant: true, is_notable: true };
    expect(deviationBadge(sig, "LIMITED").text).toBe("Significant deviation — LIMITED HISTORY");
    expect(deviationBadge(sig, "LIMITED").tone).toBe("limited-significant");
    expect(deviationBadge(sig, "ESTABLISHED").text).toBe("Significant");
    expect(deviationBadge({ is_significant: false, is_notable: true }, "LIMITED").text).toBe("Notable deviation — LIMITED HISTORY");
    expect(deviationBadge({ is_significant: false, is_notable: false }, "LIMITED").text).toBe("Normal");
  });
  it("the deviation table shows the limited-history qualification and never an established-looking badge for it", () => {
    const dim = (sig: boolean) => ({ status: "COMPUTED", observed_value: 0, expected_median: 0.49, expected_range: [0, 1], robust_z: 3, is_notable: true, is_significant: sig, explanation: "x" });
    const dev = (b: string) => ({ baseline_confidence: b, overall_deviation_score: 40, intensity: dim(false), persistence: dim(false), duration: dim(false), temporal: dim(false), spatial: dim(false), recurrence: dim(true) }) as unknown as Deviation;
    const limited = html(<DeviationTable deviation={dev("LIMITED")} />);
    expect(limited).toContain("Significant deviation — LIMITED HISTORY");
    expect(limited).not.toMatch(/>Significant</);
    const est = html(<DeviationTable deviation={dev("ESTABLISHED")} />);
    expect(est).toMatch(/>Significant</);
    expect(est).not.toContain("LIMITED HISTORY");
  });
  it("an insufficient baseline shows no deviation values or badges at all", () => {
    const ins = (n: string) => ({ status: "INSUFFICIENT_BASELINE", observed_value: null, expected_median: null, expected_range: null, robust_z: null, is_notable: false, is_significant: false, explanation: n });
    const dev = { baseline_confidence: "INSUFFICIENT", overall_deviation_score: 0, intensity: ins("a"), persistence: ins("b"), duration: ins("c"), temporal: ins("d"), spatial: ins("e"), recurrence: ins("f") } as unknown as Deviation;
    const h = html(<DeviationTable deviation={dev} />);
    expect(h).toContain("INSUFFICIENT BASELINE");
    expect(h).not.toMatch(/Significant|Notable/);
  });
  it("ML evidence is framed as one correlated component, never a confirmation", () => {
    const h = html(<MlEvidenceNote />);
    expect(h).toContain("is not presented as confirmation of a fire.");
    expect(h).toContain("Evidence sources may be correlated; ML output is treated as one evidence component.");
  });
});
