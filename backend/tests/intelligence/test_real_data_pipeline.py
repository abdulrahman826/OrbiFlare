"""End-to-end real-data path: FIRMS CSV rows -> ThermalObservation ->
cleaning -> Living Thermal Event -> facility enrichment -> Thermal Twin ->
Deviation -> ML -> Evidence -> Risk -> Trajectory -> persisted Investigation.

This does NOT use app.ingestion.demo_fixtures anywhere -- every observation
here is normalized from FIRMS-shaped rows via the same normalize_firms_row
used by the live/local FIRMS adapters, so this test proves the real-data
pipeline (not just the demo path) actually produces a coherent, traceable
investigation, and that provenance (source=FIRMS, is_demo=False) survives
end to end.
"""
from __future__ import annotations

from app.intelligence import classification
from app.intelligence import evidence as evidence_mod
from app.intelligence import risk as risk_mod
from app.intelligence.deviation import compute_deviation
from app.intelligence.events import form_events
from app.intelligence.facility_enrichment import enrich_events
from app.intelligence.investigation import get_investigation
from app.intelligence.pipeline import build_thermal_twins_stage, persist
from app.intelligence.trajectory import compute_trajectory
from app.model.schemas import DataSource, Facility, Sensor
from app.preprocessing.cleaning import deduplicate
from app.preprocessing.normalization import normalize_firms_row
from app.storage import repositories as repo


def _firms_row(lat: str, lon: str, date: str, time: str, frp: str = "40.0", bt: str = "335.0") -> dict:
    return {
        "latitude": lat, "longitude": lon, "acq_date": date, "acq_time": time,
        "frp": frp, "bright_ti4": bt, "bright_ti5": "301.0", "confidence": "n", "daynight": "N",
    }


def _build_real_observations():
    rows = [
        _firms_row("22.3200", "69.8500", "2025-02-01", "1830"),
        _firms_row("22.3202", "69.8501", "2025-02-01", "1900", frp="55.0"),
        _firms_row("22.3199", "69.8499", "2025-02-01", "1930", frp="61.0"),
    ]
    observations = []
    for row in rows:
        obs, issues = normalize_firms_row(row, Sensor.VIIRS)
        assert obs is not None, issues
        observations.append(obs)
    deduped, dup_count = deduplicate(observations)
    assert dup_count == 0
    return deduped


def test_firms_observations_form_a_real_living_thermal_event():
    observations = _build_real_observations()
    assert all(o.source == DataSource.FIRMS for o in observations)

    events = form_events(observations)
    assert len(events) == 1
    event = events[0]
    assert event.observation_count == 3
    assert event.is_demo is False
    assert event.peak_frp == 61.0


def test_real_data_pipeline_produces_traceable_investigation(db_session):
    observations = _build_real_observations()
    events = form_events(observations)

    facility = Facility(
        facility_id="FAC-REAL-TEST-1", name="Real Test Facility", facility_type="oil_refinery",
        latitude=22.3200, longitude=69.8500, source="OSM", is_demo=False,
    )
    events = enrich_events(events, [facility])
    assert events[0].facility_id == "FAC-REAL-TEST-1"

    twins, _current, obs_by_event = build_thermal_twins_stage(events, observations)
    deviations = {e.event_id: compute_deviation(e, twins.get(e.facility_id), obs_by_event.get(e.event_id, [])) for e in events}
    predictions = {}
    for e in events:
        pred = classification.classify_event(e)
        predictions[e.event_id] = pred
        e.classification, e.ml_p_industrial = pred.predicted_class, pred.p_persistent_industrial
        e.ml_p_natural, e.ml_anomaly_low_confidence = pred.p_natural_candidate, pred.low_confidence

    facilities_by_id = {facility.facility_id: facility}
    evidence_stacks = {e.event_id: evidence_mod.build_evidence_stack(e, deviations[e.event_id], predictions[e.event_id], facilities_by_id.get(e.facility_id)) for e in events}
    risks = {}
    for e in events:
        r = risk_mod.compute_risk(e, deviations[e.event_id], predictions[e.event_id], facility_present=e.facility_id is not None)
        risks[e.event_id] = r
        e.risk_score, e.severity = r.risk_score, r.severity
    trajectories = {}
    for e in events:
        twin = twins.get(e.facility_id)
        traj, _ = compute_trajectory(obs_by_event.get(e.event_id, []), twin, e.facility_id, e.facility_distance_km, e.event_id)
        trajectories[e.event_id] = traj
        e.trajectory_direction = traj.direction

    persist(db_session, [facility], events, observations, twins, deviations, evidence_stacks, risks, trajectories)

    event_id = events[0].event_id
    stored_event = repo.event_to_schema(repo.get_event(db_session, event_id))
    assert stored_event.is_demo is False
    assert stored_event.risk_score is not None
    assert stored_event.severity is not None

    # Facility is brand new -- this event is its only history, so the twin
    # correctly reports INSUFFICIENT rather than fabricating a baseline.
    twin = repo.get_thermal_twin(db_session, "FAC-REAL-TEST-1")
    assert twin is not None
    assert twin.baseline_confidence.value == "INSUFFICIENT"

    deviation = repo.get_deviation(db_session, event_id)
    assert deviation is not None
    assert deviation.baseline_confidence.value == "INSUFFICIENT"

    inv = get_investigation(db_session, event_id)
    assert inv is not None
    assert inv.facility is not None
    assert inv.risk is not None
    assert inv.evidence is not None
    assert len(inv.observations) == 3
    assert all(o.source == DataSource.FIRMS for o in inv.observations)
