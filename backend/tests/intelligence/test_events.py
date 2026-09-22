from datetime import datetime, timedelta

from app.intelligence.events import cluster_observations, form_events
from app.model.schemas import DataSource, Sensor, ThermalObservation


def _obs(i, lat, lon, ts, source=DataSource.DEMO):
    return ThermalObservation(
        observation_id=f"O{i}", timestamp=ts, latitude=lat, longitude=lon, sensor=Sensor.SYNTHETIC,
        frp=25.0, brightness_temperature=330.0, source=source,
    )


def test_close_observations_cluster_into_one_event():
    base = datetime(2025, 1, 1, 12, 0)
    obs = [
        _obs(1, 22.30, 69.80, base),
        _obs(2, 22.3005, 69.8005, base + timedelta(minutes=30)),
        _obs(3, 22.301, 69.801, base + timedelta(hours=1)),
    ]
    events = form_events(obs)
    assert len(events) == 1
    assert events[0].observation_count == 3


def test_spatially_distant_observations_form_separate_events():
    base = datetime(2025, 1, 1, 12, 0)
    obs = [
        _obs(1, 22.30, 69.80, base),
        _obs(2, 10.00, 40.00, base + timedelta(minutes=5)),  # thousands of km away
    ]
    events = form_events(obs)
    assert len(events) == 2


def test_temporally_distant_observations_form_separate_events():
    base = datetime(2025, 1, 1, 12, 0)
    obs = [
        _obs(1, 22.30, 69.80, base),
        _obs(2, 22.30, 69.80, base + timedelta(days=10)),  # same place, long gap
    ]
    groups = cluster_observations(obs, spatial_radius_km=1.5, temporal_gap_hours=12)
    assert len(groups) == 2


def test_clustering_is_deterministic_across_runs():
    base = datetime(2025, 1, 1, 12, 0)
    obs = [_obs(i, 22.30 + i * 0.0001, 69.80, base + timedelta(minutes=i * 10)) for i in range(6)]
    events_a = form_events(obs)
    events_b = form_events(list(reversed(obs)))
    assert {e.event_id for e in events_a} == {e.event_id for e in events_b}


def test_sparse_single_observation_forms_valid_event():
    obs = [_obs(1, 22.30, 69.80, datetime(2025, 1, 1))]
    events = form_events(obs)
    assert len(events) == 1
    assert events[0].observation_count == 1
    assert events[0].duration_hours == 0.0


def test_event_preserves_source_observation_ids():
    base = datetime(2025, 1, 1, 12, 0)
    obs = [_obs(1, 22.30, 69.80, base), _obs(2, 22.3001, 69.8001, base + timedelta(minutes=10))]
    events = form_events(obs)
    assert set(events[0].source_observation_ids) == {"O1", "O2"}


def test_missing_frp_values_handled_without_crash():
    base = datetime(2025, 1, 1, 12, 0)
    o = ThermalObservation(observation_id="O1", timestamp=base, latitude=22.3, longitude=69.8,
                            sensor=Sensor.SYNTHETIC, frp=None, brightness_temperature=None, source=DataSource.DEMO)
    events = form_events([o])
    assert events[0].peak_frp is None
    assert events[0].mean_frp is None
