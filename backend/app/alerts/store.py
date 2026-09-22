"""Thin alert-domain accessors over the shared repository layer -- kept as
its own module so alert read paths are easy to find/mock independently of
the general storage repositories.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.model.schemas import AlertState
from app.storage import repositories as repo


def confirm_incident(db: Session, event_id: str, confirmed_by: str, note: str | None = None) -> None:
    from app.storage import models as m
    db.add(m.ConfirmedIncidentRecord(event_id=event_id, confirmed_by=confirmed_by, confirmation_note=note))
    db.commit()


def list_active_alerts(db: Session) -> list[dict]:
    events = repo.list_events(db)
    return [
        {"event_id": e.event_id, "state": e.status, "severity": e.severity, "risk_score": e.risk_score}
        for e in events if e.status != AlertState.EXTINGUISHED.value
    ]
