// Scans the user-facing source for misleading or internal wording. Comments and API field identifiers are ignored: this is about
// text a user can read (JSX text, string literals, page metadata).
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SRC = path.resolve(__dirname, "..");

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const p = path.join(dir, n);
    if (statSync(p).isDirectory()) return files(p);
    return /\.(tsx?|css)$/.test(n) && !/\.test\./.test(n) ? [p] : [];
  });
}

function userFacing(p: string): string {
  return readFileSync(p, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .split(/\r?\n/)
    .map((l) => l.replace(/(^|\s)\/\/.*$/, ""))
    .join("\n")
    .replace(/synthetic_(observations|events)/g, ""); // API field identifiers, never rendered
}

const ALL = files(SRC).map((p) => ({ p: path.relative(SRC, p).replace(/\\/g, "/"), text: userFacing(p) }));
const hits = (re: RegExp) => ALL.filter((f) => re.test(f.text)).map((f) => f.p);
const NEGATION = /\b(not|never|no|isn't|does not|cannot)\b|✗/i;

describe("user-facing wording", () => {
  it("never shows internal development-data terminology", () => expect(hits(/synthetic/i)).toEqual([]));
  it("never calls the evaluation a geographic hold-out", () => expect(hits(/geographic[\s_-]*hold-?out/i)).toEqual([]));
  it("never advertises AI fire detection", () => {
    expect(hits(/AI[- ]based detection/i)).toEqual([]);
    expect(hits(/detection and classification of industrial fires/i)).toEqual([]);
  });
  it("has no bare accuracy metric and no accuracy percentage claim", () => {
    expect(hits(/["'>]Accuracy \(/)).toEqual([]);
    expect(hits(/label="Accuracy"/)).toEqual([]);
    expect(hits(/metrics?\.accuracy\s*\*\s*100/)).toEqual([]); // the old "81%" rendering
  });
  it("does not present risk as a probability of fire, a forecast, or facility causation", () => {
    for (const re of [/fire probabilit/i, /will become a fire/i, /predicts? (a |the )?future fires?/i, /facility caused/i, /fire at (the )?facility/i]) {
      const offenders = ALL.filter((f) => f.text.split("\n").some((l) => re.test(l) && !NEGATION.test(l))).map((f) => f.p);
      expect(offenders, String(re)).toEqual([]);
    }
  });
  it("the Model page frames the metric as a development-set evaluation, not real-world accuracy", () => {
    const t = readFileSync(path.join(SRC, "app/model/page.tsx"), "utf8");
    expect(t).toContain("MODEL_EVALUATION_LABEL");
    expect(t).toMatch(/not real-world fire-detection accuracy/);
    expect(t).toMatch(/not an OrbiFlare accuracy figure/);
    expect(t).toContain("ML_ROLE_NOTE");
  });
  it("historical validation is described neutrally (needs archived FIRMS), never as a failure rate", () => {
    const t = readFileSync(path.join(SRC, "app/model/page.tsx"), "utf8");
    expect(t).toMatch(/Historical incident validation requires matching archived FIRMS observations/);
    expect(hits(/\b0\s*\/\s*30\b|0% accuracy/i)).toEqual([]);
  });
});
