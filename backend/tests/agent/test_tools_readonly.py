from datetime import datetime

from app.agent import tools
from app.model.schemas import Severity, ThermalEvent
from app.storage import repositories as repo


def _seed_event(db, event_id="E1", severity=Severity.HIGH, risk=70.0):
    e = ThermalEvent(event_id=event_id, first_detected=datetime(2025, 1, 1), last_detected=datetime(2025, 1, 1),
                      duration_hours=1, observation_count=1, centroid_lat=22.3, centroid_lon=69.8,
                      severity=severity, risk_score=risk, source_observation_ids=["o1"])
    repo.upsert_event(db, e)
    db.commit()


def test_tool_registry_only_contains_read_only_names():
    forbidden_substrings = ("delete", "update", "set_", "write", "mutate", "transition")
    for name in tools.TOOL_REGISTRY:
        assert not any(s in name for s in forbidden_substrings), f"{name} looks like a mutating tool"


def test_list_events_reads_real_seeded_data(db_session):
    _seed_event(db_session)
    result = tools.list_events(db_session)
    assert len(result) == 1
    assert result[0]["event_id"] == "E1"


def test_get_event_returns_none_for_unknown_id(db_session):
    assert tools.get_event(db_session, "NOPE") is None


def test_list_high_risk_events_filters_by_severity(db_session):
    _seed_event(db_session, "E1", severity=Severity.HIGH, risk=70)
    _seed_event(db_session, "E2", severity=Severity.LOW, risk=10)
    db_session.commit()
    result = tools.list_high_risk_events(db_session)
    assert {r["event_id"] for r in result} == {"E1"}


def test_tools_do_not_mutate_database_state(db_session):
    _seed_event(db_session)
    before = repo.get_event(db_session, "E1").risk_score
    tools.get_investigation_tool(db_session, "E1")
    tools.list_events(db_session)
    tools.list_high_risk_events(db_session)
    after = repo.get_event(db_session, "E1").risk_score
    assert before == after
