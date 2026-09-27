import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { getMapStyle, MapKey, MapPanel } from "@/components/MapPanel";
import { declutter } from "@/lib/declutter";
import { INTERP_HEX, INTERP_LABEL, SEVERITY_RING, markerStyle } from "@/lib/interpretation";
import { DEFAULT_MAP_FOCUS, displayPriority, eventsForFocus, isActionable, isUncertain, MAP_FOCUS_ORDER } from "@/lib/mapFocus";
import type { SourceInterpretationClass, ThermalEvent } from "@/types/domain";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => undefined }) }));

const ev = (id: string, cls: SourceInterpretationClass, severity: string, over: Record<string, unknown> = {}) =>
  ({
    event_id: id, severity, risk_score: 20, observation_count: 1, baseline_confidence: null, overall_deviation_score: null, centroid_lat: 20, centroid_lon: 75,
    source_interpretation: { classification: cls, label: INTERP_LABEL[cls], strength: cls === "UNCERTAIN" ? "UNCERTAIN" : "MODERATE" }, ...over,
  }) as unknown as ThermalEvent;

const SET = [
  ev("IND-LOW", "INDUSTRIAL_SOURCE_CANDIDATE", "LOW"), ev("PER-MED", "PERSISTENT_THERMAL_SOURCE_CANDIDATE", "MEDIUM"),
  ev("UNC-HIGH", "UNCERTAIN", "HIGH"), ev("UNC-MED", "UNCERTAIN", "MEDIUM"), ev("UNC-LOW", "UNCERTAIN", "LOW"), ev("UNC-LOW2", "UNCERTAIN", "LOW"),
  ev("UNC-LOW-4OBS", "UNCERTAIN", "LOW", { observation_count: 5 }),
  ev("UNC-LOW-DEV", "UNCERTAIN", "LOW", { baseline_confidence: "ESTABLISHED", overall_deviation_score: 60 }),
  ev("UNC-LOW-DEV-INSUF", "UNCERTAIN", "LOW", { baseline_confidence: "INSUFFICIENT", overall_deviation_score: 0 }),
];
const ids = (l: ThermalEvent[]) => l.map((e) => e.event_id);

describe("map focus", () => {
  it("1. Actionable is the default focus, and the control renders it as the pressed option", () => {
    expect(DEFAULT_MAP_FOCUS).toBe("ACTIONABLE");
    expect(MAP_FOCUS_ORDER).toEqual(["ACTIONABLE", "ALL", "UNCERTAIN"]);
    const h = renderToStaticMarkup(<MapPanel events={SET} focusControl />);
    expect(h).toMatch(/aria-pressed="true"[^>]*data-focus="ACTIONABLE"|data-focus="ACTIONABLE"[^>]*aria-pressed="true"/);
    expect(h).toMatch(/aria-pressed="false"[^>]*data-focus="ALL"|data-focus="ALL"[^>]*aria-pressed="false"/);
    for (const t of ["Actionable", "All events", "Uncertain"]) expect(h).toContain(t);
  });
  it("Actionable = interpreted candidates + MEDIUM/HIGH/CRITICAL + uncertain events with meaningful evidence; faint background stays out", () => {
    expect(ids(eventsForFocus(SET, "ACTIONABLE")).sort()).toEqual(["IND-LOW", "PER-MED", "UNC-HIGH", "UNC-LOW-4OBS", "UNC-LOW-DEV", "UNC-MED"].sort());
    expect(isActionable(SET[4])).toBe(false);
    expect(isActionable(SET[8])).toBe(false);
  });
  it("2. All events displays every event, including uncertain ones", () => {
    expect(ids(eventsForFocus(SET, "ALL"))).toEqual(ids(SET));
  });
  it("3. Uncertain shows only uncertain events", () => {
    const u = eventsForFocus(SET, "UNCERTAIN");
    expect(u.length).toBe(SET.filter(isUncertain).length);
    expect(u.every(isUncertain)).toBe(true);
    expect(ids(u)).not.toContain("IND-LOW");
  });
  it("7. switching mode never mutates the events (frozen input, same objects, same counts)", () => {
    const frozen = SET.map((e) => Object.freeze({ ...e }));
    const before = JSON.stringify(frozen);
    for (const f of MAP_FOCUS_ORDER) eventsForFocus(frozen, f);
    expect(JSON.stringify(frozen)).toBe(before);
    expect(eventsForFocus(frozen, "ALL")[0]).toBe(frozen[0]);
    expect(eventsForFocus(frozen, "ALL")).not.toBe(frozen);
    expect(frozen.length).toBe(SET.length);
  });
});

describe("uncertain styling", () => {
  it("4. uncertain LOW is a faint neutral dot: tiny, ~22% opacity at India-wide zoom, no ring, no colour", () => {
    expect(markerStyle(SET[4]).faint).toBe(true);
    const layer = getMapStyle().layers.find((l) => l.id === "event-faint") as unknown as { paint: Record<string, unknown> };
    expect(layer).toBeDefined();
    const opacity = layer.paint["circle-opacity"] as unknown[];
    expect(opacity.slice(0, 5)).toEqual(["interpolate", ["linear"], ["zoom"], 3, 0.22]);
    expect(opacity[opacity.length - 1] as number).toBeGreaterThan(0.6);
    const radius = layer.paint["circle-radius"] as unknown[];
    expect(radius[4]).toBeLessThanOrEqual(1.5);
    expect(layer.paint["circle-stroke-width"]).toBeUndefined();
    expect(layer.paint["circle-color"]).toBe("#A8A28C");
  });
  it("uncertain LOW faint dots are still clickable event layers, drawn below interpreted/priority events", () => {
    const l = getMapStyle().layers.map((x) => x.id);
    expect(l).toContain("event-faint");
    expect(l.indexOf("obs-circles")).toBeLessThan(l.indexOf("event-faint"));
    expect(l.indexOf("event-faint")).toBeLessThan(l.indexOf("event-circles"));
  });
  it("5. uncertain HIGH / MEDIUM keep their priority rings around a neutral centre (not faint)", () => {
    const h = markerStyle(SET[2]);
    const m = markerStyle(SET[3]);
    expect([h.faint, h.fill, h.ringColor, h.ringPx, h.radius]).toEqual([false, INTERP_HEX.UNCERTAIN.fill, SEVERITY_RING.HIGH.color, SEVERITY_RING.HIGH.px, SEVERITY_RING.HIGH.radius]);
    expect([m.faint, m.fill, m.ringColor, m.ringPx, m.radius]).toEqual([false, INTERP_HEX.UNCERTAIN.fill, SEVERITY_RING.MEDIUM.color, SEVERITY_RING.MEDIUM.px, SEVERITY_RING.MEDIUM.radius]);
  });
  it("9/10. fill still comes only from the interpretation and ring only from the priority (interpreted events unchanged)", () => {
    const a = markerStyle(ev("a", "INDUSTRIAL_SOURCE_CANDIDATE", "HIGH"));
    const b = markerStyle(ev("b", "INDUSTRIAL_SOURCE_CANDIDATE", "LOW"));
    const c = markerStyle(ev("c", "PERSISTENT_THERMAL_SOURCE_CANDIDATE", "HIGH"));
    expect(a.fill).toBe(b.fill);
    expect(a.ringColor).toBe(c.ringColor);
    expect(a.fill).not.toBe(c.fill);
    expect(b.faint).toBe(false);
    expect(b.ringColor).toBe("#5C5F49");
  });
  it("8. no marker contains letters: no text layer, no letter in the marker style", () => {
    expect(JSON.stringify(getMapStyle().layers)).not.toMatch(/text-field|symbol-letter/);
    expect(Object.keys(markerStyle(SET[0]))).not.toContain("letter");
  });
});

describe("decluttering prefers meaningful events", () => {
  const proj = (lng: number, lat: number) => ({ x: lng, y: lat });
  const pick = (events: ThermalEvent[]) => declutter(events.map((e) => ({ id: e.event_id, lng: 1, lat: 1, rank: displayPriority(e), tie: e.risk_score || 0 })), proj, 4)[0];
  it("6. priority order: HIGH/CRITICAL > MEDIUM > interpreted > interpreted-low-evidence > uncertain", () => {
    const weak = ev("IND-WEAK", "INDUSTRIAL_SOURCE_CANDIDATE", "LOW", { source_interpretation: { classification: "INDUSTRIAL_SOURCE_CANDIDATE", label: "x", strength: "LOW" } });
    expect(displayPriority(SET[2])).toBeGreaterThan(displayPriority(SET[1]));
    expect(displayPriority(SET[1])).toBeGreaterThan(displayPriority(SET[0]));
    expect(displayPriority(SET[0])).toBeGreaterThan(displayPriority(weak));
    expect(displayPriority(weak)).toBeGreaterThan(displayPriority(SET[4]));
  });
  it("a crowd of uncertain events never crowds out an interpreted event, and uncertain HIGH still beats interpreted LOW", () => {
    const crowd = Array.from({ length: 200 }, (_, i) => ev(`U${i}`, "UNCERTAIN", "LOW", { risk_score: 1 + (i % 30) }));
    expect(pick([...crowd, SET[0]]).id).toBe("IND-LOW");
    expect(pick([SET[0], SET[2]]).id).toBe("UNC-HIGH");
    expect(pick([SET[2], SET[1]]).id).toBe("UNC-HIGH");
    expect(pick([SET[1], SET[3]]).id).toBe("PER-MED");
  });
  it("equal priority: the higher-risk event wins", () => {
    const a = ev("A", "INDUSTRIAL_SOURCE_CANDIDATE", "LOW", { risk_score: 10 });
    const b = ev("B", "INDUSTRIAL_SOURCE_CANDIDATE", "LOW", { risk_score: 25 });
    expect(pick([a, b]).id).toBe("B");
  });
  it("zooming in progressively reveals more events; the event totals are conserved", () => {
    const spread = Array.from({ length: 300 }, (_, i) => ({ id: `E${i}`, lng: (i % 20) * 0.5, lat: Math.floor(i / 20) * 0.5, rank: 10, tie: i }));
    const p = (lng: number, lat: number) => ({ x: lng * 4, y: lat * 4 });
    const shown = (z: number) => declutter(spread, p, z).length;
    expect(shown(3)).toBeLessThan(spread.length);
    expect(shown(3)).toBeLessThanOrEqual(shown(6));
    expect(shown(8)).toBe(spread.length);
    expect(declutter(spread, p, 3).reduce((n, o) => n + 1 + o.more, 0)).toBe(spread.length);
  });
});

describe("map key", () => {
  it("states the focus and that uncertain events remain available, without a long paragraph", () => {
    const h = renderToStaticMarkup(<MapKey focus="ACTIONABLE" showFirms showDemoObs={false} showIncidents={false} showAdmin={false} />);
    expect(h).toContain("FOCUS: ACTIONABLE");
    expect(h).toContain("Uncertain events remain available under All Events.");
    expect(renderToStaticMarkup(<MapKey focus="ALL" showFirms showDemoObs={false} showIncidents={false} showAdmin={false} />)).toContain("FOCUS: ALL EVENTS");
    expect(renderToStaticMarkup(<MapKey showFirms showDemoObs={false} showIncidents={false} showAdmin={false} />)).not.toContain("FOCUS:");
  });
  it("uncertain events are only ever called Uncertain (never natural, agricultural, false positive or non-fire)", () => {
    const h = renderToStaticMarkup(<MapKey focus="UNCERTAIN" showFirms showDemoObs={false} showIncidents={false} showAdmin={false} />);
    expect(h).not.toMatch(/false positive|non-fire|natural fire|agricultural fire/i);
  });
});
