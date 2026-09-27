"""Loads the context needed for a source interpretation of one stored event (facility type, twin history, typed FIRMS history)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.intelligence import history_baseline as hb
from app.intelligence import source_interpretation as si
from app.model.schemas import ThermalEvent
from app.storage import repositories as repo


def interpretation_for(db: Session, event: ThermalEvent) -> si.Interpretation:
    ftype, hist = None, 0
    if event.facility_id:
        f = repo.get_facility(db, event.facility_id)
        ftype = f.facility_type if f else None
        twin = repo.get_thermal_twin(db, event.facility_id)
        hist = twin.historical_event_count if twin else 0
    typed, static = hb.get_store().type_counts(event.facility_id) if event.facility_id else (0, 0)
    return si.interpret(event, facility_type=ftype, history_events=hist, typed_history=typed, static_history=static)
