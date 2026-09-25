import Link from "next/link";
import { notFound } from "next/navigation";
import { BaselineBanner } from "@/components/BaselineBanner";
import { BaselineStatus } from "@/components/BaselineStatus";
import { DeviationTable } from "@/components/DeviationTable";
import { EventTable } from "@/components/EventTable";
import { FacilityThermalProfile } from "@/components/FacilityThermalProfile";
import { MapPanel } from "@/components/MapPanel";
import { Panel, StateBlock } from "@/components/Panel";
import { api, ApiError } from "@/lib/api";
import { baselineView } from "@/lib/assessment";

export const dynamic = "force-dynamic";

export default async function ThermalTwinDetailPage({ params }: { params: Promise<{ facilityId: string }> }) {
  const { facilityId } = await params;
  let twin;
  try {
    twin = await api.getFacilityTwin(facilityId);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  const [facility, events] = await Promise.all([api.getFacility(facilityId), api.getFacilityEvents(facilityId)]);
  const sorted = [...events].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0));
  const focus = sorted[0];
  const deviation = focus ? await api.getDeviation(focus.event_id).catch(() => null) : null;
  const insufficient = twin.baseline_confidence === "INSUFFICIENT";

  return (
    <div className="space-y-3">
      <Panel>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-base font-semibold text-base-100">{facility.name} · {baselineView(twin.baseline_confidence, true).twinTitle}</h1>
            <p className="mt-0.5 text-xs text-base-400">
              Baseline from {twin.historical_event_count} historical event(s) / {twin.historical_observation_count} observation(s).{" "}
              <Link href={`/facilities/${facility.facility_id}`} className="text-accent hover:underline">Facility →</Link>
            </p>
          </div>
          <BaselineStatus confidence={twin.baseline_confidence} />
        </div>
        {!insufficient && <div className="mt-2"><BaselineBanner status={twin.baseline_confidence} hasFacility /></div>}
        {insufficient && (
          <p className="mt-2 rounded border border-sev-critical/30 bg-sev-critical/5 p-2 text-xs text-sev-critical">
            INSUFFICIENT BASELINE — not enough history to define normal behaviour. Deviation is not assessed and no history is fabricated.
          </p>
        )}
      </Panel>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <Panel title="Normal — historical behaviour profile"><FacilityThermalProfile twin={twin} /></Panel>
        <div className="space-y-3">
          <Panel title="Footprint" flush><div className="p-2"><MapPanel facilities={[facility]} events={events} height={220} center={[facility.longitude, facility.latitude]} zoom={11} legend={false} /></div></Panel>
          <Panel title={focus ? `Current vs normal · ${focus.event_id}` : "Current vs normal"} sub="Highest-risk current event at this facility">
            {deviation ? <DeviationTable deviation={deviation} /> : <StateBlock kind={focus ? "unavailable" : "empty"} title={focus ? "No deviation available" : "No current activity"} />}
          </Panel>
        </div>
      </div>

      <Panel title={`Current events (${events.length})`} flush>
        {events.length === 0 ? <div className="p-3"><StateBlock kind="empty" title="No events at this facility" /></div> : <EventTable events={sorted} facilityNames={{ [facility.facility_id]: facility.name }} />}
      </Panel>
    </div>
  );
}
