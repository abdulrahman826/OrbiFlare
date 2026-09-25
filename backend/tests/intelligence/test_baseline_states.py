"""Baseline handling by amount of history: 0/1/2 historical events, then limited, established, insufficient.
Insufficient history must never create deviation evidence; limited history is discounted; nothing is fabricated."""
from datetime import datetime, timedelta

import pytest

from app.config import get_settings
from app.intelligence import risk as risk_mod
from app.intelligence.deviation import compute_deviation
from app.intelligence.thermal_twin import build_thermal_twin
from app.model.schemas import BaselineConfidence, DataSource, MLClass, MLPrediction, Sensor, ThermalEvent, ThermalObservation

S = get_settings()


def _hist(i, day, n_obs=2, frp=20.0):
    ts = datetime(2026, 9, 1, 18) + timedelta(days=day)
    obs = [ThermalObservation(observation_id=f"H{i}-{k}", timestamp=ts + timedelta(minutes=20 * k), latitude=22.30, longitude=69.80, sensor=Sensor.VIIRS,
                              frp=frp + k, brightness_temperature=325.0, source=DataSource.FIRMS, day_night="N") for k in range(n_obs)]
    ev = ThermalEvent(event_id=f"EVT-H{i}", first_detected=ts, last_detected=ts + timedelta(minutes=20 * n_obs), duration_hours=0.5, observation_count=n_obs,
                      peak_frp=frp + n_obs, mean_frp=frp, peak_bt=326.0, mean_bt=325.0, centroid_lat=22.3, centroid_lon=69.8,
                      source_observation_ids=[o.observation_id for o in obs])
    return ev, obs


def _twin(n_events, n_obs=2):
    pairs = [_hist(i, i * 2, n_obs=n_obs) for i in range(n_events)]
    return build_thermal_twin("F1", [e for e, _ in pairs], {e.event_id: o for e, o in pairs})


def _current():
    ts = datetime(2026, 9, 24, 6)
    return ThermalEvent(event_id="EVT-C", first_detected=ts, last_detected=ts + timedelta(hours=9), duration_hours=9.0, observation_count=14, peak_frp=90.0,
                        mean_frp=60.0, peak_bt=350.0, mean_bt=340.0, centroid_lat=22.3, centroid_lon=69.8, facility_id="F1", facility_distance_km=0.4,
                        facility_context_quality="HIGH", source_observation_ids=[])


def _ml():
    return MLPrediction(event_id="EVT-C", p_persistent_industrial=0.5, p_natural_candidate=0.5, predicted_class=MLClass.PERSISTENT_INDUSTRIAL,
                        low_confidence=True, model_version="rf-proxy-v2")


@pytest.mark.parametrize("n_events,expected", [
    (0, BaselineConfidence.INSUFFICIENT),     # no history: nothing invented
    (1, BaselineConfidence.INSUFFICIENT),     # one event says nothing about normal variability
    (2, BaselineConfidence.LIMITED),          # two events with enough observations: cautious comparison only
    (3, BaselineConfidence.LIMITED),
    (4, BaselineConfidence.ESTABLISHED),      # 4 events / 8 observations
])
def test_baseline_state_by_number_of_historical_events(n_events, expected):
    twin = _twin(n_events)
    assert twin.baseline_confidence == expected
    assert twin.historical_event_count == n_events


def test_zero_history_twin_contains_no_fabricated_values():
    t = _twin(0)
    assert t.normal_frp.n == 0 and t.normal_frp.median is None and t.history_start is None


def test_one_event_history_still_has_no_normal_behaviour_asserted():
    t = _twin(1)
    d = compute_deviation(_current(), t, [])
    assert d.baseline_confidence == BaselineConfidence.INSUFFICIENT and d.overall_deviation_score == 0.0
    assert all(getattr(d, n).status.value != "COMPUTED" for n in ("intensity", "persistence", "duration", "temporal", "spatial", "recurrence"))
    assert "INSUFFICIENT BASELINE" in d.explanations[0]


@pytest.mark.parametrize("n_events", [0, 1])
def test_insufficient_history_contributes_exactly_zero_deviation_to_risk(n_events):
    d = compute_deviation(_current(), _twin(n_events), [])
    r = risk_mod.compute_risk(_current(), d, _ml(), True)
    assert r.baseline_status == BaselineConfidence.INSUFFICIENT and r.deviation_contribution == 0.0 and r.deviation_contribution_cap == 0.0


def test_limited_history_is_capped_and_established_is_not():
    lim = compute_deviation(_current(), _twin(2), [])
    est = compute_deviation(_current(), _twin(5), [])
    assert lim.baseline_confidence == BaselineConfidence.LIMITED and est.baseline_confidence == BaselineConfidence.ESTABLISHED
    rl, re_ = risk_mod.compute_risk(_current(), lim, _ml(), True), risk_mod.compute_risk(_current(), est, _ml(), True)
    assert rl.deviation_contribution_cap == pytest.approx(0.35 * 100 * S.risk_limited_baseline_factor)
    assert rl.deviation_contribution <= rl.deviation_contribution_cap + 1e-9
    assert re_.deviation_contribution_cap == pytest.approx(35.0)


def test_no_facility_context_means_no_facility_baseline():
    ev = _current()
    ev.facility_id, ev.facility_distance_km, ev.facility_context_quality = None, None, None
    d = compute_deviation(ev, None, [])
    r = risk_mod.compute_risk(ev, d, _ml(), False)
    assert d.baseline_confidence == BaselineConfidence.INSUFFICIENT and r.deviation_contribution == 0.0
    assert any("no relevant facility context" in x.lower() or "no usable facility baseline" in x.lower() or "insufficient baseline" in x.lower() for x in r.limiting)


def test_deviation_evidence_from_limited_history_is_one_step_weaker_and_says_so():
    from app.intelligence.evidence import build_evidence_stack
    from app.model.schemas import EvidenceStrength
    lim = compute_deviation(_current(), _twin(2), [])
    est = compute_deviation(_current(), _twin(5), [])
    items = lambda st: [i for i in st.supporting_evidence + st.contradicting_evidence if i.name.endswith("_deviation")]
    s_lim, s_est = items(build_evidence_stack(_current(), lim, None, None)), items(build_evidence_stack(_current(), est, None, None))
    assert s_lim and s_est
    assert not any(i.strength == EvidenceStrength.STRONG for i in s_lim)                      # limited history never yields STRONG evidence
    assert all("LIMITED baseline" in i.explanation for i in s_lim if i.direction.value == "SUPPORTING")
    assert not any("LIMITED baseline" in i.explanation for i in s_est)
