import { cn } from "@/lib/cn";
import { fmtNum } from "@/lib/format";
import type { Deviation, DimensionDeviation } from "@/types/domain";

const DIMENSIONS: { key: keyof Deviation; label: string; unit: string }[] = [
  { key: "intensity", label: "FRP (intensity)", unit: "MW" },
  { key: "persistence", label: "Persistence", unit: "obs" },
  { key: "duration", label: "Duration", unit: "h" },
  { key: "temporal", label: "Timing", unit: "" },
  { key: "spatial", label: "Spatial footprint", unit: "km" },
  { key: "recurrence", label: "Recurrence", unit: "d" },
];

function Row({ label, unit, dim }: { label: string; unit: string; dim: DimensionDeviation }) {
  const insufficient = dim.status === "INSUFFICIENT_BASELINE";
  return (
    <tr className="border-t border-base-700/70">
      <td className="py-2 pr-3 text-xs text-base-200">{label}</td>
      <td className="py-2 pr-3 text-right font-mono text-xs text-base-100">
        {insufficient ? "--" : `${fmtNum(dim.observed_value, unit === "obs" ? 0 : 2)} ${unit}`}
      </td>
      <td className="py-2 pr-3 text-right font-mono text-xs text-base-400">
        {insufficient ? "--" : dim.expected_median !== null ? `~${fmtNum(dim.expected_median, unit === "obs" ? 0 : 2)}` : "--"}
      </td>
      <td className="py-2 text-right">
        {insufficient ? (
          <span className="text-[10px] font-semibold uppercase text-base-400">Insufficient baseline</span>
        ) : (
          <span
            className={cn(
              "text-[10px] font-semibold uppercase tracking-wide",
              dim.is_significant ? "text-sev-critical" : dim.is_notable ? "text-sev-medium" : "text-sev-low"
            )}
          >
            {dim.is_significant ? "Significant" : dim.is_notable ? "Notable" : "Normal"}
          </span>
        )}
      </td>
    </tr>
  );
}

export function DeviationTable({ deviation }: { deviation: Deviation }) {
  return (
    <div>
      <table className="w-full">
        <thead>
          <tr className="text-left text-[10px] uppercase tracking-wider text-base-400">
            <th className="pb-2 font-medium">Dimension</th>
            <th className="pb-2 text-right font-medium">Current</th>
            <th className="pb-2 text-right font-medium">Normal</th>
            <th className="pb-2 text-right font-medium">Deviation</th>
          </tr>
        </thead>
        <tbody>
          {DIMENSIONS.map((d) => (
            <Row key={d.key} label={d.label} unit={d.unit} dim={deviation[d.key] as DimensionDeviation} />
          ))}
        </tbody>
      </table>
      <div className="mt-3 space-y-1 border-t border-base-700/70 pt-2.5">
        {deviation.explanations.map((e, i) => (
          <p key={i} className="text-xs leading-relaxed text-base-300">
            {e}
          </p>
        ))}
      </div>
    </div>
  );
}
