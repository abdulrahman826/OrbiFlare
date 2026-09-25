"""Read-only contextual joins between reference data and the operational store.

This module only READS the operational DB. Nothing here mutates it, and nothing in the ML / intelligence
pipeline imports this package (see tests/reference/test_reference_isolation.py).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.reference import admin, incidents as inc_mod
from app.reference.schemas import (
    FirmsMatchCheck, HistoricalIncident, IncidentContext, NearbyEvent, NearbyFacility,
)
from app.storage import models as m
from app.storage import repositories as repo

SPATIAL_BUFFER_KM = 1.0
TEMPORAL_WINDOW_DAYS = 1


def _hav(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def incidents_near(lat: float, lon: float, radius_km: float) -> list[tuple[HistoricalIncident, float]]:
    hits = [(i, _hav(lat, lon, i.latitude, i.longitude)) for i in inc_mod.incidents()]
    return sorted(((i, d) for i, d in hits if d <= radius_km), key=lambda t: t[1])


def firms_match_check(db: Session, incident: HistoricalIncident) -> FirmsMatchCheck:
    """Count STORED, non-demo FIRMS observations within 1 km / +-1 day of the incident date. Never fabricates a match."""
    day = datetime.fromisoformat(incident.date)
    lo, hi = day - timedelta(days=TEMPORAL_WINDOW_DAYS), day + timedelta(days=TEMPORAL_WINDOW_DAYS + 1)
    deg = SPATIAL_BUFFER_KM / 111.0 * 1.5
    stmt = select(m.ObservationRecord).where(
        m.ObservationRecord.source == "FIRMS",
        m.ObservationRecord.timestamp >= lo, m.ObservationRecord.timestamp < hi,
        m.ObservationRecord.latitude.between(incident.latitude - deg, incident.latitude + deg),
        m.ObservationRecord.longitude.between(incident.longitude - deg * 1.5, incident.longitude + deg * 1.5),
    )
    n = sum(1 for o in db.scalars(stmt) if _hav(incident.latitude, incident.longitude, o.latitude, o.longitude) <= SPATIAL_BUFFER_KM)
    if n:
        return FirmsMatchCheck(
            checked_against="stored non-demo FIRMS observations", spatial_buffer_km=SPATIAL_BUFFER_KM,
            temporal_window_days=TEMPORAL_WINDOW_DAYS, matching_firms_observations=n, status="FIRMS_OBSERVATIONS_PRESENT",
            note="Stored FIRMS observations exist near this location and date. Co-occurrence is not confirmation of the reported incident.",
        )
    return FirmsMatchCheck(
        checked_against="stored non-demo FIRMS observations", spatial_buffer_km=SPATIAL_BUFFER_KM,
        temporal_window_days=TEMPORAL_WINDOW_DAYS, matching_firms_observations=0, status="NO_FIRMS_MATCH",
        note="No FIRMS observation for this place and date is stored in OrbiFlare. This says nothing about whether the incident occurred.",
    )


def incident_context(db: Session, incident: HistoricalIncident, radius_km: float = 50.0) -> IncidentContext:
    facilities = [
        NearbyFacility(facility_id=f.facility_id, name=f.name, facility_type=f.facility_type,
                       distance_km=round(_hav(incident.latitude, incident.longitude, f.latitude, f.longitude), 2), is_demo=f.is_demo)
        for f in (repo.facility_to_schema(r) for r in repo.list_facilities(db))
    ]
    facilities = sorted((f for f in facilities if f.distance_km <= radius_km), key=lambda f: f.distance_km)
    events = []
    for r in repo.list_events(db):
        e = repo.event_to_schema(r)
        d = _hav(incident.latitude, incident.longitude, e.centroid_lat, e.centroid_lon)
        if d <= radius_km:
            events.append(NearbyEvent(event_id=e.event_id, severity=e.severity.value if e.severity else None, risk_score=e.risk_score,
                                      distance_km=round(d, 2), first_detected=e.first_detected.isoformat(), is_demo=e.is_demo))
    events.sort(key=lambda e: e.distance_km)
    region = admin.resolve(incident.latitude, incident.longitude)
    match = firms_match_check(db, incident)
    known = [
        f"Reported by: {incident.provenance.source_label} (dated {incident.date}).",
        f"Approximate location resolves to {region.district + ', ' if region.district else ''}{region.state}." if region.resolved
        else "Approximate location does not fall inside the bundled boundary geometry.",
        f"{len(facilities)} OrbiFlare facility record(s) within {radius_km:g} km (spatial association only).",
        f"{len(events)} current thermal event(s) within {radius_km:g} km.",
    ]
    unknown = [
        "Whether a satellite thermal detection corresponds to this record.",
        "The exact location, cause or extent -- coordinates are approximate.",
        "Whether any nearby current thermal event is related to it (proximity is not causation).",
    ]
    return IncidentContext(
        incident=incident, admin=region, radius_km=radius_km, nearby_facilities=facilities, nearby_current_events=events,
        firms_match=match, known=known, unknown=unknown,
    )
