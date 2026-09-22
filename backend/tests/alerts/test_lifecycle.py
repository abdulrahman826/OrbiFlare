import pytest

from app.alerts import lifecycle
from app.model.schemas import AlertState
from app.storage import repositories as repo
from app.storage.database import Base, engine


def _make_event(db, event_id="E1"):
    from datetime import datetime
    from app.model.schemas import ThermalEvent
    e = ThermalEvent(event_id=event_id, first_detected=datetime(2025, 1, 1), last_detected=datetime(2025, 1, 1),
                      duration_hours=1, observation_count=1, centroid_lat=22.3, centroid_lon=69.8,
                      source_observation_ids=["o1"])
    repo.upsert_event(db, e)
    db.commit()
    return e


def test_valid_transition_detected_to_validating(db_session):
    _make_event(db_session)
    alert = lifecycle.transition(db_session, "E1", AlertState.VALIDATING, actor="operator")
    assert alert.state == "VALIDATING"


def test_invalid_transition_raises(db_session):
    _make_event(db_session)
    with pytest.raises(lifecycle.InvalidTransitionError):
        lifecycle.transition(db_session, "E1", AlertState.EXTINGUISHED, actor="operator")


def test_full_valid_lifecycle_path(db_session):
    _make_event(db_session)
    for state in (AlertState.VALIDATING, AlertState.ALERTED, AlertState.ESCALATED, AlertState.MONITORING, AlertState.EXTINGUISHED):
        alert = lifecycle.transition(db_session, "E1", state, actor="operator")
        assert alert.state == state.value


def test_agent_can_never_extinguish_an_event(db_session):
    _make_event(db_session)
    lifecycle.transition(db_session, "E1", AlertState.VALIDATING, actor="operator")
    with pytest.raises(lifecycle.ForbiddenActorTransitionError):
        lifecycle.transition(db_session, "E1", AlertState.EXTINGUISHED, actor="agent")


def test_transitions_are_audited(db_session):
    _make_event(db_session)
    lifecycle.transition(db_session, "E1", AlertState.VALIDATING, actor="operator", note="looks unusual")
    history = lifecycle.get_history(db_session, "E1")
    assert len(history) == 1
    assert history[0].to_state == "VALIDATING"
    assert history[0].note == "looks unusual"
