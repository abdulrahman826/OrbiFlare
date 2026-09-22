import { DemoBadge, LiveBadge } from "@/components/DemoBadge";
import { RiskBadge } from "@/components/RiskBadge";
import { TrajectoryBadge } from "@/components/TrajectoryBadge";
import { classificationLabel, fmtDate } from "@/lib/format";
import type { ThermalEvent } from "@/types/domain";

export function InvestigationHeader({ event }: { event: ThermalEvent }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <div className="flex items-center gap-2">
          <h1 className="font-mono text-xl font-semibold text-base-100">{event.event_id}</h1>
          {event.is_demo ? <DemoBadge /> : <LiveBadge />}
          <span className="rounded border border-base-500/50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-base-300">{event.status}</span>
        </div>
        <p className="mt-1 text-sm text-base-300">{classificationLabel(event.classification)}</p>
        <p className="mt-2 text-xs text-base-400">
          {event.centroid_lat.toFixed(4)}, {event.centroid_lon.toFixed(4)} &middot; First detected {fmtDate(event.first_detected)} &middot; Last detected {fmtDate(event.last_detected)}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <TrajectoryBadge direction={event.trajectory_direction} />
        <RiskBadge severity={event.severity} score={event.risk_score} />
      </div>
    </div>
  );
}
