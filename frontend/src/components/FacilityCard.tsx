import Link from "next/link";
import { BaselineStatus } from "@/components/BaselineStatus";
import { FacilitySourceBadge } from "@/components/DemoBadge";
import { RiskBadge } from "@/components/RiskBadge";
import { facilityTypeLabel } from "@/lib/format";
import type { BaselineConfidence, Facility, Severity } from "@/types/domain";

export interface FacilityActivity {
  eventCount: number;
  topSeverity: Severity | null;
  topRisk: number | null;
  escalating: number;
}

export function FacilityCard({ facility, activity, baseline }: { facility: Facility; activity?: FacilityActivity; baseline?: BaselineConfidence }) {
  return (
    <Link href={`/facilities/${facility.facility_id}`} className="group block rounded border border-base-700 bg-base-850 p-3 transition-colors hover:border-base-500 hover:bg-base-800">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-base-100">{facility.name}</div>
          <div className="mt-0.5 truncate text-[11px] text-base-400">
            {facilityTypeLabel(facility.facility_type)}{facility.region || facility.state ? ` · ${facility.region || facility.state}` : ""}
          </div>
        </div>
        <FacilitySourceBadge source={facility.source} isDemo={facility.is_demo} />
      </div>
      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[11px] text-base-400">
        {baseline && <BaselineStatus confidence={baseline} />}
        <span>events <b className="font-mono text-base-100">{activity?.eventCount ?? 0}</b></span>
        {!!activity?.escalating && <span className="text-sev-high">{activity.escalating} escalating</span>}
        {activity?.topSeverity && <RiskBadge severity={activity.topSeverity} score={activity.topRisk} size="sm" />}
      </div>
      <div className="mt-2 flex items-center justify-between">
        <span className="font-mono text-[10px] text-base-500">{facility.facility_id} · {facility.source}</span>
        <span className="text-[11px] font-semibold uppercase tracking-wider text-accent group-hover:text-accent-bright">Open →</span>
      </div>
    </Link>
  );
}
