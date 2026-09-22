"""Investigation service -- aggregates event + observations + facility +
thermal twin + deviation + ML + evidence + alternative explanations + risk +
trajectory + operator state into the single payload the Investigation UI
(and the agent) consume. Precomputed artifacts (twin/deviation/evidence/
risk) are read from storage -- written by scripts/rebuild_pipeline.py or the
ingestion routes -- so a request never re-runs the whole pipeline; only
trajectory/replay/alternative-explanations are cheap enough to compute
on-demand from the event's own observations.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.intelligence.alternative_explanations import build_alternative_explanations
from app.intelligence.trajectory import compute_trajectory
from app.model.schemas import AlertState, Investigation
from app.storage import repositories as repo


def get_investigation(db: Session, event_id: str) -> Investigation | None:
    event_row = repo.get_event(db, event_id)
    if event_row is None:
        return None
    event = repo.event_to_schema(event_row)

    obs_rows = repo.list_observations_for_event(db, event_id)
    observations = [repo.observation_to_schema(r) for r in obs_rows]

    facility = None
    twin = None
    if event.facility_id:
        facility_row = repo.get_facility(db, event.facility_id)
        facility = repo.facility_to_schema(facility_row) if facility_row else None
        twin = repo.get_thermal_twin(db, event.facility_id)

    deviation = repo.get_deviation(db, event_id)
    risk = repo.get_risk(db, event_id)
    evidence = repo.get_evidence(db, event_id)

    ml = None
    if event.ml_p_industrial is not None:
        from app.model.schemas import MLClass, MLPrediction
        ml = MLPrediction(
            event_id=event_id, p_persistent_industrial=event.ml_p_industrial or 0.0,
            p_natural_candidate=event.ml_p_natural or 0.0,
            predicted_class=event.classification or MLClass.NATURAL_CANDIDATE,
            low_confidence=event.ml_anomaly_low_confidence, model_version="rf-proxy-v1",
        )

    alternatives = build_alternative_explanations(event, deviation, ml, facility)
    trajectory, _ = compute_trajectory(observations, twin, event.facility_id, event.facility_distance_km, event_id)

    uncertainty_notes = [
        "Satellite thermal-anomaly resolution limits precise source attribution.",
        "Facility proximity is contextual and does not establish causation.",
        "No ground-truth visual confirmation is available for this event.",
    ]
    if twin is None or deviation is None or deviation.baseline_confidence.value == "INSUFFICIENT":
        uncertainty_notes.insert(0, "Facility baseline is INSUFFICIENT -- behavioural comparisons are limited or unavailable.")

    alert_row = repo.get_or_create_alert(db, event_id)
    history_rows = repo.list_alert_history(db, event_id)
    operator_history = [
        {"from_state": h.from_state, "to_state": h.to_state, "actor": h.actor, "note": h.note,
         "changed_at": h.changed_at.isoformat()}
        for h in history_rows
    ]

    return Investigation(
        event=event, observations=observations, facility=facility, thermal_twin=twin, deviation=deviation,
        ml_prediction=ml, evidence=evidence, alternative_explanations=alternatives, risk=risk,
        trajectory=trajectory, uncertainty_notes=uncertainty_notes,
        operator_state=AlertState(alert_row.state), operator_history=operator_history,
    )
