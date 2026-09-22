from datetime import datetime

from app.intelligence.risk import compute_risk
from app.model.schemas import BaselineConfidence, Deviation, DeviationStatus, DimensionDeviation, MLClass, MLPrediction, Severity, ThermalEvent


def _dim(notable=False, significant=False):
    return DimensionDeviation(dimension="x", status=DeviationStatus.COMPUTED, is_notable=notable, is_significant=significant, explanation="e")


def _event(**overrides):
    base = dict(event_id="E1", first_detected=datetime(2025, 1, 1), last_detected=datetime(2025, 1, 1),
                duration_hours=1, observation_count=2, peak_frp=30.0, centroid_lat=22.3, centroid_lon=69.8,
                source_observation_ids=["a", "b"])
    base.update(overrides)
    return ThermalEvent(**base)


def test_risk_is_deterministic_for_identical_inputs():
    event = _event()
    deviation = Deviation(event_id="E1", baseline_confidence=BaselineConfidence.ESTABLISHED,
                           intensity=_dim(), persistence=_dim(), duration=_dim(), temporal=_dim(), spatial=_dim(), recurrence=_dim(),
                           overall_deviation_score=10.0)
    r1 = compute_risk(event, deviation, None, facility_present=True)
    r2 = compute_risk(event, deviation, None, facility_present=True)
    assert r1.risk_score == r2.risk_score
    assert r1.severity == r2.severity


def test_high_deviation_and_intensity_yield_high_or_critical_severity():
    event = _event(peak_frp=200.0, duration_hours=6.0, observation_count=12)
    deviation = Deviation(event_id="E1", baseline_confidence=BaselineConfidence.ESTABLISHED,
                           intensity=_dim(significant=True), persistence=_dim(significant=True),
                           duration=_dim(significant=True), temporal=_dim(significant=True),
                           spatial=_dim(significant=True), recurrence=_dim(), overall_deviation_score=90.0)
    ml = MLPrediction(event_id="E1", p_persistent_industrial=0.9, p_natural_candidate=0.1,
                       predicted_class=MLClass.PERSISTENT_INDUSTRIAL, low_confidence=False, model_version="v1")
    r = compute_risk(event, deviation, ml, facility_present=True)
    assert r.severity in (Severity.HIGH, Severity.CRITICAL)
    assert r.risk_score > 60


def test_low_everything_yields_low_severity():
    event = _event(peak_frp=5.0, duration_hours=0.2, observation_count=1)
    r = compute_risk(event, None, None, facility_present=False)
    assert r.severity == Severity.LOW


def test_risk_always_includes_caveats():
    event = _event()
    r = compute_risk(event, None, None, facility_present=False)
    assert len(r.caveats) >= 1
    assert any("not" in c.lower() for c in r.caveats)


def test_risk_score_is_bounded_0_to_100():
    event = _event(peak_frp=10000.0, duration_hours=1000.0, observation_count=1000)
    deviation = Deviation(event_id="E1", baseline_confidence=BaselineConfidence.ESTABLISHED,
                           intensity=_dim(significant=True), persistence=_dim(significant=True),
                           duration=_dim(significant=True), temporal=_dim(significant=True),
                           spatial=_dim(significant=True), recurrence=_dim(significant=True), overall_deviation_score=100.0)
    r = compute_risk(event, deviation, None, facility_present=True)
    assert 0.0 <= r.risk_score <= 100.0
