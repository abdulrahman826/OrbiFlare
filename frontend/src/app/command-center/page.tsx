import Link from "next/link";
import { DistBars } from "@/components/DistBar";
import { FirmsRefreshControl } from "@/components/FirmsRefreshControl";
import { EventCard } from "@/components/EventCard";
import { KPI } from "@/components/KPI";
import { MapPanel } from "@/components/MapPanel";
import { Panel, PageHeader, StateBlock } from "@/components/Panel";
import { api } from "@/lib/api";
import { TRAJECTORY_LABEL } from "@/lib/format";
import type { Severity, TrajectoryDirection } from "@/types/domain";

export const dynamic = "force-dynamic";

const SEV_ORDER: Severity[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
const SEV_BAR: Record<Severity, string> = { CRITICAL: "bg-sev-critical", HIGH: "bg-sev-high", MEDIUM: "bg-sev-medium", LOW: "bg-sev-low" };
const TRAJ_ORDER: TrajectoryDirection[] = ["ESCALATING", "INCREASING", "STABLE", "DECREASING", "INSUFFICIENT_DATA"];
const TRAJ_BAR: Record<TrajectoryDirection, string> = {
  ESCALATING: "bg-sev-critical", INCREASING: "bg-sev-medium", STABLE: "bg-base-400", DECREASING: "bg-info", INSUFFICIENT_DATA: "bg-base-600",
};

export default async function CommandCenterPage() {
  let data;
  try {
    data = await Promise.all([api.listEvents(), api.listFacilities(), api.analyticsOverview(), api.incidentSummary().catch(() => null), api.listObservations("FIRMS").catch(() => []), api.health().catch(() => null)]);
  } catch {
    return (
      <>
        <PageHeader title="Command Center" />
        <StateBlock kind="error" title="Backend unavailable">
          Could not reach the OrbiFlare API. Start it with <span className="font-mono">make backend-dev</span> and reload.
        </StateBlock>
      </>
    );
  }
  const [events, facilities, overview, incidentSummary, firmsObs, health] = data;
  const names = Object.fromEntries(facilities.map((f) => [f.facility_id, f.name]));

  const active = events.filter((e) => e.status !== "EXTINGUISHED");
  const highPriority = active.filter((e) => e.severity === "HIGH" || e.severity === "CRITICAL");
  const escalating = active.filter((e) => e.trajectory_direction === "ESCALATING");
  const persistent = active.filter((e) => e.observation_count >= 6);
  const needsValidation = active.filter((e) => e.status === "DETECTED");
  const feed = [...active].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0)).slice(0, 12);

  const sevCounts = SEV_ORDER.map((s) => ({ label: s, value: active.filter((e) => e.severity === s).length, colorClass: SEV_BAR[s] }));
  const trajCounts = TRAJ_ORDER.map((t) => ({ label: TRAJECTORY_LABEL[t], value: active.filter((e) => (e.trajectory_direction ?? "INSUFFICIENT_DATA") === t).length, colorClass: TRAJ_BAR[t] }));

  const byFacility = new Map<string, number>();
  for (const e of active) if (e.facility_id) byFacility.set(e.facility_id, (byFacility.get(e.facility_id) ?? 0) + 1);
  const facilityItems = [...byFacility.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6).map(([id, v]) => ({ label: names[id] ?? id, value: v, colorClass: "bg-accent" }));

  // Insufficient / no-facility are "unknown", not anomalies: neutral colours, never the severity palette.
  const baselineItems = [
    ...(["ESTABLISHED", "LIMITED", "INSUFFICIENT"] as const).map((b) => ({
      label: b[0] + b.slice(1).toLowerCase(),
      value: active.filter((e) => e.baseline_confidence === b).length,
      colorClass: b === "ESTABLISHED" ? "bg-accent" : b === "LIMITED" ? "bg-base-400" : "bg-base-600",
    })),
    { label: "No facility context", value: active.filter((e) => !e.baseline_confidence).length, colorClass: "bg-base-700" },
  ];

  return (
    <div className="space-y-3">
      <PageHeader title="Command Center" sub="Evolving thermal events prioritised for analyst investigation. Detections are observations, not confirmed fires." action={<FirmsRefreshControl firms={health?.firms ?? null} />} />

      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
        <KPI label="Active events" value={active.length} sub="not extinguished" />
        <KPI label="High priority" value={highPriority.length} tone={highPriority.length ? "critical" : "default"} sub="HIGH + CRITICAL" />
        <KPI label="Escalating" value={escalating.length} tone={escalating.length ? "high" : "default"} sub="trajectory ESCALATING" />
        <KPI label="Persistent" value={persistent.length} sub="≥ 6 observations" />
        <KPI label="Needs validation" value={needsValidation.length} tone={needsValidation.length ? "warn" : "default"} sub="status DETECTED" />
        <KPI label="Established twins" value={`${overview.facilities_with_established_baseline}/${overview.total_facilities}`} sub="facility baselines" />
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1fr)_400px]">
        <Panel title="Thermal event map" sub="Interpreted events by severity · raw FIRMS observations as small dots · facilities as neutral squares" flush>
          <div className="p-2">
            {active.length === 0 ? <StateBlock kind="empty" title="No active events" /> : <MapPanel events={active} facilities={facilities} observations={firmsObs} height={520} />}
          </div>
        </Panel>
        <Panel
          title="Priority alert feed"
          sub="Top by risk score (operational priority, not fire probability)"
          action={<Link href="/events" className="text-[11px] font-semibold uppercase tracking-wider text-accent hover:text-accent-bright">All events →</Link>}
          flush
        >
          <div className="scrollbar-thin max-h-[566px] space-y-2 overflow-y-auto p-2">
            {feed.length === 0 && <StateBlock kind="empty" title="No active events" />}
            {feed.map((e) => <EventCard key={e.event_id} event={e} facilityName={e.facility_id ? names[e.facility_id] : undefined} />)}
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Panel title="Severity distribution"><DistBars items={sevCounts} /></Panel>
        <Panel title="Risk trajectory distribution"><DistBars items={trajCounts} /></Panel>
        <Panel title="Facility activity" sub="Active events near each facility"><DistBars items={facilityItems} emptyText="No events with facility context." /></Panel>
        <Panel title="Baseline coverage" sub="Active events by Thermal Twin state"><DistBars items={baselineItems} /></Panel>
      </div>

      <Panel title="Data status">
        <div className="grid grid-cols-2 gap-3 text-xs text-base-300 sm:grid-cols-4">
          <div>Facilities monitored <b className="font-mono text-base-100">{overview.total_facilities}</b></div>
          <div>Events tracked <b className="font-mono text-base-100">{overview.total_events}</b></div>
          <div>Demo events <b className="font-mono text-base-100">{overview.demo_events}</b></div>
          <div>Live NASA FIRMS events <b className="font-mono text-base-100">{overview.total_events - overview.demo_events}</b> <span className="text-base-400">({firmsObs.length} raw observations)</span></div>
          {incidentSummary && (
            <div className="sm:col-span-4">
              Historical reference incidents <b className="font-mono text-info">{incidentSummary.total}</b> <span className="text-base-400">(historical · not live · not FIRMS detections · not used for training)</span>{" "}
              <Link href="/incidents" className="font-semibold uppercase tracking-wider text-accent hover:text-accent-bright">View →</Link>
            </div>
          )}
        </div>
      </Panel>
    </div>
  );
}
