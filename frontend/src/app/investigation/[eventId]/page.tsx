import Link from "next/link";
import { notFound } from "next/navigation";
import { BaselineBanner } from "@/components/BaselineBanner";
import { HistoricalBadge } from "@/components/DemoBadge";
import { DeviationTable } from "@/components/DeviationTable";
import { EventReplayPlayer } from "@/components/EventReplayPlayer";
import { EventTimeline } from "@/components/EventTimeline";
import { EvidenceStackView } from "@/components/EvidenceStackView";
import { FacilityContextSection } from "@/components/FacilityContextSection";
import { FirmsObservationsTable } from "@/components/FirmsObservationsTable";
import { InvestigationHeader } from "@/components/InvestigationHeader";
import { MapPanel } from "@/components/MapPanel";
import { MlEvidenceNote } from "@/components/MlEvidenceNote";
import { NasaObservationRows } from "@/components/NasaObservationRows";
import { OperatorActionsSection } from "@/components/OperatorActionsSection";
import { DataRow, Panel, StateBlock } from "@/components/Panel";
import { RiskExplanation } from "@/components/RiskExplanation";
import { RiskTrajectoryChart } from "@/components/RiskTrajectoryChart";
import { TierHeading } from "@/components/TierHeading";
import { UncertaintyNotice } from "@/components/UncertaintyNotice";
import { api, ApiError } from "@/lib/api";
import { baselineView, limitationsFor } from "@/lib/assessment";
import { firmsSourceLabel } from "@/lib/firms";
import { fmtDate, fmtNum } from "@/lib/format";

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
  const replay = await api.getReplay(eventId).catch(() => null);
  const facilityCtx = await api.getFacilityContext(eventId).catch(() => null);
  const nearIncidents = await api.incidentsNear(investigation.event.centroid_lat, investigation.event.centroid_lon, 50).catch(() => []);

  const { event, facility, thermal_twin, deviation, evidence, alternative_explanations, risk, trajectory, observations, ml_prediction, uncertainty_notes, operator_state, operator_history } = investigation;
  const live = !event.is_demo;
  const sourceLabel = live ? firmsSourceLabel(observations) : "";
  const baseline = deviation?.baseline_confidence ?? thermal_twin?.baseline_confidence ?? null;
  const bView = baselineView(baseline, !!event.facility_id);
  const ambiguous = ml_prediction?.low_confidence && evidence && evidence.supporting_evidence.length > 0 && evidence.contradicting_evidence.length > 0;
  const limitations = limitationsFor({ baseline, hasFacility: !!event.facility_id, quality: event.facility_context_quality, mlPresent: !!ml_prediction });

  return (
    <div className="space-y-3">
      <Panel><InvestigationHeader event={event} facility={facility} sourceLabel={sourceLabel} /></Panel>

      {ambiguous && (
        <div className="rounded border border-sev-medium/40 bg-sev-medium/5 px-3 py-2 text-xs text-sev-medium">
          <b>Ambiguous — requires analyst validation.</b> Behavioural evidence is mixed and ML confidence is below the reliability threshold. OrbiFlare does not force a verdict.
        </div>
      )}

      {/* ============================ 1 · NASA OBSERVATION ============================ */}
      <TierHeading n={1} label="NASA observation" sub="What the satellite actually measured — nothing here is an OrbiFlare judgement" />
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1fr)_340px]">
        <Panel variant="section" title="Location & observation timeline" sub="Where is the heat, and how did FRP evolve?" flush>
          <div className="space-y-2 p-2">
            <MapPanel events={[event]} facilities={facility ? [facility] : []} observations={observations} height={320}
              center={[event.centroid_lon, event.centroid_lat]} zoom={11} highlightEventId={event.event_id} />
            <EventTimeline observations={observations} />
          </div>
        </Panel>
        <Panel variant="section" title={live ? "FIRMS measurements" : "Demo measurements"} sub="Source fields as returned">
          {live ? <NasaObservationRows event={event} observations={observations} sourceLabel={sourceLabel} /> : (
            <p className="text-xs text-base-300">DEMO event: values are sample fixtures, not NASA measurements.</p>
          )}
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] font-semibold uppercase tracking-wider">
            <Link href={`/replay/${event.event_id}`} className="text-accent hover:text-accent-bright">Full replay →</Link>
          </div>
        </Panel>
      </div>
      {live && observations.length > 0 && (
        <Panel variant="section" title="NASA FIRMS observations forming this event" sub="Event → FIRMS observations → NASA source fields, exactly as stored. FIRMS confidence is a satellite detection attribute; it is not OrbiFlare risk.">
          <FirmsObservationsTable observations={observations} />
        </Panel>
      )}

      {/* ============================ 2 · CONTEXT ============================ */}
      <TierHeading n={2} label="Context" sub="Facility and historical context — spatial association only, never attribution" />
      <Panel variant="section" title="Facility context" sub="Nearby does not mean caused by">
        {live ? <FacilityContextSection ctx={facilityCtx} /> : (
          <>
            <DataRow label="Facility (demo)" value={facility ? facility.name : "none"} mono={false} />
            <DataRow label="Distance" value={event.facility_distance_km !== null ? `~${fmtNum(event.facility_distance_km)} km` : "—"} />
          </>
        )}
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] font-semibold uppercase tracking-wider">
          {facility && <Link href={`/thermal-twins/${facility.facility_id}`} className="text-accent hover:text-accent-bright">Thermal Twin →</Link>}
          {facility && <Link href={`/facilities/${facility.facility_id}`} className="text-accent hover:text-accent-bright">Facility →</Link>}
        </div>
      </Panel>
      <Panel variant="section" title="Historical reference context" sub="Curated historical records within 50 km — context only, not part of this event, not FIRMS detections">
        {nearIncidents.length === 0 ? (
          <p className="text-xs text-base-400">No historical reference incidents within 50 km of this event.</p>
        ) : (
          <ul className="divide-y divide-base-700/60">
            {nearIncidents.slice(0, 6).map(({ incident, distance_km }) => (
              <li key={incident.incident_id}>
                <Link href={`/incidents/${incident.incident_id}`} className="flex flex-wrap items-center justify-between gap-2 py-1.5 hover:text-accent">
                  <span className="text-xs text-base-100">{incident.name} <span className="text-base-400">· {incident.record_kind_label} · {incident.date}</span></span>
                  <span className="flex items-center gap-2 font-mono text-[11px] text-base-300">{fmtNum(distance_km)} km <HistoricalBadge compact /></span>
                </Link>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-2 text-[11px] text-base-500">Proximity to a historical record is not evidence of causation or recurrence.</p>
      </Panel>

      {/* ============================ 3 · BEHAVIOUR ============================ */}
      <TierHeading n={3} label="Behaviour" sub="Persistence, recurrence and deviation from what is normal at this facility" />
      <Panel variant="section" title={bView.twinTitle} sub="What is normal here, and what changed?">
        <BaselineBanner status={baseline} hasFacility={!!event.facility_id} contribution={risk?.deviation_contribution} cap={risk?.deviation_contribution_cap} />
        {thermal_twin && (
          <div className="mb-3 grid grid-cols-2 gap-2 text-[11px] text-base-400 md:grid-cols-4">
            <span>history <b className="font-mono text-base-100">{thermal_twin.historical_event_count}</b> events</span>
            <span>span <b className="font-mono text-base-100">{thermal_twin.history_start ? `${fmtDate(thermal_twin.history_start).split(",")[0]}…${fmtDate(thermal_twin.history_end).split(",")[0]}` : "—"}</b></span>
            <span>typical FRP <b className="font-mono text-base-100">{fmtNum(thermal_twin.normal_frp.median, 0)} MW</b></span>
            <span>typical persistence <b className="font-mono text-base-100">{fmtNum(thermal_twin.normal_persistence.median, 0)} obs</b></span>
          </div>
        )}
        {deviation && deviation.baseline_confidence !== "INSUFFICIENT" && deviation.intensity.status === "COMPUTED" && deviation.intensity.observed_value != null && deviation.intensity.expected_median != null && (
          <p className="mb-2 rounded border border-base-600 bg-base-800 px-2.5 py-1.5 font-mono text-xs text-base-100">
            Current peak FRP {fmtNum(deviation.intensity.observed_value, 1)} MW · facility baseline median {fmtNum(deviation.intensity.expected_median, 1)} MW · difference {deviation.intensity.observed_value - deviation.intensity.expected_median >= 0 ? "+" : ""}{fmtNum(deviation.intensity.observed_value - deviation.intensity.expected_median, 1)} MW ({bView.label.toLowerCase()})
          </p>
        )}
        {deviation ? <DeviationTable deviation={deviation} /> : (
          <StateBlock kind="unavailable" title="No facility baseline">
            {live ? "No facility context was found for this event, so there is no facility-level baseline to compare against. This is not evidence of a natural fire." : "This event has no facility Thermal Twin to compare against."}
          </StateBlock>
        )}
      </Panel>

      {/* ============================ 4 · ORBIFLARE ASSESSMENT ============================ */}
      <TierHeading n={4} label="OrbiFlare assessment" sub="ML evidence, risk score and severity — operational priority, not a confirmed fire" />
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Panel variant="section" title="Risk assessment" sub="Operational priority for analysts — not fire probability">
          {risk ? (
            <>
              <RiskExplanation risk={risk} />
              <ul className="mt-3 space-y-1.5">
                {[...risk.risk_factors].sort((a, b) => b.contribution - a.contribution).map((f) => (
                  <li key={f.name} title={f.explanation} className="grid grid-cols-[130px_1fr_44px] items-center gap-2 text-[11px]">
                    <span className="truncate font-mono text-base-300">{f.name}</span>
                    <span className="h-1.5 overflow-hidden rounded bg-base-700"><span className="block h-full bg-accent" style={{ width: `${Math.min(100, (f.contribution / Math.max(1, risk.risk_score)) * 100)}%` }} /></span>
                    <span className="text-right font-mono text-base-100">+{f.contribution.toFixed(1)}</span>
                  </li>
                ))}
              </ul>
              <ul className="mt-2 space-y-0.5">{risk.caveats.map((c, i) => <li key={i} className="text-[11px] text-base-500">{c}</li>)}</ul>
            </>
          ) : <StateBlock kind="unavailable" title="Risk unavailable" />}
        </Panel>

        <Panel variant="section" title="ML evidence" sub="One evidence source — separate from deviation, risk and NASA confidence">
          {ml_prediction ? (
            <>
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded border border-base-700 bg-base-800/60 p-2 text-center">
                  <div className="font-mono text-lg text-base-100">{(ml_prediction.p_persistent_industrial * 100).toFixed(0)}%</div>
                  <div className="text-[10px] uppercase tracking-wider text-base-400">Class A · persistent industrial</div>
                </div>
                <div className="rounded border border-base-700 bg-base-800/60 p-2 text-center">
                  <div className="font-mono text-lg text-base-100">{(ml_prediction.p_natural_candidate * 100).toFixed(0)}%</div>
                  <div className="text-[10px] uppercase tracking-wider text-base-400">Class B · natural/agri candidate</div>
                </div>
              </div>
              {ml_prediction.low_confidence && <p className="mt-2 text-xs font-medium text-sev-medium">Low confidence — anomaly-candidate signal only.</p>}
              <MlEvidenceNote />
              <p className="mt-2 text-[11px] leading-snug text-base-400">
                {ml_prediction.facility_context_state && ml_prediction.facility_context_state !== "USABLE"
                  ? "Facility information was not used by the model (no usable facility context); it ran without any facility-distance input. "
                  : ml_prediction.facility_context_state === "USABLE" ? "Facility distance was one of the model inputs. " : ""}
                Model {ml_prediction.model_version}. A class probability is <b className="text-base-200">not</b> fire probability and is not the risk score. <Link href="/model" className="text-accent hover:underline">Model limits →</Link>
              </p>
            </>
          ) : <StateBlock kind="unavailable" title="No ML result" />}
        </Panel>
      </div>

      <Panel variant="section" title="Why flagged?" sub="Every signal that moved this event up the queue — and every one that argues against it">
        {evidence ? <EvidenceStackView evidence={evidence} /> : <StateBlock kind="unavailable" title="Evidence unavailable" />}
      </Panel>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Panel variant="section" title="Alternative explanations" sub="Competing interpretations — not probabilities">
          {alternative_explanations ? (
            <div className="space-y-3">
              <div className="rounded border border-accent/30 bg-accent/5 p-2.5">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-accent">Primary hypothesis</div>
                <div className="mt-1 text-sm font-medium text-base-100">{alternative_explanations.primary_hypothesis.label}</div>
                <p className="mt-1 text-xs text-base-300">{alternative_explanations.primary_hypothesis.rationale}</p>
              </div>
              {alternative_explanations.alternatives.length > 0 && (
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-base-400">Alternatives</div>
                  <ul className="mt-1 space-y-1.5">
                    {alternative_explanations.alternatives.map((h, i) => (
                      <li key={i} className="text-xs text-base-300"><b className="font-medium text-base-100">{h.label}</b>{h.rationale && <span className="text-base-400"> — {h.rationale}</span>}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-wider text-base-400">Unknown / unresolved</div>
                <ul className="mt-1 space-y-1">{alternative_explanations.unknowns.map((u, i) => <li key={i} className="text-xs text-base-400">? {u}</li>)}</ul>
              </div>
            </div>
          ) : <StateBlock kind="unavailable" title="Unavailable" />}
        </Panel>
        <Panel variant="section" title="Risk trajectory" sub="How computed risk evolved over real observations (not a forecast)">
          {trajectory ? (
            <>
              <RiskTrajectoryChart trajectory={trajectory} />
              <p className="mt-1 text-xs text-base-300">{trajectory.explanation}</p>
            </>
          ) : <StateBlock kind="insufficient" title="Insufficient data" />}
        </Panel>
      </div>

      <Panel variant="section" title="Event replay" sub="Play the event through its actual observations">
        {replay && replay.frames.length > 0 ? <EventReplayPlayer replay={replay} event={event} facility={facility} /> : <StateBlock kind="insufficient" title="Not enough observations to replay" />}
      </Panel>

      {/* ============================ 5 · LIMITATIONS ============================ */}
      <TierHeading n={5} label="Limitations" sub="What this event's evidence cannot support" />
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Panel variant="section" title="For this event">
          <ul className="space-y-1.5 text-xs text-base-200" data-testid="limitations">
            {limitations.map((l, i) => <li key={i} className="flex gap-2"><span className="text-sev-medium">△</span><span>{l}</span></li>)}
          </ul>
          <div className="mt-3"><UncertaintyNotice notes={uncertainty_notes} /></div>
        </Panel>
        <Panel variant="section" title="Operator actions" sub="Human-controlled and audited. The agent can never resolve an event.">
          <OperatorActionsSection eventId={event.event_id} initialState={operator_state} initialHistory={operator_history} />
        </Panel>
      </div>
    </div>
  );
}
