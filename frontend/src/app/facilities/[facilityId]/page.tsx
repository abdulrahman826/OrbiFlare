import Link from "next/link";
import { notFound } from "next/navigation";
import { BaselineStatus } from "@/components/BaselineStatus";
import { DemoBadge } from "@/components/DemoBadge";
import { EventCard } from "@/components/EventCard";
import { MapPanel } from "@/components/MapPanel";
import { Panel } from "@/components/Panel";
import { api, ApiError } from "@/lib/api";
import { facilityTypeLabel } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function FacilityDetailPage({ params }: { params: Promise<{ facilityId: string }> }) {
  const { facilityId } = await params;
  let facility;
  try {
    facility = await api.getFacility(facilityId);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  const [events, twin] = await Promise.all([
    api.getFacilityEvents(facilityId),
    api.getFacilityTwin(facilityId).catch(() => null),
  ]);

  return (
    <div className="space-y-5">
      <Panel>
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold text-base-100">{facility.name}</h1>
              {facility.is_demo && <DemoBadge />}
            </div>
            <p className="text-sm text-base-400">
              {facilityTypeLabel(facility.facility_type)}
              {facility.industry ? ` · ${facility.industry}` : ""} · {facility.region || facility.state || facility.country || "Unknown region"}
            </p>
            <p className="mt-1 font-mono text-xs text-base-500">{facility.facility_id} · {facility.latitude.toFixed(4)}, {facility.longitude.toFixed(4)}</p>
          </div>
          {twin && <BaselineStatus confidence={twin.baseline_confidence} />}
        </div>
      </Panel>

      <Panel title="Location">
        <MapPanel facilities={[facility]} events={events} height={320} center={[facility.longitude, facility.latitude]} zoom={10} />
      </Panel>

      {twin && (
        <Link href={`/thermal-twins/${facility.facility_id}`} className="inline-block text-sm font-medium text-accent hover:underline">
          View full Thermal Twin profile &rarr;
        </Link>
      )}

      <Panel title={`Events at this facility (${events.length})`}>
        {events.length === 0 ? (
          <p className="text-sm text-base-400">No thermal events recorded at this facility yet.</p>
        ) : (
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            {events.map((e) => (
              <EventCard key={e.event_id} event={e} />
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
