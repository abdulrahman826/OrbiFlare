from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.intelligence.investigation import get_investigation
from app.reporting.csv import events_to_csv
from app.reporting.geojson import events_to_geojson
from app.reference import context as ref_context, incidents as ref_incidents
from app.reporting.incident_report import build_historical_incident_report, build_incident_report
from app.storage import repositories as repo
from app.storage.database import get_db

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/event/{event_id}")
def generate_event_report(event_id: str, db: Session = Depends(get_db)) -> dict:
    inv = get_investigation(db, event_id)
    if inv is None:
        raise HTTPException(404, f"Event {event_id} not found")
    return build_incident_report(inv)


@router.post("/historical-incident/{incident_id}")
def generate_historical_incident_report(incident_id: str, db: Session = Depends(get_db)) -> dict:
    inc = ref_incidents.get_incident(incident_id)
    if inc is None:
        raise HTTPException(404, f"Historical incident {incident_id} not found")
    return build_historical_incident_report(ref_context.incident_context(db, inc))


@router.get("/events.csv")
def events_csv(db: Session = Depends(get_db)) -> Response:
    events = [repo.event_to_schema(r) for r in repo.list_events(db)]
    return Response(content=events_to_csv(events), media_type="text/csv",
                     headers={"Content-Disposition": "attachment; filename=orbiflare_events.csv"})


@router.get("/events.geojson")
def events_geojson(db: Session = Depends(get_db)) -> dict:
    events = [repo.event_to_schema(r) for r in repo.list_events(db)]
    return events_to_geojson(events)
