"""Facility enrichment: attach nearest-facility CONTEXT to a thermal event.

Proximity is context, never causation. Callers must render/word this as
"facility located approximately X km from event" -- never "hotspot belongs
to facility". See app/intelligence/explanations.py for the enforced phrasing
helpers.
"""
from __future__ import annotations

from app.intelligence.clustering import FacilitySpatialIndex
from app.model.schemas import Facility, ThermalEvent

# Beyond this distance we no longer consider a facility "nearby" for context
# purposes (still returned by the raw nearest() call, but enrichment treats
# it as "no facility in the vicinity").
MAX_CONTEXT_DISTANCE_KM = 15.0


def build_facility_index(facilities: list[Facility]) -> FacilitySpatialIndex:
    return FacilitySpatialIndex(
        facility_ids=[f.facility_id for f in facilities],
        lats=[f.latitude for f in facilities],
        lons=[f.longitude for f in facilities],
    )


def enrich_event_with_facility(event: ThermalEvent, index: FacilitySpatialIndex) -> ThermalEvent:
    facility_id, distance_km = index.nearest(event.centroid_lat, event.centroid_lon)
    if facility_id is not None and distance_km is not None and distance_km <= MAX_CONTEXT_DISTANCE_KM:
        event.facility_id = facility_id
        event.facility_distance_km = round(distance_km, 3)
    else:
        event.facility_id = None
        event.facility_distance_km = None
    return event


def enrich_events(events: list[ThermalEvent], facilities: list[Facility]) -> list[ThermalEvent]:
    index = build_facility_index(facilities)
    return [enrich_event_with_facility(e, index) for e in events]
