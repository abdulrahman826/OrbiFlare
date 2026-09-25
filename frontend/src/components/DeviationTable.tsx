import { deviationBadge } from "@/lib/assessment";
import { cn } from "@/lib/cn";
import { fmtNum } from "@/lib/format";
import type { BaselineConfidence, Deviation, DimensionDeviation } from "@/types/domain";

const DIMENSIONS: { key: keyof Deviation; label: string; unit: string }[] = [
  { key: "intensity", label: "Intensity (FRP)", unit: "MW" },
  { key: "persistence", label: "Persistence", unit: "obs" },
  { key: "duration", label: "Duration", unit: "h" },
  { key: "temporal", label: "Temporal", unit: "" },
  { key: "spatial", label: "Spatial footprint", unit: "km" },
  { key: "recurrence", label: "Recurrence", unit: "d" },
];

const BADGE_TONE: Record<string, string> = {
  significant: "border-sev-critical/40 bg-sev-critical/10 text-sev-critical",
  notable: "border-sev-medium/40 bg-sev-medium/10 text-sev-medium",
  normal: "border-sev-low/40 bg-sev-low/10 text-sev-low",
  // LIMITED history: dashed and muted, so it never reads as an established-baseline deviation
  "limited-significant": "border-dashed border-base-400 bg-base-800 text-base-200",
  "limited-notable": "border-dashed border-base-500 bg-base-800 text-base-300",
};

function Row({ label, unit, dim, baseline }: { label: string; unit: string; dim: DimensionDeviation; baseline: BaselineConfidence | null | undefined }) {
  const insufficient = dim.status === "INSUFFICIENT_BASELINE";
  const digits = unit === "obs" ? 0 : 2;
  const z = dim.robust_z;
  return (
    <tr className="border-t border-base-700/60 align-top">
      <td className="py-2 pr-3 text-xs font-medium text-base-100">{label}</td>
      <td className="py-2 pr-3 text-right font-mono text-xs text-base-400">
        {insufficient ? "—" : dim.expected_median !== null ? `${fmtNum(dim.expected_median, digits)} ${unit}` : "—"}
        {!insufficient && dim.expected_range && <div className="text-[10px] text-base-500">{fmtNum(dim.expected_range[0], digits)}–{fmtNum(dim.expected_range[1], digits)}</div>}
      </td>
      <td className="py-2 pr-3 text-right font-mono text-xs text-base-100">{insufficient ? "—" : `${fmtNum(dim.observed_value, digits)} ${unit}`}</td>
      <td className="py-2 pr-3 text-right font-mono text-xs text-base-300">{insufficient || z === null ? "—" : `${z >= 0 ? "+" : ""}${z.toFixed(1)}σ`}</td>
      <td className="py-2 pr-3">
        {insufficient ? (
          <span className="rounded border border-base-600 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-base-400">Insufficient baseline</span>
        ) : (
          <span className={cn("inline-block rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide", BADGE_TONE[deviationBadge(dim, baseline).tone])} data-testid="deviation-badge">
            {deviationBadge(dim, baseline).text}
          </span>
        )}
      </td>
      <td className="hidden py-2 text-[11px] leading-snug text-base-400 lg:table-cell">{dim.explanation}</td>
    </tr>
  );
}

export function DeviationTable({ deviation }: { deviation: Deviation }) {
  const insufficient = deviation.baseline_confidence === "INSUFFICIENT";
  const limited = deviation.baseline_confidence === "LIMITED";
  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3 rounded border border-base-700 bg-base-800/50 px-3 py-2">
        <span className="text-[11px] uppercase tracking-wider text-base-400">Overall deviation from this facility&apos;s normal{limited ? " — LIMITED HISTORY" : ""}</span>
        {insufficient ? (
          <span className="font-mono text-sm text-sev-medium">INSUFFICIENT BASELINE</span>
        ) : (
          <span className="flex items-center gap-2">
            <span className="h-1.5 w-28 overflow-hidden rounded bg-base-700"><span className="block h-full bg-accent" style={{ width: `${Math.min(100, deviation.overall_deviation_score)}%` }} /></span>
            <span className="font-mono text-sm text-base-100">{fmtNum(deviation.overall_deviation_score, 0)}<span className="text-base-400">/100</span></span>
          </span>
        )}
      </div>
      <table className="w-full">
        <thead>
          <tr className="text-left text-[10px] uppercase tracking-wider text-base-400">
            <th className="pb-1.5 font-medium">Dimension</th>
            <th className="pb-1.5 pr-3 text-right font-medium">Normal</th>
            <th className="pb-1.5 pr-3 text-right font-medium">Current</th>
            <th className="pb-1.5 pr-3 text-right font-medium">z</th>
            <th className="pb-1.5 font-medium">Deviation</th>
            <th className="hidden pb-1.5 font-medium lg:table-cell">Why</th>
          </tr>
        </thead>
        <tbody>
          {DIMENSIONS.map((d) => <Row key={d.key} label={d.label} unit={d.unit} dim={deviation[d.key] as DimensionDeviation} baseline={deviation.baseline_confidence} />)}
        </tbody>
      </table>
      <p className="mt-2 border-t border-base-700/60 pt-2 text-[11px] text-base-400">
        Deviation says the behaviour is <b className="text-base-200">unusual for this facility</b>. It does not say what caused it — that is what evidence and alternative explanations address.
        {limited && <> Compared with a <b className="text-base-200">limited</b> history, so it counts only partially toward risk and is not strong evidence of an anomaly.</>}
      </p>
    </div>
  );
}
