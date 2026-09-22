from app.intelligence.investigation import get_investigation
from app.intelligence.pipeline import run_full_pipeline
from app.storage import repositories as repo


def test_full_demo_pipeline_produces_coherent_state(db_session):
    result = run_full_pipeline(db_session, mode="demo")
    assert result["facilities"] == 3
    assert result["events"] > 10
    assert result["thermal_twins"] == 3

    events = [repo.event_to_schema(r) for r in repo.list_events(db_session)]
    assert all(e.risk_score is not None for e in events)
    assert all(e.severity is not None for e in events)

    # The flagship Alpha event should be the highest-risk event overall.
    top = max(events, key=lambda e: e.risk_score or 0)
    assert top.facility_id == "FAC-REF-ALPHA"
    assert top.severity.value in ("HIGH", "CRITICAL")
    assert top.trajectory_direction.value == "ESCALATING"


def test_gamma_facility_has_insufficient_baseline(db_session):
    run_full_pipeline(db_session, mode="demo")
    twin = repo.get_thermal_twin(db_session, "FAC-CHEM-GAMMA")
    assert twin is not None
    assert twin.baseline_confidence.value == "INSUFFICIENT"


def test_investigation_is_fully_traceable_for_flagship_event(db_session):
    run_full_pipeline(db_session, mode="demo")
    events = [repo.event_to_schema(r) for r in repo.list_events(db_session)]
    top = max(events, key=lambda e: e.risk_score or 0)
    inv = get_investigation(db_session, top.event_id)
    assert inv is not None
    assert inv.facility is not None
    assert inv.thermal_twin is not None
    assert inv.deviation is not None
    assert inv.evidence is not None
    assert inv.risk is not None
    assert inv.trajectory is not None
    assert len(inv.observations) == top.observation_count
