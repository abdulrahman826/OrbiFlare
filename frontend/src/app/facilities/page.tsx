import { FacilityCard } from "@/components/FacilityCard";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function FacilitiesPage() {
  const facilities = await api.listFacilities();

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-base-100">Facilities</h1>
        <p className="text-sm text-base-400">{facilities.length} monitored industrial facilit{facilities.length === 1 ? "y" : "ies"}.</p>
      </div>
      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
        {facilities.map((f) => (
          <FacilityCard key={f.facility_id} facility={f} />
        ))}
      </div>
    </div>
  );
}
