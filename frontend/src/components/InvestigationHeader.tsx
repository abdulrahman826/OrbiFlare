import Link from "next/link";
import { DemoBadge, FirmsSourceBadge, LiveBadge } from "@/components/DemoBadge";
import { RiskBadge } from "@/components/RiskBadge";
import { TrajectoryBadge } from "@/components/TrajectoryBadge";
import { classificationLabel, fmtDate } from "@/lib/format";
import type { Facility, ThermalEvent } from "@/types/domain";

function Field({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-[10px] uppercase tracking-wider text-base-400">{k}</div>
      <div className="mt-0.5 truncate font-mono text-xs text-base-100">{children}</div>
    </div>
  );
}

export function InvestigationHeader({ event, facility, sourceLabel }: { event: ThermalEvent; facility: Facility | null; sourceLabel?: string }) {
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="font-mono text-lg font-semibold text-base-100">{event.event_id}</h1>
        <RiskBadge severity={event.severity} score={event.risk_score} />
        <TrajectoryBadge direction={event.trajectory_direction} />
        <span className="rounded border border-base-500/50 px-1.5 py-0.5 font-mono text-[10px] font-semibold tracking-wide text-base-200">{event.status}</span>
        {event.is_demo ? <DemoBadge /> : sourceLabel ? <FirmsSourceBadge label={sourceLabel} /> : <LiveBadge />}
        <span className="ml-auto text-xs text-base-400">{classificationLabel(event.classification)} <span className="text-base-500">(ML evidence, not a verdict)</span></span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 border-t border-base-700 pt-2.5 md:grid-cols-4 xl:grid-cols-6">
        <Field k="First detected">{fmtDate(event.first_detected)}</Field>
        <Field k="Last detected">{fmtDate(event.last_detected)}</Field>
        <Field k="Location">{event.centroid_lat.toFixed(4)}°N {event.centroid_lon.toFixed(4)}°E</Field>
        <Field k="Facility context">
          {facility ? <Link href={`/facilities/${facility.facility_id}`} className="text-accent hover:text-accent-bright">{facility.name}</Link> : "none in range"}
        </Field>
        <Field k="Peak FRP">{event.peak_frp !== null ? `${Math.round(event.peak_frp)} MW` : "--"}</Field>
        <Field k="Observations">{event.observation_count} over {event.duration_hours.toFixed(1)} h</Field>
      </div>
      <p className="mt-2 text-[11px] text-base-400">Detections are observations, not confirmed fires. OrbiFlare risk is an operational priority for analysts, separate from NASA FIRMS detection confidence.</p>
    </div>
  );
}
