from datetime import datetime

from app.intelligence.evidence import build_evidence_stack
from app.model.schemas import (
    BaselineConfidence,
    Deviation,
    DeviationStatus,
    DimensionDeviation,
    EvidenceDirection,
    Facility,
    MLClass,
    MLPrediction,
    ThermalEvent,
)


def _dim(status=DeviationStatus.COMPUTED, notable=False, significant=False):
    return DimensionDeviation(dimension="x", status=status, is_notable=notable, is_significant=significant, explanation="explanation text")


def _event():
    return ThermalEvent(event_id="E1", first_detected=datetime(2025, 1, 1), last_detected=datetime(2025, 1, 1),
                         duration_hours=1, observation_count=1, centroid_lat=22.3, centroid_lon=69.8,
                         facility_id="F1", facility_distance_km=1.2, source_observation_ids=["a"])


def test_significant_deviation_dimensions_become_supporting_evidence():
    deviation = Deviation(
        event_id="E1", baseline_confidence=BaselineConfidence.ESTABLISHED,
        intensity=_dim(significant=True), persistence=_dim(significant=True), duration=_dim(),
        temporal=_dim(), spatial=_dim(), recurrence=_dim(), overall_deviation_score=60.0,
    )
    ml = MLPrediction(event_id="E1", p_persistent_industrial=0.8, p_natural_candidate=0.2,
                       predicted_class=MLClass.PERSISTENT_INDUSTRIAL, low_confidence=False, model_version="v1")
    facility = Facility(facility_id="F1", name="Plant", facility_type="refinery", latitude=22.3, longitude=69.8)
    stack = build_evidence_stack(_event(), deviation, ml, facility)
    assert len(stack.supporting_evidence) >= 2
    assert any(i.direction == EvidenceDirection.SUPPORTING and "intensity" in i.name for i in stack.supporting_evidence)


def test_non_notable_dimensions_become_contradicting_context():
    deviation = Deviation(
        event_id="E1", baseline_confidence=BaselineConfidence.ESTABLISHED,
        intensity=_dim(), persistence=_dim(), duration=_dim(), temporal=_dim(), spatial=_dim(), recurrence=_dim(),
        overall_deviation_score=0.0,
    )
    stack = build_evidence_stack(_event(), deviation, None, None)
    assert len(stack.contradicting_evidence) == 6


def test_insufficient_baseline_dimensions_are_unavailable_not_fabricated():
    deviation = Deviation(
        event_id="E1", baseline_confidence=BaselineConfidence.INSUFFICIENT,
        intensity=_dim(status=DeviationStatus.INSUFFICIENT_BASELINE),
        persistence=_dim(status=DeviationStatus.INSUFFICIENT_BASELINE),
        duration=_dim(status=DeviationStatus.INSUFFICIENT_BASELINE),
        temporal=_dim(status=DeviationStatus.INSUFFICIENT_BASELINE),
        spatial=_dim(status=DeviationStatus.INSUFFICIENT_BASELINE),
        recurrence=_dim(status=DeviationStatus.INSUFFICIENT_BASELINE),
        overall_deviation_score=0.0,
    )
    stack = build_evidence_stack(_event(), deviation, None, None)
    assert len(stack.unavailable_evidence) >= 6


def test_facility_proximity_is_uncertain_not_supporting_causation():
    deviation = Deviation(
        event_id="E1", baseline_confidence=BaselineConfidence.ESTABLISHED,
        intensity=_dim(), persistence=_dim(), duration=_dim(), temporal=_dim(), spatial=_dim(), recurrence=_dim(),
        overall_deviation_score=0.0,
    )
    facility = Facility(facility_id="F1", name="Plant", facility_type="refinery", latitude=22.3, longitude=69.8)
    stack = build_evidence_stack(_event(), deviation, None, facility)
    facility_items = [i for i in stack.uncertain_evidence if i.category.value == "FACILITY"]
    assert len(facility_items) == 1
    assert "does not" in facility_items[0].explanation.lower()


def test_correlated_evidence_is_flagged_in_correlation_notes():
    deviation = Deviation(
        event_id="E1", baseline_confidence=BaselineConfidence.ESTABLISHED,
        intensity=_dim(notable=True), persistence=_dim(), duration=_dim(), temporal=_dim(), spatial=_dim(), recurrence=_dim(),
        overall_deviation_score=20.0,
    )
    ml = MLPrediction(event_id="E1", p_persistent_industrial=0.8, p_natural_candidate=0.2,
                       predicted_class=MLClass.PERSISTENT_INDUSTRIAL, low_confidence=False, model_version="v1")
    stack = build_evidence_stack(_event(), deviation, ml, None)
    assert len(stack.correlation_notes) >= 1
