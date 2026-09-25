"""Read-only REFERENCE data API: historical incidents + India administrative boundaries.

Everything served here is labelled HISTORICAL_REFERENCE / GEOGRAPHIC_REFERENCE -- never live, never demo.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.reference import admin, context, incidents
from app.storage.database import get_db

router = APIRouter(prefix="/reference", tags=["reference"])


def _or_404(incident_id: str):
    inc = incidents.get_incident(incident_id)
    if inc is None:
        raise HTTPException(404, f"Historical incident {incident_id} not found")
    return inc


@router.get("/incidents")
def list_incidents(state: str | None = None, kind: str | None = None) -> list[dict]:
    return [i.model_dump(mode="json") for i in incidents.list_incidents(state=state, kind=kind)]


@router.get("/incidents/summary")
def incidents_summary() -> dict:
    return incidents.summary()


@router.get("/incidents/near")
def incidents_near(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180),
                   radius_km: float = Query(50.0, gt=0, le=1000)) -> list[dict]:
    return [{"distance_km": round(d, 2), "incident": i.model_dump(mode="json")} for i, d in context.incidents_near(lat, lon, radius_km)]


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str) -> dict:
    return _or_404(incident_id).model_dump(mode="json")


@router.get("/incidents/{incident_id}/context")
def get_incident_context(incident_id: str, radius_km: float = Query(50.0, gt=0, le=500), db: Session = Depends(get_db)) -> dict:
    return context.incident_context(db, _or_404(incident_id), radius_km).model_dump(mode="json")


@router.get("/admin-regions")
def admin_regions(level: str = "state", state: str | None = None) -> dict:
    if level not in ("state", "district"):
        raise HTTPException(422, "level must be 'state' or 'district'")
    return admin.feature_collection(level, state)


@router.get("/admin-regions/summary")
def admin_summary() -> dict:
    return admin.summary()


@router.get("/admin-regions/resolve")
def admin_resolve(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180)) -> dict:
    return admin.resolve(lat, lon).model_dump(mode="json")
