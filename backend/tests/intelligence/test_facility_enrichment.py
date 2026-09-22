from datetime import datetime

from app.intelligence.facility_enrichment import enrich_events
from app.model.schemas import Facility, ThermalEvent


def _event(lat, lon):
    return ThermalEvent(
        event_id="E1", first_detected=datetime(2025, 1, 1), last_detected=datetime(2025, 1, 1),
        duration_hours=0.0, observation_count=1, centroid_lat=lat, centroid_lon=lon,
        source_observation_ids=["O1"],
    )


def test_nearest_facility_is_found_within_context_radius():
    facilities = [Facility(facility_id="F1", name="Plant A", facility_type="refinery", latitude=22.30, longitude=69.80)]
    events = enrich_events([_event(22.301, 69.801)], facilities)
    assert events[0].facility_id == "F1"
    assert events[0].facility_distance_km is not None
    assert events[0].facility_distance_km < 1.0


def test_no_facility_within_context_radius_leaves_event_unassociated():
    facilities = [Facility(facility_id="F1", name="Plant A", facility_type="refinery", latitude=22.30, longitude=69.80)]
    events = enrich_events([_event(10.0, 40.0)], facilities)  # thousands of km away
    assert events[0].facility_id is None
    assert events[0].facility_distance_km is None


def test_no_facilities_at_all_leaves_event_unassociated():
    events = enrich_events([_event(22.30, 69.80)], [])
    assert events[0].facility_id is None


def test_picks_closest_of_multiple_facilities():
    facilities = [
        Facility(facility_id="FAR", name="Far", facility_type="refinery", latitude=22.50, longitude=70.00),
        Facility(facility_id="NEAR", name="Near", facility_type="refinery", latitude=22.301, longitude=69.801),
    ]
    events = enrich_events([_event(22.30, 69.80)], facilities)
    assert events[0].facility_id == "NEAR"
