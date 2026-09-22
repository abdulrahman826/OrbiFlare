import Link from "next/link";
import { DemoBadge } from "@/components/DemoBadge";
import { facilityTypeLabel } from "@/lib/format";
import type { Facility } from "@/types/domain";

export function FacilityCard({ facility }: { facility: Facility }) {
  return (
    <Link
      href={`/facilities/${facility.facility_id}`}
      className="block rounded-md border border-base-700 bg-base-850 p-3 transition-colors hover:border-accent/50 hover:bg-base-800"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-sm font-medium text-base-100">{facility.name}</div>
          <div className="mt-0.5 text-xs text-base-400">
            {facilityTypeLabel(facility.facility_type)}
            {facility.region ? ` · ${facility.region}` : ""}
          </div>
        </div>
        {facility.is_demo && <DemoBadge compact />}
      </div>
      <div className="mt-2 font-mono text-[11px] text-base-500">{facility.facility_id}</div>
    </Link>
  );
}
