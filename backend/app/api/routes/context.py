"""Facility context (spatial association) + live-data summary for analytics.

Facility proximity is CONTEXTUAL EVIDENCE. Nothing here attributes a thermal event to a facility."""
from __future__ import annotations

import collections

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.context import facilities as facility_ctx
from app.storage import models as m
from app.storage import repositories as repo
from app.storage.database import get_db

router = APIRouter(prefix="/context", tags=["context"])

FIRMS_CONFIDENCE = {"l": "low", "n": "nominal", "h": "high"}
NEVER_CAUSATION = "Nearby does not mean caused by. Facility distance is spatial association only."


def _label(t: str) -> str:
    return t.replace("_", " ").strip().capitalize()


def _statement(nearest: dict | None, radius: float) -> str:
    if nearest is None:
        return (f"No relevant facility context within the {radius:g} km search radius. "
                "Absence of facility context does not indicate a natural fire (facility datasets are incomplete).")
    q = nearest.get("context_quality")
    if q == "LOW":
        return (f"Generic industrial land-use record within {nearest['distance_km']:.2f} km (spatial association; low-quality context, "
                "not an identified installation). It is shown as context and is not counted as strong evidence.")
    tag = f"; {q.lower()}-quality context" if q else ""
    return (f"{_label(nearest['facility_type'])} facility within {nearest['distance_km']:.2f} km (spatial association{tag}). "
            "Facility proximity contributes contextual evidence; it does not establish that the facility is the thermal source.")


@router.get("/events/{event_id}")
def event_facility_context(event_id: str, db: Session = Depends(get_db)) -> dict:
    row = repo.get_event(db, event_id)
    if row is None:
        raise HTTPException(404, f"Event {event_id} not found")
    e = repo.event_to_schema(row)
    radius = get_settings().facility_context_radius_km
    if e.is_demo:   # synthetic fixture: its own facility only, never looked up in the real dataset
        f = repo.get_facility(db, e.facility_id) if e.facility_id else None
        nearest = ({"facility_id": f.facility_id, "name": f.name, "facility_type": f.facility_type, "latitude": f.latitude,
                    "longitude": f.longitude, "distance_km": e.facility_distance_km, "source": "DEMO", "country": None} if f else None)
        return {"event_id": event_id, "radius_km": radius, "nearest": nearest, "nearby": [nearest] if nearest else [], "nearby_count": 1 if nearest else 0,
                "statement": _statement(nearest, radius), "note": NEVER_CAUSATION, "dataset": "demo fixture"}
    idx = facility_ctx.get_index()
    hits = idx.near(e.centroid_lat, e.centroid_lon, radius)
    nearest = hits[0] if hits else None
    return {
        "event_id": event_id, "radius_km": radius, "nearest": nearest, "nearby": hits[:10], "nearby_count": len(hits),
        "quality_counts": dict(collections.Counter(h["context_quality"] for h in hits)),
        "quality_note": "Quality reflects only how specific the facility record is (type and name). It is not a probability and not proof of a source.",
        "statement": _statement(nearest, radius), "note": NEVER_CAUSATION, "distance_note": facility_ctx.DISTANCE_NOTE,
        "dataset": {"name": "OSM + GPPD facility context", "records_indexed": len(idx), "excluded_types": sorted(facility_ctx.EXCLUDED_TYPES)},
    }


@router.get("/facilities/near")
def facilities_near(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180),
                    radius_km: float = Query(3.0, gt=0, le=50), limit: int = Query(20, ge=1, le=100)) -> dict:
    hits = facility_ctx.get_index().near(lat, lon, radius_km)
    return {"radius_km": radius_km, "count": len(hits), "facilities": hits[:limit], "note": NEVER_CAUSATION}


@router.get("/live-summary")
def live_summary(db: Session = Depends(get_db)) -> dict:
    """Counts for the analytics page. NASA FIRMS confidence (per observation) and OrbiFlare severity (per event) are
    reported as separate distributions and are never combined."""
    obs = list(db.scalars(select(m.ObservationRecord)))
    live = [o for o in obs if o.source == "FIRMS"]
    events = list(db.scalars(select(m.EventRecord)))
    live_events = [e for e in events if not e.is_demo]
    dev_base = {d.event_id: (d.payload or {}).get("baseline_confidence") for d in db.scalars(select(m.DeviationRecord))}
    baseline = collections.Counter()
    for e in live_events:
        baseline[dev_base.get(e.event_id) if e.facility_id else "NO_FACILITY_CONTEXT"] += 1
    twins = collections.Counter(t.baseline_confidence for t in db.scalars(select(m.ThermalTwinRecord)))
    ts = sorted(o.timestamp for o in live)
    return {
        "firms_observations": {
            "total": len(live),
            "by_satellite": dict(collections.Counter(o.satellite or "unknown" for o in live)),
            "by_nasa_confidence": dict(collections.Counter(FIRMS_CONFIDENCE.get(o.confidence or "", "n/a") for o in live)),
            "first_acquisition": ts[0].isoformat() + "Z" if ts else None, "last_acquisition": ts[-1].isoformat() + "Z" if ts else None,
        },
        "events": {
            "live_total": len(live_events),
            "by_orbiflare_severity": dict(collections.Counter(e.severity or "UNSCORED" for e in live_events)),
            "with_facility_context": sum(1 for e in live_events if e.facility_id),
            "without_facility_context": sum(1 for e in live_events if not e.facility_id),
            "by_baseline": {k: baseline.get(k, 0) for k in ("ESTABLISHED", "LIMITED", "INSUFFICIENT", "NO_FACILITY_CONTEXT")},
            "multi_observation": sum(1 for e in live_events if e.observation_count > 1),
            "by_facility_context_quality": {k: sum(1 for e in live_events if e.facility_id and e.facility_context_quality == k) for k in ("HIGH", "MEDIUM", "LOW")},
        },
        "facilities_with_context": {"referenced": len({e.facility_id for e in live_events if e.facility_id}),
                                    "twins_by_baseline": {k: twins.get(k, 0) for k in ("ESTABLISHED", "LIMITED", "INSUFFICIENT")}},
        "purity": {"demo_observations": sum(1 for o in obs if o.source != "FIRMS"), "demo_events": len(events) - len(live_events)},
    }
