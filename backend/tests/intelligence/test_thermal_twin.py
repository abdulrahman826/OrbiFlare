from datetime import datetime, timedelta

from app.intelligence.thermal_twin import build_thermal_twin
from app.model.schemas import BaselineConfidence, DataSource, Sensor, ThermalEvent, ThermalObservation


def _hist_event(i, day_offset, hour=18):
    ts = datetime(2024, 1, 1, hour) + timedelta(days=day_offset)
    obs = [
        ThermalObservation(observation_id=f"E{i}-O1", timestamp=ts, latitude=22.30, longitude=69.80,
                            sensor=Sensor.SYNTHETIC, frp=25.0 + i, brightness_temperature=330.0, source=DataSource.DEMO, day_night="N"),
        ThermalObservation(observation_id=f"E{i}-O2", timestamp=ts + timedelta(minutes=30), latitude=22.3001, longitude=69.8001,
                            sensor=Sensor.SYNTHETIC, frp=27.0 + i, brightness_temperature=332.0, source=DataSource.DEMO, day_night="N"),
    ]
    event = ThermalEvent(
        event_id=f"EVT-H{i}", first_detected=ts, last_detected=ts + timedelta(minutes=30), duration_hours=0.5,
        observation_count=2, peak_frp=27.0 + i, mean_frp=26.0 + i, peak_bt=332.0, mean_bt=331.0,
        centroid_lat=22.30005, centroid_lon=69.80005, source_observation_ids=[o.observation_id for o in obs],
    )
    return event, obs


def test_insufficient_baseline_with_too_little_history():
    events_and_obs = [_hist_event(0, 0)]
    events = [e for e, _ in events_and_obs]
    obs_by_event = {e.event_id: o for e, o in events_and_obs}
    twin = build_thermal_twin("F1", events, obs_by_event)
    assert twin.baseline_confidence == BaselineConfidence.INSUFFICIENT


def test_limited_baseline_with_moderate_history():
    # 2 events, ~4 obs total -> meets the "limited" observation floor but not "established"
    events_and_obs = [_hist_event(i, i * 10) for i in range(2)]
    events = [e for e, _ in events_and_obs]
    obs_by_event = {e.event_id: o for e, o in events_and_obs}
    twin = build_thermal_twin("F1", events, obs_by_event)
    assert twin.baseline_confidence == BaselineConfidence.LIMITED


def test_established_baseline_with_sufficient_history():
    events_and_obs = [_hist_event(i, i * 10) for i in range(6)]
    events = [e for e, _ in events_and_obs]
    obs_by_event = {e.event_id: o for e, o in events_and_obs}
    twin = build_thermal_twin("F1", events, obs_by_event)
    assert twin.baseline_confidence == BaselineConfidence.ESTABLISHED
    assert twin.normal_frp.n == 6
    assert twin.normal_frp.median is not None
    assert "18" in twin.normal_hour_pattern  # night-hour pattern captured


def test_never_fabricates_history_when_empty():
    twin = build_thermal_twin("F1", [], {})
    assert twin.baseline_confidence == BaselineConfidence.INSUFFICIENT
    assert twin.historical_event_count == 0
    assert twin.normal_frp.n == 0


def test_spatial_footprint_is_computed_from_real_centroids():
    events_and_obs = [_hist_event(i, i * 10) for i in range(6)]
    events = [e for e, _ in events_and_obs]
    obs_by_event = {e.event_id: o for e, o in events_and_obs}
    twin = build_thermal_twin("F1", events, obs_by_event)
    assert twin.normal_spatial_centroid_lat is not None
    assert twin.normal_spatial_radius_km is not None
    assert twin.normal_spatial_radius_km < 1.0  # all synthetic events are within meters of each other
