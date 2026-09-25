import Link from "next/link";
import { BaselineStatus } from "@/components/BaselineStatus";
import { fmtDate, fmtNum } from "@/lib/format";
import type { ThermalTwin } from "@/types/domain";

function Cell({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <div className="font-mono text-sm text-base-100">{v}</div>
      <div className="text-[10px] uppercase tracking-wider text-base-400">{k}</div>
    </div>
  );
}

export function ThermalTwinCard({ twin, facilityName, activeEvents = 0, maxDeviation }: { twin: ThermalTwin; facilityName?: string; activeEvents?: number; maxDeviation?: number | null }) {
  const insufficient = twin.baseline_confidence === "INSUFFICIENT";
  return (
    <Link href={`/thermal-twins/${twin.facility_id}`} className="group block rounded border border-base-700 bg-base-850 p-3 transition-colors hover:border-base-500 hover:bg-base-800">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium text-base-100">{facilityName || twin.facility_id}</span>
        <BaselineStatus confidence={twin.baseline_confidence} />
      </div>
      {insufficient ? (
        <p className="mt-3 rounded border border-dashed border-sev-critical/40 px-2 py-2 text-[11px] text-sev-critical">
          Insufficient history ({twin.historical_event_count} events). No normal behaviour is asserted.
        </p>
      ) : (
        <>
        {twin.baseline_confidence === "LIMITED" && <p className="mt-2 text-[11px] text-sev-medium">Limited baseline — insufficient history for strong behavioural inference.</p>}
        <div className="mt-3 grid grid-cols-4 gap-2">
          <Cell k="Normal FRP" v={twin.normal_frp.n ? `${fmtNum(twin.normal_frp.median, 0)} MW` : "—"} />
          <Cell k="Normal dur" v={twin.normal_duration.n ? `${fmtNum(twin.normal_duration.median)} h` : "—"} />
          <Cell k="History" v={`${twin.historical_event_count} ev`} />
          <Cell k="Now dev" v={maxDeviation === null || maxDeviation === undefined ? "—" : `${fmtNum(maxDeviation, 0)}/100`} />
        </div>
        </>
      )}
      <div className="mt-2 flex items-center justify-between text-[11px] text-base-400">
        <span>{twin.history_start ? `${fmtDate(twin.history_start).split(",").slice(0, 2).join(",")} → ${fmtDate(twin.history_end).split(",").slice(0, 2).join(",")}` : "no history"} · {activeEvents} current</span>
        <span className="font-semibold uppercase tracking-wider text-accent group-hover:text-accent-bright">Open →</span>
      </div>
    </Link>
  );
}
