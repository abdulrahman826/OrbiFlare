from datetime import datetime, timedelta

from app.intelligence.deviation import compute_deviation
from app.intelligence.thermal_twin import build_thermal_twin
from app.model.schemas import DataSource, DeviationStatus, Sensor, ThermalEvent, ThermalObservation


def _build_baseline_twin():
    events, obs_by_event = [], {}
    for i in range(8):
        ts = datetime(2024, 1, 1, 18) + timedelta(days=i * 10)
        obs = [
            ThermalObservation(observation_id=f"E{i}-O1", timestamp=ts, latitude=22.30, longitude=69.80,
                                sensor=Sensor.SYNTHETIC, frp=25.0 + (i % 3), brightness_temperature=330.0,
                                source=DataSource.DEMO, day_night="N"),
            ThermalObservation(observation_id=f"E{i}-O2", timestamp=ts + timedelta(minutes=20), latitude=22.3001, longitude=69.8001,
                                sensor=Sensor.SYNTHETIC, frp=27.0 + (i % 3), brightness_temperature=332.0,
                                source=DataSource.DEMO, day_night="N"),
        ]
        event = ThermalEvent(
            event_id=f"EVT-H{i}", first_detected=ts, last_detected=ts + timedelta(minutes=20), duration_hours=0.33,
            observation_count=2, peak_frp=27.0 + (i % 3), mean_frp=26.0, peak_bt=332.0, mean_bt=331.0,
            centroid_lat=22.30005, centroid_lon=69.80005, source_observation_ids=[o.observation_id for o in obs],
        )
        events.append(event)
        obs_by_event[event.event_id] = obs
    twin = build_thermal_twin("F1", events, obs_by_event)
    return twin


def test_insufficient_baseline_returns_insufficient_status_not_fabricated_numbers():
    from app.model.schemas import DistributionSummary, ThermalTwin, BaselineConfidence
    twin = ThermalTwin(
        facility_id="F1", baseline_confidence=BaselineConfidence.INSUFFICIENT,
        normal_frp=DistributionSummary(n=0), normal_bt=DistributionSummary(n=0),
        normal_persistence=DistributionSummary(n=0), normal_duration=DistributionSummary(n=0),
    )
    event = ThermalEvent(event_id="E-CUR", first_detected=datetime(2025, 1, 1), last_detected=datetime(2025, 1, 1),
                          duration_hours=1, observation_count=3, centroid_lat=22.3, centroid_lon=69.8,
                          source_observation_ids=["a", "b", "c"])
    deviation = compute_deviation(event, twin, [])
    assert deviation.baseline_confidence.value == "INSUFFICIENT"
    for dim_name in ("intensity", "persistence", "duration", "temporal", "spatial", "recurrence"):
        assert getattr(deviation, dim_name).status == DeviationStatus.INSUFFICIENT_BASELINE
    assert deviation.overall_deviation_score == 0.0


def test_normal_event_shows_no_significant_deviation():
    twin = _build_baseline_twin()
    ts = datetime(2024, 5, 1, 18)
    obs = [
        ThermalObservation(observation_id="CUR-O1", timestamp=ts, latitude=22.30, longitude=69.80,
                            sensor=Sensor.SYNTHETIC, frp=26.0, brightness_temperature=331.0, source=DataSource.DEMO, day_night="N"),
        ThermalObservation(observation_id="CUR-O2", timestamp=ts + timedelta(minutes=20), latitude=22.3001, longitude=69.8001,
                            sensor=Sensor.SYNTHETIC, frp=27.0, brightness_temperature=331.0, source=DataSource.DEMO, day_night="N"),
    ]
    event = ThermalEvent(event_id="E-CUR", first_detected=ts, last_detected=ts + timedelta(minutes=20), duration_hours=0.33,
                          observation_count=2, peak_frp=27.0, mean_frp=26.5, centroid_lat=22.30005, centroid_lon=69.80005,
                          source_observation_ids=[o.observation_id for o in obs])
    deviation = compute_deviation(event, twin, obs)
    assert not deviation.intensity.is_notable
    assert not deviation.spatial.is_notable


def test_anomalous_event_shows_significant_intensity_and_spatial_deviation():
    twin = _build_baseline_twin()
    ts = datetime(2024, 5, 1, 10)  # daytime -- outside the 18:00 night baseline
    obs = [
        ThermalObservation(observation_id="CUR-O1", timestamp=ts, latitude=22.35, longitude=69.85,  # ~6km away
                            sensor=Sensor.SYNTHETIC, frp=180.0, brightness_temperature=390.0, source=DataSource.DEMO, day_night="D"),
    ]
    event = ThermalEvent(event_id="E-CUR", first_detected=ts, last_detected=ts, duration_hours=0.0,
                          observation_count=1, peak_frp=180.0, mean_frp=180.0, centroid_lat=22.35, centroid_lon=69.85,
                          source_observation_ids=["CUR-O1"])
    deviation = compute_deviation(event, twin, obs)
    assert deviation.intensity.is_significant
    assert deviation.spatial.is_significant
    assert deviation.overall_deviation_score > 30
    assert any("above" in e or "outside" in e for e in deviation.explanations)


def test_deviation_never_converts_directly_to_fire_label():
    twin = _build_baseline_twin()
    ts = datetime(2024, 5, 1, 10)
    obs = [ThermalObservation(observation_id="CUR-O1", timestamp=ts, latitude=22.35, longitude=69.85,
                               sensor=Sensor.SYNTHETIC, frp=180.0, brightness_temperature=390.0, source=DataSource.DEMO)]
    event = ThermalEvent(event_id="E-CUR", first_detected=ts, last_detected=ts, duration_hours=0.0,
                          observation_count=1, peak_frp=180.0, centroid_lat=22.35, centroid_lon=69.85,
                          source_observation_ids=["CUR-O1"])
    deviation = compute_deviation(event, twin, obs)
    dumped = deviation.model_dump()
    assert "fire" not in str(dumped).lower()
