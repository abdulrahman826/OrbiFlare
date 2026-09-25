import Link from "next/link";
import { DemoBadge, LiveBadge } from "@/components/DemoBadge";
import { RiskBadge } from "@/components/RiskBadge";
import { TrajectoryBadge } from "@/components/TrajectoryBadge";
import { cn } from "@/lib/cn";
import { classificationLabel, fmtDate, fmtNum } from "@/lib/format";
import type { Severity, ThermalEvent } from "@/types/domain";

export const SEVERITY_EDGE: Record<Severity, string> = {
  CRITICAL: "border-l-sev-critical",
  HIGH: "border-l-sev-high",
  MEDIUM: "border-l-sev-medium",
  LOW: "border-l-sev-low",
};

function Stat({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <span className="whitespace-nowrap text-base-400">
      {k} <b className="font-mono font-medium text-base-100">{v}</b>
    </span>
  );
}

export function deviationLabel(e: ThermalEvent): string {
  if (e.baseline_confidence === "INSUFFICIENT") return "insufficient";
  if (e.baseline_confidence === null) return "no baseline";
  if (e.overall_deviation_score === null) return "n/a";
  return `${fmtNum(e.overall_deviation_score, 0)}/100`;
}

/** Compact priority-alert card: severity, identity, context, evidence stats, drill-down. */
export function EventCard({ event, facilityName, selected }: { event: ThermalEvent; facilityName?: string; selected?: boolean }) {
  return (
    <Link
      href={`/investigation/${event.event_id}`}
      className={cn(
        "group block rounded border border-l-[3px] border-base-600 bg-base-850 p-2.5 transition-colors hover:bg-base-800",
        event.severity ? SEVERITY_EDGE[event.severity] : "border-l-base-500",
        selected && "ring-1 ring-accent"
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <RiskBadge severity={event.severity} score={event.risk_score} size="sm" />
          <span className="truncate font-mono text-xs text-base-100">{event.event_id}</span>
        </div>
        {event.is_demo ? <DemoBadge compact /> : <LiveBadge compact />}
      </div>
      <div className="mt-1.5 text-[11px] text-base-300">
        {classificationLabel(event.classification)}
        <span className="text-base-500"> · </span>
        <span className="font-mono">{fmtDate(event.first_detected)}</span>
      </div>
      <div className="mt-0.5 truncate text-[11px] text-base-400">
        {event.facility_id
          ? `Near ${facilityName ?? event.facility_id}${event.facility_distance_km !== null ? ` · ~${fmtNum(event.facility_distance_km)} km (spatial association)` : ""}`
          : "No facility context"}
        <span className="font-mono"> · {event.centroid_lat.toFixed(3)}°N {event.centroid_lon.toFixed(3)}°E</span>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5 text-[11px]">
        <div className="flex flex-wrap gap-x-3 gap-y-0.5">
          <Stat k="FRP" v={`${fmtNum(event.peak_frp, 0)} MW`} />
          <Stat k="Persist" v={`${event.observation_count}×`} />
          <Stat k="Dur" v={`${fmtNum(event.duration_hours)}h`} />
          <Stat k="Dev" v={deviationLabel(event)} />
        </div>
        <TrajectoryBadge direction={event.trajectory_direction} />
      </div>
      <div className="mt-1.5 flex justify-end"><span className="btn !px-2 !py-1 !text-[10px]">Investigate event →</span></div>
    </Link>
  );
}
