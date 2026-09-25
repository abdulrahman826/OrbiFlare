import Link from "next/link";
import { notFound } from "next/navigation";
import { BaselineStatus } from "@/components/BaselineStatus";
import { FacilitySourceBadge } from "@/components/DemoBadge";
import { EventTable } from "@/components/EventTable";
import { MapPanel } from "@/components/MapPanel";
import { DataRow, Panel, StateBlock } from "@/components/Panel";
import { api, ApiError } from "@/lib/api";
import { facilityTypeLabel, fmtNum } from "@/lib/format";

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
  const [events, twin] = await Promise.all([api.getFacilityEvents(facilityId), api.getFacilityTwin(facilityId).catch(() => null)]);
  const sorted = [...events].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0));
  const escalating = events.filter((e) => e.trajectory_direction === "ESCALATING").length;

  return (
    <div className="space-y-3">
      <Panel>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-semibold text-base-100">{facility.name}</h1>
              <FacilitySourceBadge source={facility.source} isDemo={facility.is_demo} />
            </div>
            <p className="mt-0.5 text-xs text-base-400">
              {facilityTypeLabel(facility.facility_type)}{facility.industry ? ` · ${facility.industry}` : ""} · {facility.region || facility.state || facility.country || "Unknown region"}
            </p>
            <p className="mt-1 font-mono text-[11px] text-base-500">{facility.facility_id} · {facility.latitude.toFixed(4)}°N {facility.longitude.toFixed(4)}°E · source {facility.source}</p>
          </div>
          <div className="flex items-center gap-3">
            {twin && <BaselineStatus confidence={twin.baseline_confidence} />}
            {twin && <Link href={`/thermal-twins/${facility.facility_id}`} className="text-[11px] font-semibold uppercase tracking-wider text-accent hover:text-accent-bright">Thermal Twin →</Link>}
          </div>
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1fr)_320px]">
        <Panel title="Location & nearby events" flush>
          <div className="p-2"><MapPanel facilities={[facility]} events={events} height={340} center={[facility.longitude, facility.latitude]} zoom={10} /></div>
        </Panel>
        <Panel title="Thermal behaviour summary" sub="From the facility Thermal Twin">
          {twin ? (
            <>
              <DataRow label="Historical events" value={twin.historical_event_count} />
              <DataRow label="Typical FRP" value={twin.normal_frp.n ? `${fmtNum(twin.normal_frp.median, 0)} MW` : "no data"} />
              <DataRow label="Typical duration" value={twin.normal_duration.n ? `${fmtNum(twin.normal_duration.median)} h` : "no data"} />
              <DataRow label="Typical persistence" value={twin.normal_persistence.n ? `${fmtNum(twin.normal_persistence.median, 0)} obs` : "no data"} />
              <DataRow label="Events now" value={events.length} />
              <DataRow label="Escalating" value={escalating} />
              {twin.baseline_confidence === "INSUFFICIENT" && <p className="mt-2 text-[11px] text-sev-medium">Insufficient history — normal behaviour is not established.</p>}
            </>
          ) : (
            <StateBlock kind="unavailable" title="No Thermal Twin" />
          )}
        </Panel>
      </div>

      <Panel title={`Events near this facility (${events.length})`} sub="Spatial association only" flush>
        {events.length === 0 ? (
          <div className="p-3"><StateBlock kind="empty" title="No thermal events recorded here" /></div>
        ) : (
          <EventTable events={sorted} facilityNames={{ [facility.facility_id]: facility.name }} />
        )}
      </Panel>
    </div>
  );
}
