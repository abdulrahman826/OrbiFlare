import Link from "next/link";
import { DemoBadge, LiveBadge } from "@/components/DemoBadge";
import { deviationLabel, SEVERITY_EDGE } from "@/components/EventCard";
import { RiskBadge } from "@/components/RiskBadge";
import { TrajectoryBadge } from "@/components/TrajectoryBadge";
import { cn } from "@/lib/cn";
import { classificationLabel, fmtDate, fmtNum } from "@/lib/format";
import type { ThermalEvent } from "@/types/domain";

const TH = "whitespace-nowrap px-2.5 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-base-400";
const TD = "whitespace-nowrap px-2.5 py-2 text-xs text-base-200";

/** Dense analyst table. Rows are real links so they are keyboard-navigable. */
export function EventTable({ events, facilityNames = {} }: { events: ThermalEvent[]; facilityNames?: Record<string, string> }) {
  return (
    <div className="scrollbar-thin overflow-x-auto">
      <table className="w-full min-w-[900px] border-collapse">
        <thead className="border-b border-base-700 bg-base-900/60">
          <tr>
            <th className={TH}>Severity / Risk</th>
            <th className={TH}>Event</th>
            <th className={TH}>First detected</th>
            <th className={TH}>ML class</th>
            <th className={TH}>Facility context</th>
            <th className={cn(TH, "text-right")}>Peak FRP</th>
            <th className={cn(TH, "text-right")}>Obs</th>
            <th className={cn(TH, "text-right")}>Deviation</th>
            <th className={TH}>Trajectory</th>
            <th className={TH}>Status</th>
            <th className={TH} />
          </tr>
        </thead>
        <tbody>
          {events.map((e) => (
            <tr key={e.event_id} className={cn("border-b border-base-700/50 border-l-[3px] hover:bg-base-800/70", e.severity ? SEVERITY_EDGE[e.severity] : "border-l-base-500")}>
              <td className={TD}><RiskBadge severity={e.severity} score={e.risk_score} size="sm" /></td>
              <td className={cn(TD, "font-mono text-base-100")}>{e.event_id} <span className="ml-1 align-middle">{e.is_demo ? <DemoBadge compact /> : <LiveBadge compact />}</span></td>
              <td className={cn(TD, "font-mono")}>{fmtDate(e.first_detected)}</td>
              <td className={TD}>{classificationLabel(e.classification)}{e.ml_anomaly_low_confidence && <span className="ml-1 text-sev-medium">(low conf.)</span>}</td>
              <td className={TD}>
                {e.facility_id ? (
                  <>{facilityNames[e.facility_id] ?? e.facility_id}<span className="text-base-400"> · {fmtNum(e.facility_distance_km)} km</span></>
                ) : <span className="text-base-400">none</span>}
              </td>
              <td className={cn(TD, "text-right font-mono")}>{fmtNum(e.peak_frp, 0)} MW</td>
              <td className={cn(TD, "text-right font-mono")}>{e.observation_count}</td>
              <td className={cn(TD, "text-right font-mono")}>{deviationLabel(e)}</td>
              <td className={TD}><TrajectoryBadge direction={e.trajectory_direction} /></td>
              <td className={cn(TD, "font-mono text-[11px]")}>{e.status}</td>
              <td className={TD}>
                <Link href={`/investigation/${e.event_id}`} className="link-action">
                  Investigate →
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
