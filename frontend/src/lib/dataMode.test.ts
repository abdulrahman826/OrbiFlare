import { describe, expect, it } from "vitest";
import { DATA_MODE_UI } from "./format";

describe("data mode presentation", () => {
  it("only LIVE_FIRMS is presented as live", () => {
    expect(DATA_MODE_UI.LIVE_FIRMS.top).toContain("LIVE");
    for (const k of ["DEMO", "MIXED", "EMPTY"]) expect(DATA_MODE_UI[k].top).not.toMatch(/^FIRMS LIVE/);
  });
  it("demo is explicitly labelled as demo data", () => {
    expect(DATA_MODE_UI.DEMO.short).toMatch(/DEMO/);
    expect(DATA_MODE_UI.DEMO.sensor).toMatch(/demo/);
  });
});
