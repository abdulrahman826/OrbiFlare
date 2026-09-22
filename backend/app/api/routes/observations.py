from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.storage import repositories as repo
from app.storage.database import get_db

router = APIRouter(prefix="/observations", tags=["observations"])


@router.get("")
def list_observations(db: Session = Depends(get_db)) -> list[dict]:
    rows = repo.list_all_observations(db)
    return [repo.observation_to_schema(r).model_dump(mode="json") for r in rows]
