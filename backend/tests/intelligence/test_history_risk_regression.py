"""Historical baselines feed ONLY the existing behaviour-deviation input: risk logic, thresholds and caps are unchanged."""
from datetime import datetime, timedelta

import pytest

from app.config import get_settings
from app.intelligence import history_baseline as hb
from app.intelligence import pipeline as pl
from app.model.schemas import BaselineConfidence, DataSource, Sensor, ThermalEvent, ThermalObservation

S = get_settings()


class _Store:
    available = True

    def __init__(self, n):
        self.n = n

    def coverage_fraction(self):
        return 1.0

    def events_for(self, fid, before=None):
        evs, obs = [], {}
        for i in range(self.n):
            t0 = datetime(2026, 4, 1) + timedelta(days=6 * i)
            e = ThermalEvent(event_id=f"HIST-{i:04d}", first_detected=t0, last_detected=t0 + timedelta(hours=1), duration_hours=1.0, observation_count=3, peak_frp=4.0, mean_frp=4.0,
                             peak_bt=320.0, mean_bt=318.0, centroid_lat=22.3, centroid_lon=69.8, facility_id=fid, source_observation_ids=[])
            evs.append(e)
            obs[e.event_id] = [ThermalObservation(observation_id=f"{e.event_id}-{k}", timestamp=t0 + timedelta(minutes=20 * k), latitude=22.3, longitude=69.8, sensor=Sensor.VIIRS, frp=4.0,
                                                  source=DataSource.FIRMS, day_night="N") for k in range(3)]
        return evs, obs


def _run(monkeypatch, n_hist, facility=True):
    monkeypatch.setattr(hb, "get_store", lambda: _Store(n_hist))
    t0 = datetime(2026, 9, 24, 6)
    obs = [ThermalObservation(observation_id=f"L{k}", timestamp=t0 + timedelta(minutes=30 * k), latitude=22.3, longitude=69.8, sensor=Sensor.VIIRS, frp=[40, 90, 60, 20][k % 4],
                              brightness_temperature=345.0, source=DataSource.FIRMS, day_night="N") for k in range(12)]
    e = ThermalEvent(event_id="EVT-LIVE000002", first_detected=t0, last_detected=obs[-1].timestamp, duration_hours=5.5, observation_count=12, peak_frp=90.0, mean_frp=52.0, peak_bt=345.0, mean_bt=345.0,
                     centroid_lat=22.3, centroid_lon=69.8, footprint_radius_km=0.2, facility_id="F-REF" if facility else None, facility_distance_km=0.2 if facility else None,
                     facility_context_quality="HIGH" if facility else None, source_observation_ids=[o.observation_id for o in obs])
    events = [e]
    twins, _cur, obs_by_event = pl.build_thermal_twins_stage(events, obs)
    dev = pl.calculate_deviations_stage(events, twins, obs_by_event)
    preds = pl.classify_stage(events)
    risks = pl.calculate_risk_stage(events, dev, preds, obs_by_event)
    trajs = pl.calculate_trajectory_stage(events, twins, obs_by_event)
    return e, twins, dev[e.event_id], risks[e.event_id], trajs[e.event_id]


def test_thresholds_and_weights_are_unchanged():
    assert (S.risk_threshold_medium, S.risk_threshold_high, S.risk_threshold_critical) == (35.0, 60.0, 80.0)
    assert S.risk_limited_baseline_factor == 0.4 and (S.baseline_min_events_limited, S.baseline_min_events_established) == (2, 4)


@pytest.mark.parametrize("n_hist,state,cap", [(0, BaselineConfidence.INSUFFICIENT, 0.0), (1, BaselineConfidence.INSUFFICIENT, 0.0),
                                              (2, BaselineConfidence.LIMITED, 14.0), (6, BaselineConfidence.ESTABLISHED, 35.0)])
def test_history_only_supplies_the_deviation_input_and_the_caps_hold(monkeypatch, n_hist, state, cap):
    e, twins, dev, risk, traj = _run(monkeypatch, n_hist)
    assert twins["F-REF"].baseline_confidence == state and risk.baseline_status == state
    assert risk.deviation_contribution_cap == pytest.approx(cap) and risk.deviation_contribution <= cap + 1e-9
    if state == BaselineConfidence.INSUFFICIENT:
        assert dev.overall_deviation_score == 0.0 and risk.deviation_contribution == 0.0            # no invented z-scores, no risk contribution
    # canonical latest-FRP semantics: event risk == last trajectory point, whatever the baseline
    assert traj.points[-1].risk_score == risk.risk_score == e.risk_score and traj.points[-1].severity == risk.severity


def test_history_adds_no_risk_component_and_never_double_counts_recurrence(monkeypatch):
    _e, _t, _d, risk, _tr = _run(monkeypatch, 6)
    assert {f.name for f in risk.risk_factors} <= {"behaviour_deviation", "ml_signal", "persistence", "duration", "intensity", "facility_context"}
    assert all("history" not in f.name and "recurrence" not in f.name for f in risk.risk_factors)


def test_no_facility_still_contributes_zero_deviation_even_with_history_available(monkeypatch):
    _e, twins, dev, risk, _tr = _run(monkeypatch, 6, facility=False)
    assert twins == {} and dev.overall_deviation_score == 0.0 and risk.deviation_contribution == 0.0
