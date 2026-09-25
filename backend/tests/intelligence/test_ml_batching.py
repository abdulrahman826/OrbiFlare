"""Batching/memoisation of ML predictions must not change any prediction."""
from datetime import datetime, timedelta

from app.intelligence import classification
from app.intelligence.events import build_event_from_group
from app.intelligence.trajectory import compute_trajectory, prefetch_ml
from app.model.schemas import DataSource, Sensor, ThermalObservation


def _obs(i, lat, lon, frp, minutes):
    return ThermalObservation(observation_id=f"B{i}", timestamp=datetime(2026, 9, 24, 6) + timedelta(minutes=minutes), latitude=lat, longitude=lon,
                              sensor=Sensor.VIIRS, frp=frp, brightness_temperature=320 + frp, source=DataSource.FIRMS, day_night="D")


def _events():
    groups = [[_obs(1, 21.0, 72.0, 3.0, 0)], [_obs(2, 22.0, 73.0, 9.0, 0), _obs(3, 22.001, 73.001, 14.0, 90)],
              [_obs(4, 23.0, 74.0, 40.0, 0), _obs(5, 23.0, 74.001, 55.0, 30), _obs(6, 23.001, 74.0, 61.0, 200)]]
    return [build_event_from_group(g) for g in groups], groups


def test_batch_predictions_equal_single_predictions():
    events, _ = _events()
    classification._MEMO.clear()
    single = [classification.classify_event(e) for e in events]
    batch = classification.classify_events(events)
    again = classification.classify_events(events)                      # memo hit
    for s, b, a in zip(single, batch, again):
        assert s.model_dump() == b.model_dump() == a.model_dump()


def test_prefetching_does_not_change_a_trajectory():
    events, groups = _events()
    classification._MEMO.clear()
    cold = [compute_trajectory(g, None, None, None, e.event_id)[0].model_dump() for e, g in zip(events, groups)]
    classification._MEMO.clear()
    prefetch_ml([(g, None, None) for g in groups])
    warm = [compute_trajectory(g, None, None, None, e.event_id)[0].model_dump() for e, g in zip(events, groups)]
    assert cold == warm
