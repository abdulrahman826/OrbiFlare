import { FacilityCard, type FacilityActivity } from "@/components/FacilityCard";
import { MapPanel } from "@/components/MapPanel";
import { PageHeader, Panel, StateBlock } from "@/components/Panel";
import { api } from "@/lib/api";
import type { ThermalEvent } from "@/types/domain";

export const dynamic = "force-dynamic";

export default async function FacilitiesPage() {
  let data;
  try {
    data = await Promise.all([api.listFacilities(), api.listEvents(), api.listThermalTwins()]);
  } catch {
    return <StateBlock kind="error" title="Backend unavailable" />;
  }
  const [facilities, events, twins] = data;
  const twinBy = Object.fromEntries(twins.map((t) => [t.facility_id, t.baseline_confidence]));
  const byFac = new Map<string, ThermalEvent[]>();
  for (const e of events) if (e.facility_id) byFac.set(e.facility_id, [...(byFac.get(e.facility_id) ?? []), e]);
  const activity = (id: string): FacilityActivity => {
    const list = byFac.get(id) ?? [];
    const top = [...list].sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0))[0];
    return { eventCount: list.length, topSeverity: top?.severity ?? null, topRisk: top?.risk_score ?? null, escalating: list.filter((e) => e.trajectory_direction === "ESCALATING").length };
  };
  const sorted = [...facilities].sort((a, b) => (activity(b.facility_id).topRisk ?? -1) - (activity(a.facility_id).topRisk ?? -1));

  return (
    <div className="space-y-3">
      <PageHeader title="Facilities" sub={`${facilities.length} facilities providing spatial context. Proximity is contextual evidence, never proof of causation.`} />
      {facilities.length === 0 ? (
        <StateBlock kind="empty" title="No facilities loaded" />
      ) : (
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          <div className="grid grid-cols-1 content-start gap-2.5 md:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
            {sorted.map((f) => <FacilityCard key={f.facility_id} facility={f} activity={activity(f.facility_id)} baseline={twinBy[f.facility_id]} />)}
          </div>
          <Panel title="Facility map" flush>
            <div className="p-2"><MapPanel facilities={facilities} events={events} height={460} /></div>
          </Panel>
        </div>
      )}
    </div>
  );
}
