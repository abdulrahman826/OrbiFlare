import Link from "next/link";
import { notFound } from "next/navigation";
import { DeviationTable } from "@/components/DeviationTable";
import { EventTimeline } from "@/components/EventTimeline";
import { EvidenceStackView } from "@/components/EvidenceStackView";
import { InvestigationHeader } from "@/components/InvestigationHeader";
import { MapPanel } from "@/components/MapPanel";
import { OperatorActionsSection } from "@/components/OperatorActionsSection";
import { Panel } from "@/components/Panel";
import { RiskTrajectoryChart } from "@/components/RiskTrajectoryChart";
import { UncertaintyNotice } from "@/components/UncertaintyNotice";
import { ApiError } from "@/lib/api";
import { api } from "@/lib/api";
import { classificationLabel, fmtNum } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function InvestigationPage({ params }: { params: Promise<{ eventId: string }> }) {
  const { eventId } = await params;
  let investigation;
  try {
    investigation = await api.getInvestigation(eventId);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  const { event, facility, thermal_twin, deviation, evidence, alternative_explanations, risk, trajectory, observations, ml_prediction, uncertainty_notes, operator_state } = investigation;

  return (
    <div className="space-y-5">
      <Panel>
        <InvestigationHeader event={event} />
      </Panel>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel title="Location & Event Map" className="xl:col-span-2">
          <MapPanel
            events={[event]}
            facilities={facility ? [facility] : []}
            height={340}
            center={[event.centroid_lon, event.centroid_lat]}
            zoom={11}
          />
          <div className="mt-4">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-base-300">Observation Timeline</div>
            <EventTimeline observations={observations} />
          </div>
        </Panel>

        <Panel title="Event Summary">
          <dl className="space-y-2 text-xs">
            <Row k="Facility context" v={facility ? `${facility.name} (~${fmtNum(event.facility_distance_km)} km away)` : "No facility within context radius"} />
            <Row k="Classification" v={classificationLabel(event.classification)} />
            <Row k="Peak FRP" v={`${fmtNum(event.peak_frp, 0)} MW`} />
            <Row k="Mean FRP" v={`${fmtNum(event.mean_frp, 0)} MW`} />
            <Row k="Duration" v={`${fmtNum(event.duration_hours)} h`} />
            <Row k="Observations" v={String(event.observation_count)} />
            <Row k="Footprint radius" v={`${fmtNum(event.footprint_radius_km, 2)} km`} />
          </dl>
          {facility && (
            <Link href={`/thermal-twins/${facility.facility_id}`} className="mt-3 inline-block text-xs font-medium text-accent hover:underline">
              View Facility Thermal Twin &rarr;
            </Link>
          )}
          <Link href={`/replay/${event.event_id}`} className="mt-3 block text-xs font-medium text-accent hover:underline">
            Open Event Replay &rarr;
          </Link>
        </Panel>
      </div>

      {thermal_twin && deviation && (
        <Panel title="Facility Thermal Twin -- Normal vs. Current">
          <DeviationTable deviation={deviation} />
        </Panel>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {evidence && (
          <Panel title="Why Flagged?">
            <EvidenceStackView evidence={evidence} />
          </Panel>
        )}

        {alternative_explanations && (
          <Panel title="Alternative Explanations">
            <div className="space-y-3">
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-wide text-accent">Primary hypothesis</div>
                <div className="mt-1 text-sm font-medium text-base-100">{alternative_explanations.primary_hypothesis.label}</div>
                <p className="mt-1 text-xs text-base-400">{alternative_explanations.primary_hypothesis.rationale}</p>
              </div>
              {alternative_explanations.alternatives.length > 0 && (
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-wide text-base-300">Possible alternatives</div>
                  <ul className="mt-1 space-y-2">
                    {alternative_explanations.alternatives.map((h, i) => (
                      <li key={i} className="text-xs text-base-300">
                        <span className="font-medium text-base-200">{h.label}</span>
                        {h.rationale && <span className="text-base-400"> -- {h.rationale}</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-wide text-base-300">Unknowns</div>
                <ul className="mt-1 space-y-1">
                  {alternative_explanations.unknowns.map((u, i) => (
                    <li key={i} className="text-xs text-base-400">
                      {u}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </Panel>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {trajectory && risk && (
          <Panel title="Risk Trajectory">
            <RiskTrajectoryChart trajectory={trajectory} />
            <p className="mt-2 text-xs text-base-300">{risk.explanation}</p>
            <ul className="mt-2 space-y-1">
              {risk.caveats.map((c, i) => (
                <li key={i} className="text-[11px] text-base-500">
                  {c}
                </li>
              ))}
            </ul>
          </Panel>
        )}

        {ml_prediction && (
          <Panel title="ML Evidence">
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded border border-base-700 bg-base-800 p-2.5 text-center">
                <div className="font-mono text-lg text-base-100">{(ml_prediction.p_persistent_industrial * 100).toFixed(0)}%</div>
                <div className="text-[10px] uppercase text-base-400">P(persistent industrial)</div>
              </div>
              <div className="rounded border border-base-700 bg-base-800 p-2.5 text-center">
                <div className="font-mono text-lg text-base-100">{(ml_prediction.p_natural_candidate * 100).toFixed(0)}%</div>
                <div className="text-[10px] uppercase text-base-400">P(natural/agri candidate)</div>
              </div>
            </div>
            {ml_prediction.low_confidence && (
              <p className="mt-2 text-xs font-medium text-sev-medium">Low-confidence prediction -- treat as an anomaly candidate signal only.</p>
            )}
            <div className="mt-3">
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-base-300">Top feature importance</div>
              {Object.entries(ml_prediction.feature_importance)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 4)
                .map(([k, v]) => (
                  <div key={k} className="mb-1 flex items-center gap-2">
                    <span className="w-32 shrink-0 text-[11px] text-base-400">{k}</span>
                    <div className="h-1.5 flex-1 rounded bg-base-700">
                      <div className="h-full rounded bg-accent" style={{ width: `${v * 100}%` }} />
                    </div>
                  </div>
                ))}
            </div>
            <p className="mt-2 text-[11px] text-base-500">Model: {ml_prediction.model_version} (trained on proxy-labelled synthetic data -- see the Model page).</p>
          </Panel>
        )}
      </div>

      <UncertaintyNotice notes={uncertainty_notes} />

      <Panel title="Operator Action">
        <OperatorActionsSection eventId={event.event_id} initialState={operator_state} />
      </Panel>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between border-b border-base-700/50 pb-1.5">
      <dt className="text-base-400">{k}</dt>
      <dd className="text-right text-base-100">{v}</dd>
    </div>
  );
}
