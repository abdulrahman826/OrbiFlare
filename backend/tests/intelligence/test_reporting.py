from datetime import datetime

from app.model.schemas import Facility, Severity, ThermalEvent
from app.reporting.csv import events_to_csv
from app.reporting.geojson import events_to_geojson, facilities_to_geojson


def _event():
    return ThermalEvent(event_id="E1", first_detected=datetime(2025, 1, 1), last_detected=datetime(2025, 1, 1),
                         duration_hours=1, observation_count=1, centroid_lat=22.3, centroid_lon=69.8,
                         severity=Severity.HIGH, risk_score=70.0, source_observation_ids=["o1"])


def test_events_csv_contains_header_and_row():
    csv_text = events_to_csv([_event()])
    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("event_id")
    assert "E1" in lines[1]


def test_events_geojson_is_valid_feature_collection():
    geo = events_to_geojson([_event()])
    assert geo["type"] == "FeatureCollection"
    assert geo["features"][0]["geometry"]["coordinates"] == [69.8, 22.3]
    assert geo["features"][0]["properties"]["event_id"] == "E1"


def test_facilities_geojson_is_valid_feature_collection():
    f = Facility(facility_id="F1", name="Plant", facility_type="refinery", latitude=22.3, longitude=69.8)
    geo = facilities_to_geojson([f])
    assert geo["features"][0]["properties"]["facility_id"] == "F1"
