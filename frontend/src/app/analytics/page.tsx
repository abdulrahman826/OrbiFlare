import { BarByKey, DeviationHistogram, SeverityPie } from "@/components/AnalyticsCharts";
import { DistBars } from "@/components/DistBar";
import { KPI } from "@/components/KPI";
import { PageHeader, Panel, StateBlock } from "@/components/Panel";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function AnalyticsPage() {
  let data;
  try {
    data = await Promise.all([api.analyticsOverview(), api.analyticsEvents(), api.analyticsRisk(), api.analyticsDataQuality(), api.incidentSummary().catch(() => null), api.liveSummary().catch(() => null)]);
  } catch {
    return <StateBlock kind="error" title="Analytics unavailable">The backend could not be reached.</StateBlock>;
  }
  const [overview, eventsAnalytics, riskAnalytics, dataQuality, incidentSummary, live] = data;
  const { coordinate_validation: cv, ingestion_batches: batches } = dataQuality;
  const ev = eventsAnalytics as {
    by_state: Record<string, number>; by_region: Record<string, number>; by_admin_state: Record<string, number>; by_facility_type: Record<string, number>; by_classification: Record<string, number>;
    deviation_scores: number[]; peak_frp_values: number[];
  };
  const metrics = riskAnalytics.model_metrics;

  return (
    <div className="space-y-3">
      <PageHeader title="Analytics" sub="Aggregates computed by the backend across tracked thermal events and facility baselines. Each panel answers one question." />

      {live && (
        <>
          <Panel variant="section" title="Live NASA FIRMS" sub="Real observations and the OrbiFlare events built from them. NASA detection confidence and OrbiFlare severity are different things and are never combined.">
            <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
              <KPI label="FIRMS observations" value={live.firms_observations.total} sub="live, NASA" />
              <KPI label="Live events" value={live.events.live_total} sub="OrbiFlare" />
              <KPI label="Multi-observation" value={live.events.multi_observation} sub="persistent events" />
              <KPI label="With facility context" value={live.events.with_facility_context} sub="spatial association" />
              <KPI label="Established baseline" value={live.events.by_baseline.ESTABLISHED ?? 0} tone="good" sub="real history" />
              <KPI label="Demo data in live view" value={live.purity.demo_observations + live.purity.demo_events} sub="must be 0" tone={live.purity.demo_observations + live.purity.demo_events ? "critical" : "good"} />
            </div>
          </Panel>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-4">
            <Panel title="NASA FIRMS confidence" sub="Per observation · satellite attribute"><DistBars items={Object.entries(live.firms_observations.by_nasa_confidence).map(([k, v]) => ({ label: k, value: v, colorClass: "bg-base-400" }))} /></Panel>
            <Panel title="OrbiFlare severity" sub="Per event · operational risk"><DistBars items={["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((k) => ({ label: k, value: live.events.by_orbiflare_severity[k] ?? 0, colorClass: k === "CRITICAL" ? "bg-sev-critical" : k === "HIGH" ? "bg-sev-high" : k === "MEDIUM" ? "bg-sev-medium" : "bg-sev-low" }))} /></Panel>
            <Panel title="Facility context" sub="Live events"><DistBars items={[{ label: "With context", value: live.events.with_facility_context, colorClass: "bg-accent" }, { label: "None in radius", value: live.events.without_facility_context, colorClass: "bg-base-400" }]} /></Panel>
            <Panel title="Baseline sufficiency" sub="Live events · real FIRMS history only"><DistBars items={[
              { label: "Established", value: live.events.by_baseline.ESTABLISHED ?? 0, colorClass: "bg-sev-low" },
              { label: "Limited", value: live.events.by_baseline.LIMITED ?? 0, colorClass: "bg-sev-medium" },
              { label: "Insufficient", value: live.events.by_baseline.INSUFFICIENT ?? 0, colorClass: "bg-sev-critical" },
              { label: "No facility", value: live.events.by_baseline.NO_FACILITY_CONTEXT ?? 0, colorClass: "bg-base-400" },
            ]} /></Panel>
          </div>
          <p className="text-[11px] text-base-400">A baseline exists only for facilities with enough real historical FIRMS events; “no facility” events cannot have one, and that is not evidence of a natural fire.</p>
        </>
      )}

      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
        <KPI label="Total events" value={overview.total_events} />
        <KPI label="High risk" value={overview.high_risk_events} tone={overview.high_risk_events ? "critical" : "default"} />
        <KPI label="Escalating" value={overview.escalating_events} tone={overview.escalating_events ? "warn" : "default"} />
        <KPI label="Established baselines" value={`${overview.facilities_with_established_baseline}/${overview.total_facilities}`} />
        <KPI label="Demo data" value={overview.demo_events} sub="events" />
        <KPI label="Live / FIRMS" value={overview.total_events - overview.demo_events} sub="events" />
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
        <SeverityPie data={overview.by_severity} />
        <BarByKey title="Where: events by administrative state" data={ev.by_admin_state} note="Point-in-polygon of each event centroid against real India state boundaries. Independent of facility metadata." />
        <BarByKey title="Facility metadata: events by facility region" data={ev.by_region} note="Region of the associated facility (spatial association); events without facility context are grouped separately." />
        <BarByKey title="Workflow: events by operator status" data={ev.by_state} />
        <BarByKey title="Which industry: events by facility type" data={ev.by_facility_type} />
        <BarByKey title="ML evidence: events by class (facility-context events only; not verdicts)" data={ev.by_classification} colorMode="classification" />
        <DeviationHistogram values={ev.deviation_scores} />
        <BarByKey title="Evolution: risk trajectory directions" data={riskAnalytics.trajectory_directions} />
      </div>

      {incidentSummary && (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <BarByKey title="Historical reference: records by kind" data={incidentSummary.by_record_kind} note="Curated historical records. Not live, not FIRMS detections, not used for training." />
          <BarByKey title="Historical reference: records by state" data={incidentSummary.by_state} note="State as supplied by the record." />
        </div>
      )}

      <Panel title="Model metrics summary">
        <div className="grid grid-cols-2 gap-3 text-xs md:grid-cols-5">
          <Stat label="Macro-F1 (development set)" value={metrics.macro_f1 != null ? metrics.macro_f1.toFixed(2) : "--"} />
          <Stat label="ROC-AUC (development set)" value={metrics.roc_auc ? metrics.roc_auc.toFixed(2) : "--"} />
          <Stat label="Train / hold-out size" value={`${metrics.n_train} / ${metrics.n_val}`} />
          <Stat label="Evaluation" value="Random hold-out" />
          <Stat label="Version" value={metrics.model_version} />
        </div>
        <p className="mt-3 text-[11px] text-base-500">
          Development-set evaluation of the ML evidence layer -- see the <a href="/model" className="text-accent hover:underline">Model page</a> for full caveats. This is not real-world fire-detection accuracy.
        </p>
      </Panel>

      <Panel title="Data quality & coordinate validation">
        <div className="grid grid-cols-2 gap-3 text-xs md:grid-cols-4">
          <Stat label="Observations plotted" value={String(cv.total_observations)} />
          <Stat label="Within region bbox" value={String(cv.in_region_count)} />
          <Stat label="Outside region bbox" value={String(cv.outside_region_count)} />
          <Stat label="Ingestion batches" value={String(batches.length)} />
        </div>
        <p className="mt-2 text-[11px] text-base-500">
          Region = {cv.region_bbox.label} ({cv.region_bbox.west}, {cv.region_bbox.south}) to ({cv.region_bbox.east}, {cv.region_bbox.north}).
          {cv.latitude_range && ` Latitude range ${cv.latitude_range[0].toFixed(2)} to ${cv.latitude_range[1].toFixed(2)}, longitude range ${cv.longitude_range![0].toFixed(2)} to ${cv.longitude_range![1].toFixed(2)}.`}
          {" "}No observation is ever moved, clipped, or dropped for falling outside this box -- it is reporting only.
        </p>
        {cv.outside_region_samples.length > 0 && (
          <div className="mt-3 overflow-x-auto">
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-base-300">Sample out-of-region observations</div>
            <table className="w-full text-[11px]">
              <thead>
                <tr className="text-left text-base-400">
                  <th className="pb-1 pr-3">Observation</th>
                  <th className="pb-1 pr-3">Lat</th>
                  <th className="pb-1 pr-3">Lon</th>
                  <th className="pb-1 pr-3">Source</th>
                </tr>
              </thead>
              <tbody>
                {cv.outside_region_samples.map((s) => (
                  <tr key={s.observation_id} className="border-t border-base-700/60">
                    <td className="py-1 pr-3 font-mono text-base-200">{s.observation_id}</td>
                    <td className="py-1 pr-3 font-mono text-base-100">{s.latitude.toFixed(3)}</td>
                    <td className="py-1 pr-3 font-mono text-base-100">{s.longitude.toFixed(3)}</td>
                    <td className="py-1 pr-3 text-base-300">{s.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {batches.length > 0 && (
          <div className="mt-3 overflow-x-auto">
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-base-300">Ingestion batches</div>
            <table className="w-full text-[11px]">
              <thead>
                <tr className="text-left text-base-400">
                  <th className="pb-1 pr-3">Batch</th>
                  <th className="pb-1 pr-3">Source</th>
                  <th className="pb-1 pr-3">Received</th>
                  <th className="pb-1 pr-3">Accepted</th>
                  <th className="pb-1 pr-3">Flagged</th>
                  <th className="pb-1 pr-3">Rejected</th>
                </tr>
              </thead>
              <tbody>
                {batches.map((b) => (
                  <tr key={b.batch_id} className="border-t border-base-700/60">
                    <td className="py-1 pr-3 font-mono text-base-200">{b.batch_id}</td>
                    <td className="py-1 pr-3 text-base-300">{b.source}</td>
                    <td className="py-1 pr-3 font-mono text-base-100">{b.rows_received}</td>
                    <td className="py-1 pr-3 font-mono text-base-100">{b.rows_accepted}</td>
                    <td className="py-1 pr-3 font-mono text-base-100">{b.rows_flagged}</td>
                    <td className="py-1 pr-3 font-mono text-base-100">{b.rows_rejected}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase text-base-400">{label}</div>
      <div className="mt-0.5 font-mono text-sm text-base-100">{value}</div>
    </div>
  );
}
