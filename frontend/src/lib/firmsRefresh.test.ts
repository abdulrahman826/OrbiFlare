import { describe, expect, it } from "vitest";
import { failedUi, formatAcquisition, formatIst, idleUi, okUi, RUNNING_UI } from "./firmsRefresh";
import type { FirmsRefreshSummary } from "@/types/domain";

const summary: FirmsRefreshSummary = {
  status: "OK", synced_at: "2026-09-24T16:19:00Z",
  sources: [{ product: "VIIRS_NOAA21_NRT", satellites: ["N21"], received: 142, rejected: 0 }],
  satellites: ["N21"], observations_received: 142, observations_stored: 142, new_observations: 21, updated_observations: 0,
  rejected_rows: 0, events_total: 90, events_created: 12, events_updated: 3, events_unchanged: 75,
  first_acquisition: "2026-09-23T08:00:00Z", last_acquisition: "2026-09-24T09:24:00Z",
  demo_data_removed: { events: 0, facilities: 0, observations: 0 }, note: "",
};

describe("FIRMS refresh control state", () => {
  it("idle: enabled when configured, disabled and honest when not", () => {
    expect(idleUi(true)).toMatchObject({ state: "idle", buttonDisabled: false });
    const u = idleUi(false);
    expect(u).toMatchObject({ state: "unconfigured", buttonDisabled: true, title: "FIRMS NOT CONFIGURED" });
    expect(u.lines.join(" ")).toMatch(/demo/i);
  });
  it("running: button is disabled and says Refreshing…", () => {
    expect(RUNNING_UI).toMatchObject({ state: "running", buttonDisabled: true, buttonLabel: "Refreshing…" });
  });
  it("success: shows exactly the numbers returned by the API", () => {
    const u = okUi(summary);
    expect(u.title).toBe("FIRMS SYNC COMPLETE");
    expect(u.lines).toEqual([
      "142 observations received",
      "142 observations stored (21 new)",
      "12 events created · 3 updated · 90 total",
      "Source: VIIRS NOAA-21 NRT",
    ]);
    expect(u.buttonDisabled).toBe(false);
  });
  it("success with zero rows says so instead of implying data", () => {
    expect(okUi({ ...summary, observations_received: 0, new_observations: 0 }).lines).toContain("No detections in the requested window");
  });
  it("reports demo data removal only when it happened", () => {
    expect(okUi(summary).lines.join(" ")).not.toMatch(/demo data removed/i);
    expect(okUi({ ...summary, demo_data_removed: { events: 64, facilities: 4, observations: 184 } }).lines).toContain("Demo data removed (64 events)");
  });
  it("two products are both named as the source", () => {
    const two = { ...summary, sources: [summary.sources[0], { product: "VIIRS_NOAA20_NRT", satellites: ["N20"], received: 5, rejected: 0 }] };
    expect(okUi(two).lines.at(-1)).toBe("Source: VIIRS NOAA-21 NRT + VIIRS NOAA-20 NRT");
  });
  it("failure: short real error, keeps last data, no stack traces", () => {
    const u = failedUi({ status: "FAILED", code: "TIMEOUT", message: "NASA FIRMS did not respond in time.", showing: "last available data" });
    expect(u).toMatchObject({ state: "failed", title: "FIRMS SYNC FAILED", buttonDisabled: false });
    expect(u.lines).toEqual(["NASA FIRMS did not respond in time.", "Showing last available data"]);
  });
  it("failure with no body (API unreachable) is still clean", () => {
    expect(failedUi(null).lines[0]).toMatch(/could not be reached/);
  });
  it("missing key is presented as NOT CONFIGURED, not as a failure", () => {
    expect(failedUi({ status: "FAILED", code: "NOT_CONFIGURED", message: "x", showing: "" })).toMatchObject({ state: "unconfigured", title: "FIRMS NOT CONFIGURED" });
  });
});

describe("time formatting keeps sync time and acquisition time separate", () => {
  it("formats sync time in IST", () => expect(formatIst("2026-09-24T16:19:00Z")).toBe("21:49 IST"));
  it("never / invalid", () => { expect(formatIst(null)).toBe("never"); expect(formatIst("garbage")).toBe("—"); });
  it("acquisition is shown as stored UTC, not converted", () => expect(formatAcquisition("2026-09-24T09:24:00Z")).toBe("2026-09-24 09:24Z"));
});
