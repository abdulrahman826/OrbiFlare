from datetime import datetime, timedelta

from app.intelligence.trajectory import _direction, compute_trajectory
from app.model.schemas import DataSource, Sensor, ThermalObservation, TrajectoryDirection


def test_direction_classifies_escalating_monotonic_rise():
    assert _direction([24, 38, 57, 72]) == TrajectoryDirection.ESCALATING


def test_direction_classifies_stable_flat_series():
    assert _direction([20, 21, 19, 20]) == TrajectoryDirection.STABLE


def test_direction_classifies_increasing_modest_rise():
    assert _direction([20, 24, 26, 30]) == TrajectoryDirection.INCREASING


def test_direction_classifies_decreasing_series():
    assert _direction([70, 55, 40, 30]) == TrajectoryDirection.DECREASING


def test_direction_classifies_insufficient_data():
    assert _direction([]) == TrajectoryDirection.INSUFFICIENT_DATA
    assert _direction([50]) == TrajectoryDirection.INSUFFICIENT_DATA


def _obs(i, ts, frp):
    return ThermalObservation(observation_id=f"O{i}", timestamp=ts, latitude=22.30 + i * 0.001,
                               longitude=69.80, sensor=Sensor.SYNTHETIC, frp=frp,
                               brightness_temperature=330.0 + frp * 0.1, source=DataSource.DEMO)


def test_compute_trajectory_never_predicts_the_future():
    base = datetime(2025, 1, 1)
    obs = [_obs(i, base + timedelta(minutes=i * 20), 30 + i * 8) for i in range(5)]
    traj, steps = compute_trajectory(obs, None, None, None, "E1")
    assert "will become" not in traj.explanation.lower()
    assert "fire probability" not in traj.explanation.lower()
    assert len(steps) == 5


def test_compute_trajectory_matches_point_count_to_observations():
    base = datetime(2025, 1, 1)
    obs = [_obs(i, base + timedelta(minutes=i * 20), 30) for i in range(3)]
    traj, _ = compute_trajectory(obs, None, None, None, "E1")
    assert len(traj.points) == 3
