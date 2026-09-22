import { BarByKey, DeviationHistogram, SeverityPie } from "@/components/AnalyticsCharts";
import { KPI } from "@/components/KPI";
import { Panel } from "@/components/Panel";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function AnalyticsPage() {
  const [overview, eventsAnalytics, riskAnalytics] = await Promise.all([
    api.analyticsOverview(), api.analyticsEvents(), api.analyticsRisk(),
  ]);
  const ev = eventsAnalytics as {
    by_state: Record<string, number>; by_facility_type: Record<string, number>; by_classification: Record<string, number>;
    deviation_scores: number[]; peak_frp_values: number[];
  };
  const metrics = riskAnalytics.model_metrics;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold text-base-100">Analytics</h1>
        <p className="text-sm text-base-400">Aggregate view across all tracked thermal events and facility baselines.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <KPI label="Total events" value={overview.total_events} />
        <KPI label="High risk" value={overview.high_risk_events} tone={overview.high_risk_events ? "critical" : "default"} />
        <KPI label="Escalating" value={overview.escalating_events} tone={overview.escalating_events ? "warn" : "default"} />
        <KPI label="Established baselines" value={`${overview.facilities_with_established_baseline}/${overview.total_facilities}`} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SeverityPie data={overview.by_severity} />
        <BarByKey title="Events by State" data={ev.by_state} />
        <BarByKey title="Events by Facility Type" data={ev.by_facility_type} />
        <BarByKey title="Events by Classification" data={ev.by_classification} colorMode="classification" />
        <DeviationHistogram values={ev.deviation_scores} />
        <BarByKey title="Risk Trajectory Directions" data={riskAnalytics.trajectory_directions} />
      </div>

      <Panel title="Model Metrics Summary">
        <div className="grid grid-cols-2 gap-3 text-xs md:grid-cols-5">
          <Stat label="Accuracy (holdout)" value={`${(metrics.accuracy * 100).toFixed(0)}%`} />
          <Stat label="ROC-AUC" value={metrics.roc_auc ? metrics.roc_auc.toFixed(2) : "--"} />
          <Stat label="Train / Val size" value={`${metrics.n_train} / ${metrics.n_val}`} />
          <Stat label="Split strategy" value={metrics.split_strategy} />
          <Stat label="Version" value={metrics.model_version} />
        </div>
        <p className="mt-3 text-[11px] text-base-500">
          Proxy-labelled synthetic training data -- see the <a href="/model" className="text-accent hover:underline">Model page</a> for full caveats. This is not real-world fire-detection accuracy.
        </p>
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
