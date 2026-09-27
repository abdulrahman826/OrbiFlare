import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { EventCard } from "@/components/EventCard";
import { HistoryStatusNote } from "@/components/HistoryStatusNote";
import { MapLegend } from "@/components/MapPanel";
import { SourceInterpretationPanel } from "@/components/SourceInterpretationPanel";
import { TwinHistorySummary } from "@/components/TwinHistorySummary";
import { INTERP_HEX, INTERP_LABEL, INTERP_ORDER, interpretationOf, popupHtml, tooltipText } from "@/lib/interpretation";
import type { HistoryStatus, SourceInterpretation, SourceInterpretationClass, ThermalEvent, ThermalTwin } from "@/types/domain";

const ev = (cls: SourceInterpretationClass | null, over: Record<string, unknown> = {}) =>
  ({
    event_id: "EVT-1", first_detected: "2026-09-20T06:00:00", severity: "MEDIUM", risk_score: 41, classification: "PERSISTENT_INDUSTRIAL_THERMAL_SOURCE", is_demo: false,
    facility_id: "F1", facility_type: "oil_refinery", facility_distance_km: 1.24, facility_context_quality: "HIGH", centroid_lat: 21, centroid_lon: 72, peak_frp: 24.8, observation_count: 6,
    duration_hours: 7.5, trajectory_direction: "STABLE", baseline_confidence: "LIMITED", overall_deviation_score: 33,
    source_interpretation: cls ? { classification: cls, label: INTERP_LABEL[cls], strength: cls === "UNCERTAIN" ? "UNCERTAIN" : "MODERATE" } : null, ...over,
  }) as unknown as ThermalEvent;

afterEach(() => vi.restoreAllMocks());

describe("map classification", () => {
  it("has five distinct candidate classes with distinct fills; uncertain is light; no class is called a fire", () => {
    expect(INTERP_ORDER).toHaveLength(5);
    expect(new Set(INTERP_ORDER.map((c) => INTERP_HEX[c].fill)).size).toBe(5);
    expect(INTERP_HEX.UNCERTAIN.fill).toBe("#C9C2B0");
    for (const c of INTERP_ORDER) expect(INTERP_LABEL[c]).not.toMatch(/industrial fire|agricultural fire|natural fire|confirmed/i);
  });
  it("an event without an interpretation is Uncertain, never a guessed class", () => {
    expect(interpretationOf(ev(null)).cls).toBe("UNCERTAIN");
    expect(interpretationOf({ source_interpretation: { classification: "BOGUS" } } as never).cls).toBe("UNCERTAIN");
  });
  it("legend lists the five interpretations and, separately, the operational priority", () => {
    const h = renderToStaticMarkup(<MapLegend showFirms={false} showDemoObs={false} showIncidents={false} showAdmin={false} />);
    for (const c of INTERP_ORDER.filter((x) => x !== "NATURAL_OTHER_THERMAL_SOURCE_CANDIDATE")) expect(h).toContain(INTERP_LABEL[c]);
    expect(h).toContain("Natural / other");
    for (const t of ["Map key", "Thermal source", "Operational priority", "High / Critical", "Medium", "Context", "Facility", "Fill = source interpretation · Ring = operational priority"]) expect(h).toContain(t);
    expect(h.indexOf("Thermal source")).toBeLessThan(h.indexOf("Operational priority"));
    expect(h).toContain("not a confirmed fire");
    expect(h).not.toMatch(/absolute|bottom-2|left-2/);                                  // the key is never an overlay on the map
  });
  it("tooltip is compact: interpretation, priority, FRP, persistence", () => {
    expect(tooltipText(ev("INDUSTRIAL_SOURCE_CANDIDATE")).split("\n")).toEqual(["Industrial-source candidate", "Medium priority", "FRP 24.8 MW", "Persistence 6 obs"]);
    expect(tooltipText(ev("AGRICULTURAL_VEGETATION_CANDIDATE", { severity: "LOW", peak_frp: 8.1, observation_count: 2 })).split("\n")).toEqual([
      "Agricultural / vegetation-fire candidate", "Low priority", "FRP 8.1 MW", "Persistence 2 obs"]);
  });
  it("popup shows interpretation, strength, priority, evidence, context, behaviour, ML and the required disclaimers", () => {
    const h = popupHtml(ev("INDUSTRIAL_SOURCE_CANDIDATE"), "Test Refinery");
    for (const t of ["THERMAL EVENT", "EVT-1", "INDUSTRIAL-SOURCE CANDIDATE", "moderate evidence", "Medium (risk 41)", "Thermal evidence", "24.8 MW", "6 obs", "Spatial context", "Test Refinery",
      "oil refinery", "1.24 km", "high", "Behaviour", "limited", "33/100 (limited history)", "ML evidence", "Class A"]) expect(h).toContain(t);
    expect(h).toContain("Source interpretation is evidence-based and not a confirmed fire classification.");
    expect(h).toContain("Facility association is spatial context, not source attribution.");
  });
  it("popup without a facility says so and omits the facility disclaimer; insufficient baseline shows no deviation value", () => {
    const h = popupHtml(ev("UNCERTAIN", { facility_id: null, facility_distance_km: null, baseline_confidence: null, classification: null, overall_deviation_score: null }));
    expect(h).toContain("no usable facility context");
    expect(h).toContain("not assessed (no usable facility)");
    expect(h).not.toContain("not source attribution");
    expect(popupHtml(ev("UNCERTAIN", { baseline_confidence: "INSUFFICIENT", overall_deviation_score: null }))).toContain("insufficient baseline");
  });
  it("popup escapes untrusted text", () => {
    const h = popupHtml(ev("INDUSTRIAL_SOURCE_CANDIDATE"), "<img src=x onerror=alert(1)>");
    expect(h).not.toContain("<img");
    expect(h).toContain("&lt;img");
  });
  it("priority and interpretation stay separate dimensions on the priority feed card", () => {
    const h = renderToStaticMarkup(<EventCard event={ev("INDUSTRIAL_SOURCE_CANDIDATE")} />);
    expect(h).toContain("Industrial-source candidate");
    expect(h).toContain("moderate evidence");
    expect(h).toContain("MEDIUM");
    expect(h).not.toMatch(/Industrial Fire|Confirmed/);
  });
});

const si = (cls: SourceInterpretationClass, over: Partial<SourceInterpretation> = {}): SourceInterpretation => ({
  classification: cls, label: INTERP_LABEL[cls], strength: "MODERATE", meaning: "Evidence is associated with an industrial facility. This is not a confirmed industrial fire.", scores: {},
  supporting_evidence: [
    { signal: "facility_context", supports: cls, weight: 2, text: "1.4 km from eligible facility" },
    { signal: "persistence", supports: cls, weight: 1, text: "persistent across 8 observations" },
  ],
  contradicting_evidence: [], unavailable_evidence: ["land-use / vegetation cover: no agricultural land-use dataset is configured"],
  alternative_explanations: ["planned thermal process activity", "a mixed 375 m pixel"], disclaimer: "Source interpretation is evidence-based and not a confirmed fire classification.",
  facility_note: "Facility association is spatial context, not source attribution.", ...over,
});

describe("event detail: source interpretation", () => {
  it("shows label, strength, why, alternatives and both disclaimers", () => {
    const h = renderToStaticMarkup(<SourceInterpretationPanel si={si("INDUSTRIAL_SOURCE_CANDIDATE")} />);
    for (const t of ["Source interpretation", "Industrial-source candidate", "moderate evidence", "Why?", "1.4 km from eligible facility", "persistent across 8 observations", "Alternative explanations",
      "a mixed 375 m pixel", "not a confirmed fire classification", "not source attribution", "Unavailable"]) expect(h).toContain(t);
    expect(h).not.toMatch(/Industrial Fire detected|95%|probab/i);
  });
  it("an uncertain interpretation says the evidence is insufficient or conflicting and asserts nothing", () => {
    const h = renderToStaticMarkup(
      <SourceInterpretationPanel si={si("UNCERTAIN", { strength: "UNCERTAIN", supporting_evidence: [], contradicting_evidence: [{ signal: "conflict", text: "industrial-type and agricultural-type evidence are both present" }] })} />,
    );
    expect(h).toContain("evidence insufficient or conflicting");
    expect(h).toContain("No supporting evidence for a specific source interpretation.");
    expect(h).toContain("Against or limiting");
  });
  it("renders nothing when the backend sent no interpretation", () => expect(renderToStaticMarkup(<SourceInterpretationPanel si={null} />)).toBe(""));
  it("repeating labels never produce React duplicate-key warnings (index-qualified keys)", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    renderToStaticMarkup(
      <SourceInterpretationPanel
        si={si("INDUSTRIAL_SOURCE_CANDIDATE", {
          supporting_evidence: [{ signal: "s", supports: "x", weight: 1, text: "Unnamed industrial" }, { signal: "s", supports: "x", weight: 1, text: "Unnamed industrial" }],
          alternative_explanations: ["Unnamed industrial", "Unnamed industrial"], unavailable_evidence: ["Unnamed industrial", "Unnamed industrial"],
        })}
      />,
    );
    renderToStaticMarkup(<div>{[ev("UNCERTAIN"), ev("UNCERTAIN")].map((e, i) => <EventCard key={`${e.event_id}-${i}`} event={e} />)}</div>);
    expect(spy.mock.calls.filter((c) => String(c[0]).includes("same key"))).toEqual([]);
  });
});

const twin = (over: Record<string, unknown>): ThermalTwin =>
  ({
    facility_id: "F1", baseline_confidence: "ESTABLISHED", history_start: "2026-04-01T00:00:00", history_end: "2026-08-06T00:00:00", historical_event_count: 14, historical_observation_count: 52,
    normal_frp: { n: 14, median: 18.4, q25: 10, q75: 25 }, normal_bt: { n: 14, median: 330, q25: 320, q75: 340 }, normal_persistence: { n: 14, median: 3.7, q25: 2, q75: 5 },
    normal_duration: { n: 14, median: 2, q25: 1, q75: 3 }, normal_recurrence_days: 9, ...over,
  }) as unknown as ThermalTwin;

describe("Thermal Twin history display", () => {
  it("established: history, span, typical FRP and persistence", () => {
    const h = renderToStaticMarkup(<TwinHistorySummary twin={twin({})} />);
    for (const t of ["14 events", "127 days", "18.4 MW", "3.7 obs"]) expect(h).toContain(t);
  });
  it("limited: shown with its real (smaller) values", () => {
    expect(renderToStaticMarkup(<TwinHistorySummary twin={twin({ baseline_confidence: "LIMITED", historical_event_count: 2 })} />)).toContain("2 events");
  });
  it("insufficient: dashes, never fake zeros", () => {
    const h = renderToStaticMarkup(
      <TwinHistorySummary twin={twin({ baseline_confidence: "INSUFFICIENT", historical_event_count: 0, history_start: null, history_end: null,
        normal_frp: { n: 0, median: null, q25: null, q75: null }, normal_persistence: { n: 0, median: null, q25: null, q75: null } })} />,
    );
    expect(h).toContain("0 events");
    expect((h.match(/—/g) ?? []).length).toBe(3);
    expect(h).not.toMatch(/0\.0 MW|0 days/);
  });
  it("history status: unavailable is explicit and blocks nothing; partial reports coverage honestly", () => {
    expect(renderToStaticMarkup(<HistoryStatusNote status={null} />)).toContain("UNAVAILABLE");
    expect(renderToStaticMarkup(<HistoryStatusNote status={{ state: "UNAVAILABLE", message: null } as HistoryStatus} />)).toContain("nothing is estimated");
    const h = renderToStaticMarkup(<HistoryStatusNote status={{ state: "PARTIAL", message: null, covered_days: 143, requested_days: 180, facilities_with_history: 9383 } as HistoryStatus} />);
    for (const t of ["PARTIAL", "143 / 180 days", "never appear as current events"]) expect(h).toContain(t);
  });
});

import { SEVERITY_HEX } from "@/components/MapPanel";
import { SEVERITY_RING, markerStyle } from "@/lib/interpretation";

describe("map encoding: fill = source interpretation, ring = operational priority (independent)", () => {
  const sevs = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
  it("fill depends only on the interpretation; ring colour and thickness depend only on the severity", () => {
    for (const cls of INTERP_ORDER) {
      const fills = new Set(sevs.map((s) => markerStyle(ev(cls, { severity: s })).fill));
      expect(fills.size).toBe(1);                                                             // same fill for every severity
    }
    for (const s of sevs) {
      const rings = new Set(INTERP_ORDER.map((c) => { const m = markerStyle(ev(c, { severity: s })); return `${m.ringColor}|${m.ringPx}`; }));
      expect(rings.size).toBe(1);                                                             // same ring for every interpretation
    }
    expect(new Set(INTERP_ORDER.flatMap((c) => sevs.map((s) => `${markerStyle(ev(c, { severity: s })).fill}|${markerStyle(ev(c, { severity: s })).ringColor}`))).size).toBe(INTERP_ORDER.length * sevs.length);
  });
  it("no colour is shared between the interpretation palette and the priority palette", () => {
    const interp = new Set(INTERP_ORDER.map((c) => INTERP_HEX[c].fill.toLowerCase()));
    for (const s of sevs) expect(interp.has(SEVERITY_RING[s].color.toLowerCase())).toBe(false);
  });
  it("the legend uses the same priority colours as the markers", () => {
    for (const s of sevs) expect(SEVERITY_HEX[s].toLowerCase()).toBe(SEVERITY_RING[s].color.toLowerCase());
  });
  it("priority is visible without colour or letters: strictly heavier rings, and no text in markers", () => {
    expect(SEVERITY_RING.HIGH.px).toBeGreaterThan(SEVERITY_RING.MEDIUM.px);
    expect(SEVERITY_RING.MEDIUM.px).toBeGreaterThan(SEVERITY_RING.LOW.px);
    expect(SEVERITY_RING.HIGH.px).toBeGreaterThanOrEqual(SEVERITY_RING.CRITICAL.px);
    expect(Object.keys(markerStyle(ev("UNCERTAIN")))).not.toContain("letter");
    expect(JSON.stringify(SEVERITY_RING)).not.toMatch(/"letter"/);
  });
  it("the legend keeps the two dimensions in separate labelled sections", () => {
    const h = renderToStaticMarkup(<MapLegend showFirms={false} showDemoObs={false} showIncidents={false} showAdmin={false} />);
    expect(h).toContain('data-testid="legend-interpretation"');
    expect(h).toContain('data-testid="legend-priority"');
    expect(h).toContain('data-testid="legend-context"');
    expect(h).toMatch(/Thermal source[\s\S]*Operational priority[\s\S]*Context/);
  });
  it("the popup links to the investigation and the tooltip carries no HTML", () => {
    expect(popupHtml(ev("INDUSTRIAL_SOURCE_CANDIDATE"))).toContain('href="/investigation/EVT-1"');
    expect(tooltipText(ev("INDUSTRIAL_SOURCE_CANDIDATE"))).not.toContain("<");
  });
});


import { declutter } from "@/lib/declutter";
import { INTERP_HEX as HEX } from "@/lib/interpretation";

describe("visual model: exact channels", () => {
  it("every marker sample class follows the agreed industrial palette: terracotta / olive / dark terracotta-brown / neutral silver / pale neutral fills", () => {
    const rgb = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
    const [ir, ig, ib] = rgb(HEX.INDUSTRIAL_SOURCE_CANDIDATE.fill);
    expect(ir).toBeGreaterThan(ig); expect(ig).toBeGreaterThan(ib);                         // terracotta (warm orange-brown)
    const [ar, ag, ab] = rgb(HEX.AGRICULTURAL_VEGETATION_CANDIDATE.fill);
    expect(ag).toBeGreaterThan(ar); expect(ag).toBeGreaterThan(ab);                         // olive green
    const [tr, tg, tb] = rgb(HEX.PERSISTENT_THERMAL_SOURCE_CANDIDATE.fill);
    expect(tr).toBeGreaterThan(tg); expect(tg).toBeGreaterThan(tb);                         // dark terracotta-brown -- same family as industrial, but darker/more muted
    expect(tr).toBeLessThan(ir);                                                            // distinctly darker than industrial, so the two never read as identical
    const [nr, ng, nb] = rgb(HEX.NATURAL_OTHER_THERMAL_SOURCE_CANDIDATE.fill);
    const naturalSpread = Math.max(nr, ng, nb) - Math.min(nr, ng, nb);
    expect(naturalSpread).toBeLessThan(20);                                                 // neutral silver-grey (low colour saturation)
    const [ur, ug, ub] = rgb(HEX.UNCERTAIN.fill);
    expect(Math.min(ur, ug, ub)).toBeGreaterThan(150);                                      // the lightest, most desaturated fill of the five
    expect(Math.min(ur, ug, ub)).toBeGreaterThan(Math.min(nr, ng, nb));                      // uncertain reads lighter than natural/other, not just different
  });
  it("rings: LOW muted olive and thin, MEDIUM desert-bronze and medium, HIGH/CRITICAL terracotta/red and thickest", () => {
    expect(SEVERITY_RING.LOW.color).toBe("#5C5F49");
    expect(SEVERITY_RING.MEDIUM.color).toBe("#B69A6A");
    expect(SEVERITY_RING.HIGH.px).toBeGreaterThan(SEVERITY_RING.MEDIUM.px);
    expect(SEVERITY_RING.MEDIUM.px).toBeGreaterThan(SEVERITY_RING.LOW.px);
    expect(SEVERITY_RING.LOW.px).toBeLessThanOrEqual(2);
    expect(SEVERITY_RING.HIGH.px).toBeLessThanOrEqual(3);
    for (const k of ["LOW", "MEDIUM", "HIGH", "CRITICAL"]) { expect(SEVERITY_RING[k].radius * 2).toBeGreaterThanOrEqual(7); expect(SEVERITY_RING[k].radius * 2).toBeLessThanOrEqual(10); }
  });
  it("examples: Industrial+High, Persistent+Medium, Uncertain+Low", () => {
    const a = markerStyle(ev("INDUSTRIAL_SOURCE_CANDIDATE", { severity: "HIGH" }));
    const b = markerStyle(ev("PERSISTENT_THERMAL_SOURCE_CANDIDATE", { severity: "MEDIUM" }));
    const c = markerStyle(ev("UNCERTAIN", { severity: "LOW" }));
    expect([a.fill, a.ringColor]).toEqual(["#A9573C", "#C5775D"]);
    expect(a.fill).not.toBe(a.ringColor);                                                   // fill and ring must stay visibly distinct even within the same colour family
    expect([b.fill, b.ringColor]).toEqual(["#7C402C", "#B69A6A"]);
    expect([c.fill, c.ringColor, c.ringPx]).toEqual(["#C9C2B0", "#5C5F49", 1.5]);
  });
});

describe("decluttering (no wall of identical circles)", () => {
  const proj = (lng: number, lat: number) => ({ x: lng * 10, y: lat * 10 });
  const items = [
    { id: "LOW-A", lng: 1.00, lat: 1.00, rank: 0, tie: 5 }, { id: "HIGH-B", lng: 1.02, lat: 1.02, rank: 2, tie: 40 },
    { id: "MED-C", lng: 1.03, lat: 1.01, rank: 1, tie: 30 }, { id: "FAR-D", lng: 20, lat: 20, rank: 0, tie: 1 },
  ];
  it("one representative per screen cell: the highest priority wins and the rest are counted", () => {
    const out = declutter(items, proj, 4);
    expect(out.map((o) => o.id).sort()).toEqual(["FAR-D", "HIGH-B"]);
    expect(out.find((o) => o.id === "HIGH-B")?.more).toBe(2);
    expect(out.find((o) => o.id === "FAR-D")?.more).toBe(0);
  });
  it("is deterministic regardless of input order and never drops an event when zoomed in", () => {
    expect(declutter([...items].reverse(), proj, 4)).toEqual(expect.arrayContaining(declutter(items, proj, 4)));
    expect(declutter(items, proj, 9).map((o) => o.id).sort()).toEqual(items.map((i) => i.id).sort());
    expect(declutter(items, proj, 9).every((o) => o.more === 0)).toBe(true);
  });
  it("total events are conserved: shown + hidden = all", () => {
    const out = declutter(items, proj, 4);
    expect(out.reduce((n, o) => n + 1 + o.more, 0)).toBe(items.length);
  });
});
