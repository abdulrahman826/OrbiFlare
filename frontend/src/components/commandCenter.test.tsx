import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AgentPanel } from "@/components/AgentPanel";
import { EventCard } from "@/components/EventCard";
import type { ThermalEvent } from "@/types/domain";

const ev = (over: Partial<ThermalEvent> = {}) => ({
  event_id: "EVT-1", first_detected: "2026-09-20T06:00:00", severity: "LOW", risk_score: 20, classification: "PERSISTENT_INDUSTRIAL_THERMAL_SOURCE", is_demo: false,
  facility_id: "F1", facility_distance_km: 0.4, centroid_lat: 21, centroid_lon: 72, peak_frp: 5, observation_count: 3, duration_hours: 1, trajectory_direction: "STABLE",
  baseline_confidence: null, overall_deviation_score: null, ...over,
}) as unknown as ThermalEvent;

describe("command center wording and ML evidence", () => {
  it("class A is a candidate label, never confirmed", () => {
    const h = renderToStaticMarkup(<EventCard event={ev()} />);
    expect(h).toContain("Persistent Industrial-Source Candidate");
    expect(h).toContain("ML evidence");
    expect(h).toContain("Class A");
    expect(h).not.toMatch(/Confirmed|Industrial Fire|Persistent Industrial Source/);
  });
  it("class B and unassessed events are shown without inventing values", () => {
    expect(renderToStaticMarkup(<EventCard event={ev({ classification: "NATURAL_AGRICULTURAL_FIRE_CANDIDATE" })} />)).toContain("Class B candidate");
    expect(renderToStaticMarkup(<EventCard event={ev({ classification: null })} />)).toContain("not assessed (no usable facility)");
  });
  it("the embedded console renders idle (no request until the user sends a query) with the compact placeholder", () => {
    const h = renderToStaticMarkup(<AgentPanel suggestions={["show escalating events"]} compact />);
    expect(h).toContain("Ask about events, facilities, risk or thermal behaviour…");
    expect(h).toContain("show escalating events");
    expect(h).toContain("No queries run yet");
  });
});
