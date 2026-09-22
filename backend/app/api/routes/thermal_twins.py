from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.storage import repositories as repo
from app.storage.database import get_db

router = APIRouter(prefix="/thermal-twins", tags=["thermal-twins"])


@router.get("")
def list_thermal_twins(db: Session = Depends(get_db)) -> list[dict]:
    facilities = repo.list_facilities(db)
    twins = []
    for f in facilities:
        twin = repo.get_thermal_twin(db, f.facility_id)
        if twin:
            twins.append(twin.model_dump(mode="json"))
    return twins


@router.get("/{facility_id}")
def get_thermal_twin(facility_id: str, db: Session = Depends(get_db)) -> dict:
    twin = repo.get_thermal_twin(db, facility_id)
    if twin is None:
        raise HTTPException(404, f"No thermal twin computed for {facility_id}")
    return twin.model_dump(mode="json")
