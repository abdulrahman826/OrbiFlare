import { fmtNum } from "@/lib/format";
import type { ThermalTwin } from "@/types/domain";

const DAY = 86_400_000;

/** History / Span / Typical FRP / Persistence. An insufficient baseline shows "—" (never fabricated zeros). */
export function TwinHistorySummary({ twin }: { twin: ThermalTwin }) {
  const est = twin.baseline_confidence !== "INSUFFICIENT" && twin.historical_event_count > 0;
  const span = est && twin.history_start && twin.history_end ? Math.max(0, Math.round((Date.parse(twin.history_end) - Date.parse(twin.history_start)) / DAY)) : null;
  const cells: [string, string][] = [
    ["History", `${twin.historical_event_count} event${twin.historical_event_count === 1 ? "" : "s"}`],
    ["Span", span != null ? `${span} days` : "—"],
    ["Typical FRP", est && twin.normal_frp.n > 0 ? `${fmtNum(twin.normal_frp.median, 1)} MW` : "—"],
    ["Persistence", est && twin.normal_persistence.n > 0 ? `${fmtNum(twin.normal_persistence.median, 1)} obs` : "—"],
  ];
  return (
    <div className="grid grid-cols-2 gap-x-6 gap-y-1 md:grid-cols-4" data-testid="twin-history">
      {cells.map(([k, v]) => (
        <div key={k}>
          <div className="text-[10px] uppercase tracking-wider text-base-400">{k}</div>
          <div className="font-mono text-sm text-base-100">{v}</div>
        </div>
      ))}
    </div>
  );
}
