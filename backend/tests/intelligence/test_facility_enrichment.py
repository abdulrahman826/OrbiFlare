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


def test_facilities_at_identical_coordinates_are_ordered_deterministically_not_by_row_order():
    import pandas as pd
    from app.context.facilities import FacilityContextIndex
    rows = [
        {"facility_id": "F-Z", "lat": 21.88, "lon": 73.69, "facility_type": "bus_depot", "source": "OSM", "name": "Named Depot", "country": "IND"},
        {"facility_id": "F-A", "lat": 21.88, "lon": 73.69, "facility_type": "industrial", "source": "OSM", "name": None, "country": "IND"},
        {"facility_id": "F-H", "lat": 21.88, "lon": 73.69, "facility_type": "refinery", "source": "OSM", "name": "Real Refinery", "country": "IND"},
        {"facility_id": "F-M", "lat": 21.88, "lon": 73.69, "facility_type": "cement", "source": "OSM", "name": None, "country": "IND"},
    ]
    orders = [rows, rows[::-1], rows[2:] + rows[:2]]
    winners, full = set(), set()
    for order in orders:
        idx = FacilityContextIndex(pd.DataFrame(order))
        hits = idx.near(21.881, 73.69, 3.0)
        winners.add(hits[0]["facility_id"])
        full.add(tuple(h["facility_id"] for h in hits))
    assert winners == {"F-H"} and len(full) == 1                      # HIGH-quality heat-relevant facility first, in every row order
    assert list(full)[0] == ("F-H", "F-M", "F-A", "F-Z")             # MEDIUM heat-relevant, then LOW by facility_id


def test_equal_quality_and_type_ties_fall_back_to_the_stable_facility_id():
    import pandas as pd
    from app.context.facilities import FacilityContextIndex
    a = {"facility_id": "OSM-1277783028", "lat": 21.883144, "lon": 73.689988, "facility_type": "industrial", "source": "OSM", "name": None, "country": "IND"}
    b = {"facility_id": "OSM-1318752813", "lat": 21.883144, "lon": 73.689988, "facility_type": "bus_depot", "source": "OSM", "name": "Ekta Nagar Bus Depot", "country": "IND"}
    for order in ([a, b], [b, a]):
        assert FacilityContextIndex(pd.DataFrame(order)).nearest(21.88546, 73.69077, 3.0)["facility_id"] == "OSM-1277783028"


def test_distinct_distances_are_never_reordered_by_the_tie_break():
    import pandas as pd
    from app.context.facilities import FacilityContextIndex
    rows = [{"facility_id": "F-HIGH-FAR", "lat": 21.90, "lon": 73.69, "facility_type": "refinery", "source": "OSM", "name": "Far Refinery", "country": "IND"},
            {"facility_id": "F-LOW-NEAR", "lat": 21.881, "lon": 73.69, "facility_type": "industrial", "source": "OSM", "name": None, "country": "IND"}]
    assert FacilityContextIndex(pd.DataFrame(rows)).nearest(21.88, 73.69, 3.0)["facility_id"] == "F-LOW-NEAR"     # nearest still wins
