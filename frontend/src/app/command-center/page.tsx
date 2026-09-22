import { EventCard } from "@/components/EventCard";
import { KPI } from "@/components/KPI";
import { MapPanel } from "@/components/MapPanel";
import { Panel } from "@/components/Panel";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function CommandCenterPage() {
  const [events, facilities, overview] = await Promise.all([
    api.listEvents(), api.listFacilities(), api.analyticsOverview(),
  ]);

  const active = events.filter((e) => e.status !== "EXTINGUISHED");
  const highPriority = active.filter((e) => e.severity === "HIGH" || e.severity === "CRITICAL");
  const escalating = active.filter((e) => e.trajectory_direction === "ESCALATING");
  const persistent = active.filter((e) => e.observation_count >= 6);
  const needsValidation = active.filter((e) => e.status === "DETECTED");

  const feed = [...active].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0)).slice(0, 12);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold text-base-100">Command Center</h1>
        <p className="text-sm text-base-400">Operational overview of active thermal events across all monitored facilities.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <KPI label="Active events" value={active.length} />
        <KPI label="High priority" value={highPriority.length} tone={highPriority.length ? "critical" : "default"} />
        <KPI label="Escalating" value={escalating.length} tone={escalating.length ? "warn" : "default"} />
        <KPI label="Persistent" value={persistent.length} />
        <KPI label="Needs validation" value={needsValidation.length} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <Panel title="Thermal Event Map">
            <MapPanel events={active} facilities={facilities} height={440} />
          </Panel>
        </div>
        <Panel title="Priority Event Feed" className="xl:col-span-1">
          <div className="max-h-[440px] space-y-2 overflow-y-auto scrollbar-thin pr-1">
            {feed.length === 0 && <p className="text-sm text-base-400">No active events.</p>}
            {feed.map((e) => (
              <EventCard key={e.event_id} event={e} />
            ))}
          </div>
        </Panel>
      </div>

      <Panel title="System status">
        <div className="grid grid-cols-2 gap-3 text-xs text-base-300 sm:grid-cols-4">
          <div>Total facilities monitored: <b className="text-base-100">{overview.total_facilities}</b></div>
          <div>Facilities with established baseline: <b className="text-base-100">{overview.facilities_with_established_baseline}</b></div>
          <div>Demo/synthetic events: <b className="text-base-100">{overview.demo_events}</b></div>
          <div>Total events tracked: <b className="text-base-100">{overview.total_events}</b></div>
        </div>
      </Panel>
    </div>
  );
}
