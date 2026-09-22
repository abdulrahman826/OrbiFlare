"""Alert lifecycle state machine:

DETECTED -> VALIDATING -> ALERTED -> ESCALATED -> MONITORING -> EXTINGUISHED

All transitions are explicit operator actions and are fully auditable
(app.storage.models.AlertHistoryRecord). The AI/agent may never autonomously
mark an event EXTINGUISHED -- enforced here, not just by convention.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.model.schemas import ALERT_TRANSITIONS, AlertState
from app.storage import models as m
from app.storage import repositories as repo

AGENT_FORBIDDEN_STATES = {AlertState.EXTINGUISHED}


class InvalidTransitionError(Exception):
    pass


class ForbiddenActorTransitionError(Exception):
    pass


def transition(db: Session, event_id: str, to_state: AlertState, actor: str, note: str | None = None) -> m.AlertRecord:
    alert = repo.get_or_create_alert(db, event_id)
    from_state = AlertState(alert.state)

    if actor.lower() in ("agent", "ai", "system") and to_state in AGENT_FORBIDDEN_STATES:
        raise ForbiddenActorTransitionError("The AI agent may never autonomously mark an event EXTINGUISHED.")

    allowed = ALERT_TRANSITIONS.get(from_state, set())
    if to_state not in allowed and to_state != from_state:
        raise InvalidTransitionError(f"Cannot transition from {from_state.value} to {to_state.value}.")

    return repo.set_alert_state(db, event_id, to_state.value, actor, note)


def get_state(db: Session, event_id: str) -> AlertState:
    return AlertState(repo.get_or_create_alert(db, event_id).state)


def get_history(db: Session, event_id: str) -> list[m.AlertHistoryRecord]:
    return repo.list_alert_history(db, event_id)
