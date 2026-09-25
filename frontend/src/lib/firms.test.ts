import { describe, expect, it } from "vitest";
import { confidenceCounts, firmsSourceLabel, satelliteName } from "./firms";
import type { ThermalObservation } from "@/types/domain";

const obs = (over: Partial<ThermalObservation>): ThermalObservation => ({
  observation_id: "x", timestamp: "2026-09-24T06:44:00", latitude: 1, longitude: 2, sensor: "VIIRS", brightness_temperature: 300,
  brightness_temperature_11: 290, frp: 3, confidence: "n", day_night: "D", source: "FIRMS", source_id: null, quality_flags: [],
  satellite: "N21", instrument: "VIIRS", scan: 0.4, track: 0.4, source_product: "VIIRS_NOAA21_NRT", is_live_firms: true, ...over,
} as ThermalObservation);

describe("FIRMS presentation helpers", () => {
  it("labels the source from the products actually on the observations", () => {
    expect(firmsSourceLabel([obs({})])).toBe("NASA FIRMS · VIIRS NOAA-21 NRT");
    expect(firmsSourceLabel([obs({}), obs({ source_product: "VIIRS_NOAA20_NRT", satellite: "N20" })])).toBe("NASA FIRMS · VIIRS NOAA-21 NRT + VIIRS NOAA-20 NRT");
  });
  it("never labels synthetic observations as NASA FIRMS", () => {
    expect(firmsSourceLabel([obs({ source: "DEMO", is_live_firms: false })])).toBe("");
  });
  it("NASA confidence is reported as its own attribute", () => {
    expect(confidenceCounts([obs({ confidence: "l" }), obs({ confidence: "n" }), obs({ confidence: "n" })])).toBe("low ×1, nominal ×2");
  });
  it("satellite codes map to names without inventing any", () => {
    expect(satelliteName("N20")).toBe("NOAA-20");
    expect(satelliteName("ZZ")).toBe("ZZ");
    expect(satelliteName(null)).toBe("unknown");
  });
});
