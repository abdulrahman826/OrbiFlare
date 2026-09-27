import { describe, expect, it } from "vitest";
import { getMapStyle } from "@/components/MapPanel";

describe("map style", () => {
  it("draws basemap < raw observations < events, with events last (on top)", () => {
    const ids = getMapStyle().layers.map((l) => l.id);
    expect(ids.indexOf("osm-layer")).toBeLessThan(ids.indexOf("obs-circles"));
    expect(ids.indexOf("obs-circles")).toBeLessThan(ids.indexOf("event-circles"));
  });
  it("raw observations are tiny, low-opacity dots without ring; events carry fill and ring from feature data, no text", () => {
    const layers = Object.fromEntries(getMapStyle().layers.map((l) => [l.id, l as unknown as { paint: Record<string, unknown>; layout?: Record<string, unknown> }]));
    expect(layers["obs-circles"].paint["circle-opacity"]).toBeLessThanOrEqual(0.5);
    expect(layers["obs-circles"].paint["circle-stroke-width"]).toBeUndefined();
    expect(layers["event-circles"].paint["circle-color"]).toEqual(["get", "fill"]);
    expect(layers["event-circles"].paint["circle-stroke-color"]).toEqual(["get", "ring"]);
    expect(layers["event-circles"].paint["circle-stroke-width"]).toEqual(["get", "ringPx"]);
    expect(JSON.stringify(getMapStyle().layers)).not.toContain("text-field");                  // no letters in markers
  });
  it("the basemap is desaturated inside the raster layer, so marker colours are never filtered", () => {
    const osm = getMapStyle().layers.find((l) => l.id === "osm-layer") as unknown as { paint: Record<string, number> };
    expect(osm.paint["raster-saturation"]).toBeLessThan(-0.5);
  });
});
