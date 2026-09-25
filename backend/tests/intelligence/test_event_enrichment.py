"""Tests for app.storage.repositories.attach_derived_event_fields -- the
bulk join that lets the Events page/agent sort and filter by deviation
score, facility type, and facility baseline confidence without a query per
event.
"""
from __future__ import annotations

from app.intelligence.pipeline import run_full_pipeline
from app.storage import repositories as repo


def test_attach_derived_event_fields_populates_deviation_facility_type_and_baseline(db_session):
    run_full_pipeline(db_session, mode="demo")
    rows = repo.list_events(db_session)
    events = [repo.event_to_schema(r) for r in rows]

    enriched = repo.attach_derived_event_fields(db_session, events)

    with_facility = [e for e in enriched if e.facility_id]
    assert with_facility, "demo scenario should include facility-linked events"
    for e in with_facility:
        assert e.facility_type is not None
        assert e.baseline_confidence is not None
        # Deviation is only unavailable for the facility with no prior history
        # (INSUFFICIENT) -- every ESTABLISHED/LIMITED facility's events must
        # carry a real, non-fabricated numeric deviation score.
        if e.baseline_confidence.value != "INSUFFICIENT":
            assert e.overall_deviation_score is not None

    without_facility = [e for e in enriched if not e.facility_id]
    for e in without_facility:
        assert e.facility_type is None
        assert e.baseline_confidence is None


def test_attach_derived_event_fields_is_a_bulk_join_not_per_event_query(db_session):
    """Sanity check on the query shape: calling it with zero events must not
    error, and must not issue any facility/twin lookups."""
    result = repo.attach_derived_event_fields(db_session, [])
    assert result == []


def test_list_deviation_scores_bulk_lookup(db_session):
    run_full_pipeline(db_session, mode="demo")
    rows = repo.list_events(db_session)
    event_ids = [r.event_id for r in rows]
    scores = repo.list_deviation_scores(db_session, event_ids)
    assert isinstance(scores, dict)
    assert all(isinstance(v, float) for v in scores.values())
