from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.reporting.geojson import events_to_geojson, facilities_to_geojson
from app.storage import repositories as repo
from app.storage.database import get_db

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/events")
def map_events(db: Session = Depends(get_db)) -> dict:
    events = [repo.event_to_schema(r) for r in repo.list_events(db)]
    return events_to_geojson(events)


@router.get("/facilities")
def map_facilities(db: Session = Depends(get_db)) -> dict:
    facilities = [repo.facility_to_schema(r) for r in repo.list_facilities(db)]
    return facilities_to_geojson(facilities)
