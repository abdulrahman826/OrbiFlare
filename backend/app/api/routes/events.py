from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.alerts import lifecycle
from app.api.schemas import AlertTransitionRequest
from app.intelligence.replay import build_replay
from app.intelligence.trajectory import compute_trajectory
from app.model.schemas import AlertState
from app.storage import repositories as repo
from app.storage.database import get_db

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
def list_events(
    severity: str | None = None, status: str | None = None, facility_id: str | None = None,
    trajectory: str | None = None, classification: str | None = None, db: Session = Depends(get_db),
) -> list[dict]:
    rows = repo.list_events(db, severity=severity, status=status, facility_id=facility_id,
                             trajectory=trajectory, classification=classification)
    events = repo.attach_derived_event_fields(db, [repo.event_to_schema(r) for r in rows])
    return [e.model_dump(mode="json") for e in events]


@router.get("/{event_id}")
def get_event(event_id: str, db: Session = Depends(get_db)) -> dict:
    row = repo.get_event(db, event_id)
    if row is None:
        raise HTTPException(404, f"Event {event_id} not found")
    event = repo.attach_derived_event_fields(db, [repo.event_to_schema(row)])[0]
    return event.model_dump(mode="json")


@router.get("/{event_id}/timeline")
def event_timeline(event_id: str, db: Session = Depends(get_db)) -> dict:
    row = repo.get_event(db, event_id)
    if row is None:
        raise HTTPException(404, f"Event {event_id} not found")
    obs = [repo.observation_to_schema(o).model_dump(mode="json") for o in repo.list_observations_for_event(db, event_id)]
    return {"event_id": event_id, "observations": obs}


@router.get("/{event_id}/deviation")
def event_deviation(event_id: str, db: Session = Depends(get_db)) -> dict:
    d = repo.get_deviation(db, event_id)
    if d is None:
        raise HTTPException(404, f"No deviation computed for {event_id}")
    return d.model_dump(mode="json")


@router.get("/{event_id}/evidence")
def event_evidence(event_id: str, db: Session = Depends(get_db)) -> dict:
    e = repo.get_evidence(db, event_id)
    if e is None:
        raise HTTPException(404, f"No evidence computed for {event_id}")
    return e.model_dump(mode="json")


@router.get("/{event_id}/risk")
def event_risk(event_id: str, db: Session = Depends(get_db)) -> dict:
    r = repo.get_risk(db, event_id)
    if r is None:
        raise HTTPException(404, f"No risk computed for {event_id}")
    return r.model_dump(mode="json")


@router.get("/{event_id}/trajectory")
def event_trajectory(event_id: str, db: Session = Depends(get_db)) -> dict:
    row = repo.get_event(db, event_id)
    if row is None:
        raise HTTPException(404, f"Event {event_id} not found")
    event = repo.event_to_schema(row)
    obs = [repo.observation_to_schema(o) for o in repo.list_observations_for_event(db, event_id)]
    twin = repo.get_thermal_twin(db, event.facility_id) if event.facility_id else None
    traj, _ = compute_trajectory(obs, twin, event.facility_id, event.facility_distance_km, event_id, event.facility_context_quality)
    return traj.model_dump(mode="json")


@router.get("/{event_id}/replay")
def event_replay(event_id: str, db: Session = Depends(get_db)) -> dict:
    row = repo.get_event(db, event_id)
    if row is None:
        raise HTTPException(404, f"Event {event_id} not found")
    event = repo.event_to_schema(row)
    obs = [repo.observation_to_schema(o) for o in repo.list_observations_for_event(db, event_id)]
    twin = repo.get_thermal_twin(db, event.facility_id) if event.facility_id else None
    replay = build_replay(event_id, obs, twin, event.facility_id, event.facility_distance_km, event.facility_context_quality)
    return replay.model_dump(mode="json")


@router.get("/{event_id}/investigation")
def event_investigation(event_id: str, db: Session = Depends(get_db)) -> dict:
    from app.intelligence.investigation import get_investigation
    inv = get_investigation(db, event_id)
    if inv is None:
        raise HTTPException(404, f"Event {event_id} not found")
    return inv.model_dump(mode="json")


@router.post("/{event_id}/transition")
def transition_event(event_id: str, body: AlertTransitionRequest, db: Session = Depends(get_db)) -> dict:
    row = repo.get_event(db, event_id)
    if row is None:
        raise HTTPException(404, f"Event {event_id} not found")
    try:
        to_state = AlertState(body.to_state)
    except ValueError:
        raise HTTPException(400, f"Invalid state {body.to_state!r}")
    try:
        alert = lifecycle.transition(db, event_id, to_state, body.actor, body.note)
    except lifecycle.InvalidTransitionError as exc:
        raise HTTPException(409, str(exc))
    except lifecycle.ForbiddenActorTransitionError as exc:
        raise HTTPException(403, str(exc))
    db.commit()
    return {"event_id": event_id, "state": alert.state}
