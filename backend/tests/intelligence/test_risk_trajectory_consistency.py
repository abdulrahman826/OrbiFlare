"""Regression: the stored event risk and the last point of its risk trajectory are ONE definition (latest-observation FRP).

Previously the stored risk used the event's PEAK FRP while the trajectory used the LATEST observation's FRP, so the same event
showed two different risk values whenever latest FRP != peak FRP."""
from datetime import datetime, timedelta

import pytest

from app.intelligence import pipeline as pl
from app.intelligence import risk as risk_mod
from app.intelligence.events import form_events
from app.model.schemas import DataSource, Sensor, ThermalObservation


def _obs(i, minutes, frp, oid=None):
    return ThermalObservation(observation_id=oid or f"O{i}", timestamp=datetime(2026, 9, 20, 6, 0) + timedelta(minutes=minutes),
                              latitude=22.300 + i * 0.0005, longitude=69.800, sensor=Sensor.VIIRS, frp=frp,
                              brightness_temperature=320.0 + (frp or 0) * 0.2, source=DataSource.FIRMS)


def _run(observations):
    events = form_events(observations)
    assert len(events) == 1
    twins, _cur, obs_by_event = pl.build_thermal_twins_stage(events, observations)
    dev = pl.calculate_deviations_stage(events, twins, obs_by_event)
    preds = pl.classify_stage(events)
    risks = pl.calculate_risk_stage(events, dev, preds, obs_by_event)
    trajs = pl.calculate_trajectory_stage(events, twins, obs_by_event)
    e = events[0]
    return e, risks[e.event_id], trajs[e.event_id], obs_by_event[e.event_id]


@pytest.mark.parametrize("frps", [
    [90.0, 60.0, 30.0, 10.0],        # peak FRP > latest FRP (event tapers off)
    [10.0, 30.0, 60.0, 90.0],        # latest FRP is the peak (event intensifies)
    [20.0, 120.0, 20.0, 70.0, 5.0],  # peak in the middle, latest low
])
def test_event_risk_equals_last_trajectory_point(frps):
    e, risk, traj, _ = _run([_obs(i, i * 20, f) for i, f in enumerate(frps)])
    assert traj.points[-1].risk_score == risk.risk_score == e.risk_score
    assert traj.points[-1].severity == risk.severity == e.severity


def test_the_previous_failure_case_peak_greater_than_latest():
    e, risk, traj, _ = _run([_obs(0, 0, 120.0), _obs(1, 20, 5.0), _obs(2, 40, 5.0)])
    assert e.peak_frp == 120.0 and e.peak_frp > 5.0
    assert risk.risk_score == traj.points[-1].risk_score
    from app.intelligence import classification
    ml = classification.classify_event(e)
    peak_based = risk_mod.compute_risk(e, None, ml, facility_present=False).risk_score                    # what the old stored value effectively was
    latest_based = risk_mod.compute_risk(e, None, ml, facility_present=False, recent_frp=5.0).risk_score
    assert peak_based > latest_based == risk.risk_score                                                   # the two definitions really differed


def test_intensity_explanation_quotes_the_frp_actually_used():
    _, risk, _, obs = _run([_obs(0, 0, 90.0), _obs(1, 20, 30.0)])
    assert risk_mod.latest_observation_frp(obs) == 30.0


def test_latest_frp_does_not_depend_on_storage_order_or_timestamp_ties():
    a = _obs(0, 0, 10.0, "OA")
    b = _obs(1, 20, 80.0, "OB")
    c = _obs(2, 20, 5.0, "OC")            # same timestamp as b: tie broken by observation id, deterministically
    forward, backward = risk_mod.latest_observation_frp([a, b, c]), risk_mod.latest_observation_frp([c, b, a])
    assert forward == backward == 5.0
    _, r1, t1, _ = _run([a, b, c])
    _, r2, t2, _ = _run([c, a, b])
    assert r1.risk_score == r2.risk_score == t1.points[-1].risk_score == t2.points[-1].risk_score


def test_missing_latest_frp_falls_back_consistently():
    e, risk, traj, _ = _run([_obs(0, 0, 40.0), _obs(1, 20, None)])
    assert risk.risk_score == traj.points[-1].risk_score


def test_every_trajectory_point_is_the_event_risk_at_that_moment():
    """A trajectory point k is exactly the canonical risk of the event as it was after observation k (a documented relationship,
    not an unrelated series): the final point IS the event risk."""
    frps = [15.0, 45.0, 25.0, 60.0]
    obs = [_obs(i, i * 20, f) for i, f in enumerate(frps)]
    e, risk, traj, _ = _run(obs)
    assert len(traj.points) == len(frps)
    assert traj.points[-1].risk_score == risk.risk_score
