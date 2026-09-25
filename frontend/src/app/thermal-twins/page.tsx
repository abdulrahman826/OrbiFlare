import { KPI } from "@/components/KPI";
import { PageHeader, StateBlock } from "@/components/Panel";
import { ThermalTwinCard } from "@/components/ThermalTwinCard";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ThermalTwinsPage() {
  let data;
  try {
    data = await Promise.all([api.listThermalTwins(), api.listFacilities(), api.listEvents()]);
  } catch {
    return <StateBlock kind="error" title="Backend unavailable" />;
  }
  const [twins, facilities, events] = data;
  const name = Object.fromEntries(facilities.map((f) => [f.facility_id, f.name]));
  const count = (c: string) => twins.filter((t) => t.baseline_confidence === c).length;

  return (
    <div className="space-y-3">
      <PageHeader title="Facility Thermal Twins" sub="Multidimensional behavioural baselines learned from each facility's own history: what is normal here." />
      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4">
        <KPI label="Twins" value={twins.length} />
        <KPI label="Established" value={count("ESTABLISHED")} tone="good" />
        <KPI label="Limited" value={count("LIMITED")} tone="warn" />
        <KPI label="Insufficient" value={count("INSUFFICIENT")} tone={count("INSUFFICIENT") ? "critical" : "default"} sub="never fabricated" />
      </div>
      {twins.length === 0 ? (
        <StateBlock kind="empty" title="No thermal twins computed yet" />
      ) : (
        <div className="grid grid-cols-1 gap-2.5 md:grid-cols-2 xl:grid-cols-3">
          {twins.map((t) => {
            const mine = events.filter((e) => e.facility_id === t.facility_id);
            const devs = mine.map((e) => e.overall_deviation_score).filter((v): v is number => v !== null);
            return <ThermalTwinCard key={t.facility_id} twin={t} facilityName={name[t.facility_id]} activeEvents={mine.length} maxDeviation={devs.length ? Math.max(...devs) : null} />;
          })}
        </div>
      )}
    </div>
  );
}
