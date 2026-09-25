import { describe, expect, it } from "vitest";
import { classificationLabel, facilityTypeLabel, fmtNum } from "./format";

describe("format helpers", () => {
  it("never fabricates a number for missing values", () => {
    expect(fmtNum(null)).toBe("--");
    expect(fmtNum(undefined)).toBe("--");
    expect(fmtNum(Number.NaN)).toBe("--");
    expect(fmtNum(3.14159, 2)).toBe("3.14");
  });

  it("labels the two development classes without inventing a third", () => {
    expect(classificationLabel("PERSISTENT_INDUSTRIAL_THERMAL_SOURCE")).toBe("Persistent Industrial-Source Candidate");
    expect(classificationLabel("NATURAL_AGRICULTURAL_FIRE_CANDIDATE")).toBe("Natural/Agricultural Candidate");
    expect(classificationLabel(null)).toBe("No class (no usable facility)");
  });

  it("formats facility types", () => {
    expect(facilityTypeLabel("oil_refinery")).toBe("Oil Refinery");
  });
});
