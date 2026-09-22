import Link from "next/link";
import { DemoBadge, LiveBadge } from "@/components/DemoBadge";
import { RiskBadge } from "@/components/RiskBadge";
import { TrajectoryBadge } from "@/components/TrajectoryBadge";
import { classificationLabel, fmtDate, fmtNum } from "@/lib/format";
import type { ThermalEvent } from "@/types/domain";

export function EventCard({ event }: { event: ThermalEvent }) {
  return (
    <Link
      href={`/investigation/${event.event_id}`}
      className="block rounded-md border border-base-700 bg-base-850 p-3 transition-colors hover:border-accent/50 hover:bg-base-800"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm text-base-100">{event.event_id}</span>
            {event.is_demo ? <DemoBadge compact /> : <LiveBadge compact />}
          </div>
          <div className="mt-0.5 text-xs text-base-400">
            {classificationLabel(event.classification)} &middot; {fmtDate(event.first_detected)}
          </div>
        </div>
        <RiskBadge severity={event.severity} score={event.risk_score} size="sm" />
      </div>
      <div className="mt-2.5 flex items-center justify-between">
        <div className="flex gap-3 text-[11px] text-base-300">
          <span>FRP <b className="text-base-100">{fmtNum(event.peak_frp, 0)}</b> MW</span>
          <span>Dur <b className="text-base-100">{fmtNum(event.duration_hours)}</b>h</span>
          <span>Obs <b className="text-base-100">{event.observation_count}</b></span>
        </div>
        <TrajectoryBadge direction={event.trajectory_direction} />
      </div>
      {event.facility_id && (
        <div className="mt-2 text-[11px] text-base-400">
          {event.facility_distance_km !== null && `Facility context: ~${fmtNum(event.facility_distance_km)} km away`}
        </div>
      )}
    </Link>
  );
}
