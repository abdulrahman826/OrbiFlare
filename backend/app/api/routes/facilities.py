from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.storage import repositories as repo
from app.storage.database import get_db

router = APIRouter(prefix="/facilities", tags=["facilities"])


@router.get("")
def list_facilities(facility_type: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    rows = repo.list_facilities(db, facility_type=facility_type)
    return [repo.facility_to_schema(r).model_dump(mode="json") for r in rows]


@router.get("/{facility_id}")
def get_facility(facility_id: str, db: Session = Depends(get_db)) -> dict:
    row = repo.get_facility(db, facility_id)
    if row is None:
        raise HTTPException(404, f"Facility {facility_id} not found")
    return repo.facility_to_schema(row).model_dump(mode="json")


@router.get("/{facility_id}/thermal-twin")
def get_facility_twin(facility_id: str, db: Session = Depends(get_db)) -> dict:
    twin = repo.get_thermal_twin(db, facility_id)
    if twin is None:
        raise HTTPException(404, f"No thermal twin computed for {facility_id}")
    return twin.model_dump(mode="json")


@router.get("/{facility_id}/events")
def get_facility_events(facility_id: str, db: Session = Depends(get_db)) -> list[dict]:
    rows = repo.list_events(db, facility_id=facility_id)
    return [repo.event_to_schema(r).model_dump(mode="json") for r in rows]
