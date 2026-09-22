from datetime import datetime

from app.agent import tools
from app.model.schemas import (
    BaselineConfidence,
    Deviation,
    DeviationStatus,
    DimensionDeviation,
    Facility,
    Severity,
    ThermalEvent,
    TrajectoryDirection,
)
from app.storage import repositories as repo


def _dim(name: str, status=DeviationStatus.COMPUTED) -> DimensionDeviation:
    return DimensionDeviation(dimension=name, status=status, explanation=f"{name} explanation")


def _seed_facility(db, facility_id="FAC-1", facility_type="oil_refinery", region="Gujarat"):
    repo.upsert_facility(db, Facility(
        facility_id=facility_id, name=f"Facility {facility_id}", facility_type=facility_type,
        latitude=22.3, longitude=69.8, source="DEMO", region=region, is_demo=True,
    ))


def _seed_event(db, event_id, severity=Severity.HIGH, risk=70.0, obs_count=3, status="DETECTED",
                 trajectory=TrajectoryDirection.STABLE, facility_id=None, peak_frp=50.0):
    e = ThermalEvent(
        event_id=event_id, first_detected=datetime(2025, 1, 1), last_detected=datetime(2025, 1, 1),
        duration_hours=2.0, observation_count=obs_count, centroid_lat=22.3, centroid_lon=69.8,
        severity=severity, risk_score=risk, status=status, trajectory_direction=trajectory,
        facility_id=facility_id, peak_frp=peak_frp, source_observation_ids=[f"{event_id}-o1"],
    )
    repo.upsert_event(db, e)
    return e


def test_get_event_statistics_computed_from_real_records(db_session):
    _seed_facility(db_session)
    _seed_event(db_session, "E1", severity=Severity.CRITICAL, risk=90, obs_count=8, facility_id="FAC-1", peak_frp=100.0)
    _seed_event(db_session, "E2", severity=Severity.LOW, risk=10, obs_count=2, peak_frp=5.0)
    db_session.commit()

    stats = tools.get_event_statistics(db_session)
    assert stats["total_events"] == 2
    assert stats["critical_events"] == 1
    assert stats["high_risk_events"] == 1
    assert stats["persistent_events"] == 1  # only E1 has >= 6 observations
    assert stats["peak_frp"] == 100.0
    assert stats["average_frp"] == 52.5
    assert stats["events_by_facility_type"] == {"oil_refinery": 1}


def test_list_persistent_events_uses_observation_count_threshold(db_session):
    _seed_event(db_session, "E1", obs_count=6)
    _seed_event(db_session, "E2", obs_count=2)
    db_session.commit()

    result = tools.list_persistent_events(db_session)
    assert {r["event_id"] for r in result} == {"E1"}


def test_list_persistent_events_excludes_extinguished(db_session):
    _seed_event(db_session, "E1", obs_count=9, status="EXTINGUISHED")
    db_session.commit()

    assert tools.list_persistent_events(db_session) == []


def test_facility_event_frequency_ranks_by_persistent_count(db_session):
    _seed_facility(db_session, "FAC-1")
    _seed_facility(db_session, "FAC-2")
    _seed_event(db_session, "E1", obs_count=8, facility_id="FAC-1")
    _seed_event(db_session, "E2", obs_count=1, facility_id="FAC-1")
    _seed_event(db_session, "E3", obs_count=7, facility_id="FAC-2")
    _seed_event(db_session, "E4", obs_count=9, facility_id="FAC-2")
    db_session.commit()

    ranking = tools.facility_event_frequency(db_session)
    assert ranking[0]["facility_id"] == "FAC-2"
    assert ranking[0]["persistent_event_count"] == 2
    assert ranking[1]["facility_id"] == "FAC-1"
    assert ranking[1]["persistent_event_count"] == 1


def test_get_facility_statistics_unknown_facility_returns_none(db_session):
    assert tools.get_facility_statistics(db_session, "FAC-NOPE") is None


def test_get_facility_statistics_aggregates_real_events(db_session):
    _seed_facility(db_session, "FAC-1")
    _seed_event(db_session, "E1", severity=Severity.HIGH, obs_count=8, facility_id="FAC-1")
    db_session.commit()

    stats = tools.get_facility_statistics(db_session, "FAC-1")
    assert stats["total_events"] == 1
    assert stats["high_risk_events"] == 1
    assert stats["persistent_events"] == 1
    assert stats["baseline_confidence"] == "INSUFFICIENT"  # no thermal twin computed in this test


def test_get_risk_statistics_computes_distribution(db_session):
    _seed_event(db_session, "E1", severity=Severity.HIGH, risk=70)
    _seed_event(db_session, "E2", severity=Severity.LOW, risk=10)
    db_session.commit()

    stats = tools.get_risk_statistics(db_session)
    assert stats["scored_event_count"] == 2
    assert stats["average_risk_score"] == 40.0
    assert stats["peak_risk_score"] == 70.0
    assert stats["severity_distribution"] == {"HIGH": 1, "LOW": 1}


def test_compare_event_to_baseline_reports_insufficient_when_no_deviation_stored(db_session):
    _seed_event(db_session, "E1", facility_id="FAC-1")
    db_session.commit()

    result = tools.compare_event_to_baseline(db_session, "E1")
    assert result["baseline_status"] == "INSUFFICIENT_BASELINE"
    assert result["message"] == "Insufficient baseline data."


def test_compare_event_to_baseline_never_fabricates_missing_dimension_values(db_session):
    _seed_event(db_session, "E1", facility_id="FAC-1")
    db_session.commit()
    deviation = Deviation(
        event_id="E1", facility_id="FAC-1", baseline_confidence=BaselineConfidence.ESTABLISHED,
        intensity=_dim("intensity"), persistence=_dim("persistence"), duration=_dim("duration"),
        temporal=_dim("temporal"), spatial=_dim("spatial"), recurrence=_dim("recurrence"),
        overall_deviation_score=42.0,
    )
    repo.upsert_deviation(db_session, deviation)
    db_session.commit()

    result = tools.compare_event_to_baseline(db_session, "E1")
    assert result["baseline_status"] == "ESTABLISHED"
    assert result["overall_deviation_score"] == 42.0
    assert result["dimensions"]["intensity"]["normal"] is None  # not fabricated -- genuinely absent
    assert result["dimensions"]["intensity"]["current"] is None


def test_compare_event_to_baseline_unknown_event_returns_none(db_session):
    assert tools.compare_event_to_baseline(db_session, "EVT-NOPE") is None
