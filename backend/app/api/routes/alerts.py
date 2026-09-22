from __future__ import annotations

from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from app.alerts import lifecycle, store
from app.storage.database import get_db

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
def list_active_alerts(db: Session = Depends(get_db)) -> list[dict]:
    return store.list_active_alerts(db)


@router.get("/{event_id}/history")
def alert_history(event_id: str, db: Session = Depends(get_db)) -> list[dict]:
    rows = lifecycle.get_history(db, event_id)
    return [{"from_state": r.from_state, "to_state": r.to_state, "actor": r.actor, "note": r.note,
             "changed_at": r.changed_at.isoformat()} for r in rows]
