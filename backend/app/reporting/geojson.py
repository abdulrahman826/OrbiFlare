from __future__ import annotations

from app.model.schemas import Facility, ThermalEvent


def events_to_geojson(events: list[ThermalEvent]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [e.centroid_lon, e.centroid_lat]},
                "properties": {
                    "event_id": e.event_id, "severity": e.severity.value if e.severity else None,
                    "risk_score": e.risk_score, "status": e.status.value, "peak_frp": e.peak_frp,
                    "facility_id": e.facility_id, "trajectory_direction": e.trajectory_direction.value if e.trajectory_direction else None,
                    "is_demo": e.is_demo, "first_detected": e.first_detected.isoformat(),
                },
            }
            for e in events
        ],
    }


def facilities_to_geojson(facilities: list[Facility]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [f.longitude, f.latitude]},
                "properties": {
                    "facility_id": f.facility_id, "name": f.name, "facility_type": f.facility_type,
                    "industry": f.industry, "is_demo": f.is_demo,
                },
            }
            for f in facilities
        ],
    }
