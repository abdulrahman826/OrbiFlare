"""Data-access layer. Every DB read/write in the app goes through here so
routes and intelligence modules never touch SQLAlchemy directly.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.model import schemas as sc
from app.storage import models as m


# --- Facilities ---------------------------------------------------------

def upsert_facility(db: Session, f: sc.Facility) -> m.FacilityRecord:
    row = db.get(m.FacilityRecord, f.facility_id)
    if row is None:
        row = m.FacilityRecord(facility_id=f.facility_id)
        db.add(row)
    row.name = f.name
    row.facility_type = f.facility_type
    row.industry = f.industry
    row.latitude = f.latitude
    row.longitude = f.longitude
    row.source = f.source
    row.country = f.country
    row.state = f.state
    row.region = f.region
    row.is_demo = f.is_demo
    db.flush()
    return row


def list_facilities(db: Session, facility_type: Optional[str] = None) -> list[m.FacilityRecord]:
    stmt = select(m.FacilityRecord)
    if facility_type:
        stmt = stmt.where(m.FacilityRecord.facility_type == facility_type)
    return list(db.scalars(stmt))


def get_facility(db: Session, facility_id: str) -> Optional[m.FacilityRecord]:
    return db.get(m.FacilityRecord, facility_id)


def facility_to_schema(row: m.FacilityRecord) -> sc.Facility:
    return sc.Facility(
        facility_id=row.facility_id, name=row.name, facility_type=row.facility_type,
        industry=row.industry, latitude=row.latitude, longitude=row.longitude,
        source=row.source, country=row.country, state=row.state, region=row.region,
        is_demo=row.is_demo,
    )


# --- Observations --------------------------------------------------------

def bulk_insert_observations(db: Session, obs: list[sc.ThermalObservation]) -> int:
    count = 0
    for o in obs:
        existing = db.get(m.ObservationRecord, o.observation_id)
        if existing is not None:
            continue
        row = m.ObservationRecord(
            observation_id=o.observation_id, timestamp=o.timestamp, latitude=o.latitude,
            longitude=o.longitude, sensor=o.sensor.value, brightness_temperature=o.brightness_temperature,
            brightness_temperature_11=o.brightness_temperature_11, frp=o.frp, confidence=o.confidence,
            day_night=o.day_night.value if o.day_night else None, source=o.source.value,
            source_id=o.source_id, ingestion_time=o.ingestion_time,
            quality_flags=[q.value for q in o.quality_flags],
            satellite=o.satellite, instrument=o.instrument, scan=o.scan, track=o.track, source_product=o.source_product,
        )
        db.add(row)
        count += 1
    db.flush()
    return count


def list_unclustered_observations(db: Session) -> list[m.ObservationRecord]:
    stmt = select(m.ObservationRecord).where(m.ObservationRecord.event_id.is_(None)).order_by(m.ObservationRecord.timestamp)
    return list(db.scalars(stmt))


def list_all_observations(db: Session) -> list[m.ObservationRecord]:
    return list(db.scalars(select(m.ObservationRecord).order_by(m.ObservationRecord.timestamp)))


def list_observations_for_event(db: Session, event_id: str) -> list[m.ObservationRecord]:
    stmt = select(m.ObservationRecord).where(m.ObservationRecord.event_id == event_id).order_by(m.ObservationRecord.timestamp)
    return list(db.scalars(stmt))


def observation_to_schema(row: m.ObservationRecord) -> sc.ThermalObservation:
    return sc.ThermalObservation(
        observation_id=row.observation_id, timestamp=row.timestamp, latitude=row.latitude,
        longitude=row.longitude, sensor=row.sensor, brightness_temperature=row.brightness_temperature,
        brightness_temperature_11=row.brightness_temperature_11, frp=row.frp, confidence=row.confidence,
        day_night=row.day_night, source=row.source, source_id=row.source_id,
        ingestion_time=row.ingestion_time, quality_flags=row.quality_flags or [],
        satellite=row.satellite, instrument=row.instrument, scan=row.scan, track=row.track, source_product=row.source_product,
    )


# --- Events ---------------------------------------------------------------

def upsert_event(db: Session, e: sc.ThermalEvent) -> m.EventRecord:
    row = db.get(m.EventRecord, e.event_id)
    if row is None:
        row = m.EventRecord(event_id=e.event_id)
        db.add(row)
    row.first_detected = e.first_detected
    row.last_detected = e.last_detected
    row.duration_hours = e.duration_hours
    row.observation_count = e.observation_count
    row.peak_frp = e.peak_frp
    row.mean_frp = e.mean_frp
    row.peak_bt = e.peak_bt
    row.mean_bt = e.mean_bt
    row.centroid_lat = e.centroid_lat
    row.centroid_lon = e.centroid_lon
    row.footprint_radius_km = e.footprint_radius_km
    row.facility_id = e.facility_id
    row.facility_distance_km = e.facility_distance_km
    row.facility_context_quality = e.facility_context_quality
    row.status = e.status.value
    row.classification = e.classification.value if e.classification else None
    row.ml_p_industrial = e.ml_p_industrial
    row.ml_p_natural = e.ml_p_natural
    row.ml_anomaly_low_confidence = e.ml_anomaly_low_confidence
    row.risk_score = e.risk_score
    row.severity = e.severity.value if e.severity else None
    row.trajectory_direction = e.trajectory_direction.value if e.trajectory_direction else None
    row.is_demo = e.is_demo
    row.updated_at = datetime.utcnow()
    db.flush()
    return row


def assign_observations_to_event(db: Session, event_id: str, observation_ids: list[str]) -> None:
    db.query(m.ObservationRecord).filter(m.ObservationRecord.observation_id.in_(observation_ids)).update(
        {m.ObservationRecord.event_id: event_id}, synchronize_session=False
    )


def list_events(
    db: Session, severity: Optional[str] = None, status: Optional[str] = None,
    facility_id: Optional[str] = None, trajectory: Optional[str] = None,
    classification: Optional[str] = None,
) -> list[m.EventRecord]:
    stmt = select(m.EventRecord)
    if severity:
        stmt = stmt.where(m.EventRecord.severity == severity)
    if status:
        stmt = stmt.where(m.EventRecord.status == status)
    if facility_id:
        stmt = stmt.where(m.EventRecord.facility_id == facility_id)
    if trajectory:
        stmt = stmt.where(m.EventRecord.trajectory_direction == trajectory)
    if classification:
        stmt = stmt.where(m.EventRecord.classification == classification)
    stmt = stmt.order_by(m.EventRecord.risk_score.desc().nullslast())
    return list(db.scalars(stmt))


def get_event(db: Session, event_id: str) -> Optional[m.EventRecord]:
    return db.get(m.EventRecord, event_id)


def list_deviation_scores(db: Session, event_ids: list[str]) -> dict[str, float]:
    if not event_ids:
        return {}
    rows = db.execute(
        select(m.DeviationRecord.event_id, m.DeviationRecord.overall_deviation_score)
        .where(m.DeviationRecord.event_id.in_(event_ids))
    ).all()
    return {event_id: score for event_id, score in rows}


def attach_derived_event_fields(db: Session, events: list[sc.ThermalEvent]) -> list[sc.ThermalEvent]:
    """Bulk-attach read-model-only fields that aren't columns on EventRecord
    itself (deviation score, facility type, facility baseline confidence) so
    list/filter/sort views (Events page, GIS, reports, agent) can use them
    without an extra round-trip per event. Bulk-queried: O(events + distinct
    facilities), never per-event."""
    event_ids = [e.event_id for e in events]
    deviation_scores = list_deviation_scores(db, event_ids)

    facility_ids = {e.facility_id for e in events if e.facility_id}
    facility_type_by_id: dict[str, str] = {}
    baseline_confidence_by_id: dict[str, sc.BaselineConfidence] = {}
    for fid in facility_ids:
        f = get_facility(db, fid)
        if f:
            facility_type_by_id[fid] = f.facility_type
        twin = get_thermal_twin(db, fid)
        if twin:
            baseline_confidence_by_id[fid] = twin.baseline_confidence

    for e in events:
        e.overall_deviation_score = deviation_scores.get(e.event_id)
        if e.facility_id:
            e.facility_type = facility_type_by_id.get(e.facility_id)
            e.baseline_confidence = baseline_confidence_by_id.get(e.facility_id)
    return events


def event_to_schema(row: m.EventRecord) -> sc.ThermalEvent:
    return sc.ThermalEvent(
        event_id=row.event_id, first_detected=row.first_detected, last_detected=row.last_detected,
        duration_hours=row.duration_hours, observation_count=row.observation_count,
        peak_frp=row.peak_frp, mean_frp=row.mean_frp, peak_bt=row.peak_bt, mean_bt=row.mean_bt,
        centroid_lat=row.centroid_lat, centroid_lon=row.centroid_lon, footprint_radius_km=row.footprint_radius_km,
        facility_id=row.facility_id, facility_distance_km=row.facility_distance_km, facility_context_quality=row.facility_context_quality,
        status=row.status, classification=row.classification, ml_p_industrial=row.ml_p_industrial,
        ml_p_natural=row.ml_p_natural, ml_anomaly_low_confidence=row.ml_anomaly_low_confidence,
        risk_score=row.risk_score, severity=row.severity, trajectory_direction=row.trajectory_direction,
        is_demo=row.is_demo, created_at=row.created_at, updated_at=row.updated_at,
        source_observation_ids=[o.observation_id for o in row.observations],
    )


# --- Thermal twins ----------------------------------------------------------

def upsert_thermal_twin(db: Session, twin: sc.ThermalTwin) -> m.ThermalTwinRecord:
    row = db.get(m.ThermalTwinRecord, twin.facility_id)
    if row is None:
        row = m.ThermalTwinRecord(facility_id=twin.facility_id)
        db.add(row)
    row.baseline_confidence = twin.baseline_confidence.value
    row.payload = twin.model_dump(mode="json")
    row.computed_at = twin.computed_at
    db.flush()
    return row


def get_thermal_twin(db: Session, facility_id: str) -> Optional[sc.ThermalTwin]:
    row = db.get(m.ThermalTwinRecord, facility_id)
    if row is None:
        return None
    return sc.ThermalTwin.model_validate(row.payload)


# --- Deviation / Evidence / Risk / Trajectory (JSON-payload tables) --------

def upsert_deviation(db: Session, d: sc.Deviation) -> None:
    row = db.get(m.DeviationRecord, d.event_id)
    if row is None:
        row = m.DeviationRecord(event_id=d.event_id)
        db.add(row)
    row.facility_id = d.facility_id
    row.overall_deviation_score = d.overall_deviation_score
    row.payload = d.model_dump(mode="json")
    db.flush()


def get_deviation(db: Session, event_id: str) -> Optional[sc.Deviation]:
    row = db.get(m.DeviationRecord, event_id)
    return sc.Deviation.model_validate(row.payload) if row else None


def upsert_evidence(db: Session, ev: sc.EvidenceStack) -> None:
    row = db.get(m.EvidenceRecord, ev.event_id)
    if row is None:
        row = m.EvidenceRecord(event_id=ev.event_id)
        db.add(row)
    row.payload = ev.model_dump(mode="json")
    db.flush()


def get_evidence(db: Session, event_id: str) -> Optional[sc.EvidenceStack]:
    row = db.get(m.EvidenceRecord, event_id)
    return sc.EvidenceStack.model_validate(row.payload) if row else None


def upsert_risk(db: Session, r: sc.Risk) -> None:
    row = db.get(m.RiskAssessmentRecord, r.event_id)
    if row is None:
        row = m.RiskAssessmentRecord(event_id=r.event_id)
        db.add(row)
    row.risk_score = r.risk_score
    row.severity = r.severity.value
    row.payload = r.model_dump(mode="json")
    db.flush()


def get_risk(db: Session, event_id: str) -> Optional[sc.Risk]:
    row = db.get(m.RiskAssessmentRecord, event_id)
    return sc.Risk.model_validate(row.payload) if row else None


def replace_trajectory_points(db: Session, event_id: str, points: list[sc.TrajectoryPoint]) -> None:
    db.query(m.RiskTrajectoryPointRecord).filter(m.RiskTrajectoryPointRecord.event_id == event_id).delete()
    for p in points:
        db.add(m.RiskTrajectoryPointRecord(
            event_id=event_id, timestamp=p.timestamp, risk_score=p.risk_score,
            deviation_score=p.deviation_score, severity=p.severity.value,
        ))
    db.flush()


def get_trajectory_points(db: Session, event_id: str) -> list[m.RiskTrajectoryPointRecord]:
    stmt = select(m.RiskTrajectoryPointRecord).where(m.RiskTrajectoryPointRecord.event_id == event_id).order_by(m.RiskTrajectoryPointRecord.timestamp)
    return list(db.scalars(stmt))


# --- Alerts / lifecycle -----------------------------------------------------

def get_or_create_alert(db: Session, event_id: str) -> m.AlertRecord:
    row = db.get(m.AlertRecord, event_id)
    if row is None:
        row = m.AlertRecord(event_id=event_id, state=sc.AlertState.DETECTED.value)
        db.add(row)
        db.flush()
    return row


def set_alert_state(db: Session, event_id: str, new_state: str, actor: str, note: Optional[str] = None) -> m.AlertRecord:
    alert = get_or_create_alert(db, event_id)
    old_state = alert.state
    alert.state = new_state
    db.add(m.AlertHistoryRecord(event_id=event_id, from_state=old_state, to_state=new_state, actor=actor, note=note))
    ev = db.get(m.EventRecord, event_id)
    if ev is not None:
        ev.status = new_state
    db.flush()
    return alert


def add_alert_note(db: Session, event_id: str, note: str, actor: str = "system") -> None:
    """Audit-trail entry that records WHY something happened to an event without changing its lifecycle state."""
    alert = get_or_create_alert(db, event_id)
    db.add(m.AlertHistoryRecord(event_id=event_id, from_state=alert.state, to_state=alert.state, actor=actor, note=note))
    db.flush()


def list_alert_history(db: Session, event_id: str) -> list[m.AlertHistoryRecord]:
    stmt = select(m.AlertHistoryRecord).where(m.AlertHistoryRecord.event_id == event_id).order_by(m.AlertHistoryRecord.changed_at)
    return list(db.scalars(stmt))


# --- Data quality ------------------------------------------------------------

def record_data_quality(db: Session, rec: sc.DataQualityRecord) -> None:
    db.add(m.DataQualityRecordORM(
        batch_id=rec.batch_id, source=rec.source.value, ingested_at=rec.ingested_at,
        rows_received=rec.rows_received, rows_accepted=rec.rows_accepted,
        rows_flagged=rec.rows_flagged, rows_rejected=rec.rows_rejected, issues=rec.issues,
    ))
    db.flush()


def list_data_quality(db: Session) -> list[m.DataQualityRecordORM]:
    return list(db.scalars(select(m.DataQualityRecordORM).order_by(m.DataQualityRecordORM.ingested_at.desc())))
