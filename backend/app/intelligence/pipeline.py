"""Production-like pipeline service.

Each stage is an independently callable, independently testable function --
this module is the orchestrator, not a single 2000-line function. Run it end
to end with run_full_pipeline(), or call stages individually (e.g. from a
notebook or a partial re-run script).

Baseline-leakage rule: for each facility, the CHRONOLOGICALLY LAST event is
always treated as "the current event under investigation" and excluded from
that facility's own thermal twin -- a twin must never be built from the
event it will be compared against.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.ingestion.demo_fixtures import generate_demo_dataset
from app.intelligence import classification
from app.intelligence import evidence as evidence_mod
from app.intelligence import risk as risk_mod
from app.intelligence.deviation import compute_deviation
from app.intelligence.events import form_events
from app.intelligence.facility_enrichment import enrich_events
from app.intelligence.thermal_twin import build_thermal_twin
from app.intelligence.trajectory import compute_trajectory
from app.model.schemas import Facility, ThermalEvent, ThermalObservation
from app.preprocessing.cleaning import deduplicate
from app.storage import repositories as repo

logger = logging.getLogger("orbiflare.pipeline")
settings = get_settings()


def ingest(mode: str = "demo") -> tuple[list[Facility], list[ThermalObservation]]:
    if mode == "demo":
        return generate_demo_dataset()
    raise ValueError(
        f"mode={mode!r} requires real FIRMS/facility data -- use scripts/ingest_firms.py to populate "
        f"data/raw/firms and pass observations explicitly, then call the remaining stages directly."
    )


def clean(observations: list[ThermalObservation]) -> list[ThermalObservation]:
    """Batch-level dedup. Per-row validation already happened during
    normalization (app.preprocessing.normalization / .validation)."""
    deduped, dup_count = deduplicate(observations)
    if dup_count:
        logger.info("clean(): removed %d duplicate observation(s)", dup_count)
    return deduped


def feature_engineer(observations: list[ThermalObservation]) -> list[ThermalObservation]:
    """Per-observation feature engineering placeholder. Real feature
    construction for the ML layer is event-level and happens in
    app.intelligence.classification.build_feature_vector at classify() time,
    since features like persistence/facility-distance only exist once
    observations are grouped into events with facility context."""
    return observations


def form_events_stage(observations: list[ThermalObservation]) -> list[ThermalEvent]:
    return form_events(observations)


def enrich_facilities_stage(events: list[ThermalEvent], facilities: list[Facility]) -> list[ThermalEvent]:
    return enrich_events(events, facilities)


def _observations_by_event(events: list[ThermalEvent], observations: list[ThermalObservation]) -> dict[str, list[ThermalObservation]]:
    by_id = {o.observation_id: o for o in observations}
    return {e.event_id: [by_id[oid] for oid in e.source_observation_ids if oid in by_id] for e in events}


def build_thermal_twins_stage(events: list[ThermalEvent], observations: list[ThermalObservation]):
    obs_by_event = _observations_by_event(events, observations)
    events_by_facility: dict[str, list[ThermalEvent]] = {}
    for e in events:
        if e.facility_id:
            events_by_facility.setdefault(e.facility_id, []).append(e)

    twins = {}
    current_event_by_facility = {}
    for facility_id, facility_events in events_by_facility.items():
        facility_events_sorted = sorted(facility_events, key=lambda e: e.first_detected)
        current_event = facility_events_sorted[-1]
        historical = facility_events_sorted[:-1]
        current_event_by_facility[facility_id] = current_event.event_id
        twins[facility_id] = build_thermal_twin(facility_id, historical, obs_by_event)
    return twins, current_event_by_facility, obs_by_event


def calculate_deviations_stage(events: list[ThermalEvent], twins: dict, obs_by_event: dict):
    deviations = {}
    for e in events:
        twin = twins.get(e.facility_id) if e.facility_id else None
        deviations[e.event_id] = compute_deviation(e, twin, obs_by_event.get(e.event_id, []))
    return deviations


def classify_stage(events: list[ThermalEvent]):
    predictions = {}
    for e in events:
        pred = classification.classify_event(e)
        predictions[e.event_id] = pred
        e.classification = pred.predicted_class
        e.ml_p_industrial = pred.p_persistent_industrial
        e.ml_p_natural = pred.p_natural_candidate
        e.ml_anomaly_low_confidence = pred.low_confidence
    return predictions


def build_evidence_stage(events: list[ThermalEvent], deviations: dict, predictions: dict, facilities_by_id: dict):
    stacks = {}
    for e in events:
        facility = facilities_by_id.get(e.facility_id) if e.facility_id else None
        stacks[e.event_id] = evidence_mod.build_evidence_stack(e, deviations.get(e.event_id), predictions.get(e.event_id), facility)
    return stacks


def calculate_risk_stage(events: list[ThermalEvent], deviations: dict, predictions: dict):
    risks = {}
    for e in events:
        r = risk_mod.compute_risk(e, deviations.get(e.event_id), predictions.get(e.event_id), facility_present=e.facility_id is not None)
        risks[e.event_id] = r
        e.risk_score = r.risk_score
        e.severity = r.severity
    return risks


def calculate_trajectory_stage(events: list[ThermalEvent], twins: dict, obs_by_event: dict):
    trajectories = {}
    for e in events:
        twin = twins.get(e.facility_id) if e.facility_id else None
        traj, _ = compute_trajectory(obs_by_event.get(e.event_id, []), twin, e.facility_id, e.facility_distance_km, e.event_id)
        trajectories[e.event_id] = traj
        e.trajectory_direction = traj.direction
    return trajectories


def persist(
    db: Session, facilities: list[Facility], events: list[ThermalEvent], observations: list[ThermalObservation],
    twins: dict, deviations: dict, evidence_stacks: dict, risks: dict, trajectories: dict,
) -> None:
    for f in facilities:
        repo.upsert_facility(db, f)
    repo.bulk_insert_observations(db, observations)
    for e in events:
        repo.upsert_event(db, e)
        repo.assign_observations_to_event(db, e.event_id, e.source_observation_ids)
    for facility_id, twin in twins.items():
        repo.upsert_thermal_twin(db, twin)
    for event_id, d in deviations.items():
        repo.upsert_deviation(db, d)
    for event_id, ev in evidence_stacks.items():
        repo.upsert_evidence(db, ev)
    for event_id, r in risks.items():
        repo.upsert_risk(db, r)
    for event_id, traj in trajectories.items():
        repo.replace_trajectory_points(db, event_id, traj.points)
    for e in events:
        repo.get_or_create_alert(db, e.event_id)
    db.commit()


def run_full_pipeline(db: Session, mode: str = "demo") -> dict:
    facilities, raw_observations = ingest(mode)
    observations = clean(raw_observations)
    observations = feature_engineer(observations)
    events = form_events_stage(observations)
    events = enrich_facilities_stage(events, facilities)
    twins, _current_by_facility, obs_by_event = build_thermal_twins_stage(events, observations)
    deviations = calculate_deviations_stage(events, twins, obs_by_event)
    predictions = classify_stage(events)
    facilities_by_id = {f.facility_id: f for f in facilities}
    evidence_stacks = build_evidence_stage(events, deviations, predictions, facilities_by_id)
    risks = calculate_risk_stage(events, deviations, predictions)
    trajectories = calculate_trajectory_stage(events, twins, obs_by_event)

    persist(db, facilities, events, observations, twins, deviations, evidence_stacks, risks, trajectories)

    return {
        "facilities": len(facilities), "observations": len(observations), "events": len(events),
        "thermal_twins": len(twins), "mode": mode,
    }
