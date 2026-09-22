import { notFound } from "next/navigation";
import { BaselineStatus } from "@/components/BaselineStatus";
import { EventCard } from "@/components/EventCard";
import { FacilityThermalProfile } from "@/components/FacilityThermalProfile";
import { Panel } from "@/components/Panel";
import { api, ApiError } from "@/lib/api";

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
  const activeEvents = [...events].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0));

  return (
    <div className="space-y-5">
      <Panel>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-lg font-semibold text-base-100">{facility.name} -- Thermal Twin</h1>
            <p className="text-sm text-base-400">
              Baseline built from {twin.historical_event_count} historical event(s) / {twin.historical_observation_count} observation(s)
            </p>
          </div>
          <BaselineStatus confidence={twin.baseline_confidence} />
        </div>
        {twin.baseline_confidence === "INSUFFICIENT" && (
          <p className="mt-2 rounded border border-sev-critical/30 bg-sev-critical/5 p-2 text-xs text-sev-critical">
            INSUFFICIENT BASELINE: not enough historical data exists for this facility. Behavioural deviation cannot be reliably assessed until more history accumulates. No history is fabricated to fill this gap.
          </p>
        )}
      </Panel>

      <Panel title="Historical Behaviour Profile">
        <FacilityThermalProfile twin={twin} />
      </Panel>

      <Panel title={`Active Events (${activeEvents.length})`}>
        {activeEvents.length === 0 ? (
          <p className="text-sm text-base-400">No events at this facility.</p>
        ) : (
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            {activeEvents.map((e) => (
              <EventCard key={e.event_id} event={e} />
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
