"""SQLAlchemy ORM models.

Structured/scalar fields (used for filtering, sorting, indexing) are real
columns. Rich nested payloads produced by the intelligence layer (evidence
items, distribution summaries, trajectory points, ...) are stored as JSON
columns keyed by the Pydantic schema they mirror (app.model.schemas) — the
API layer re-hydrates them into typed models on read. This avoids an
exploding number of join tables for a hackathon-appropriate schema while
keeping every field queryable where it matters (timestamp, location,
facility_id, event_id, severity, status all have real indexed columns).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex[:12]


class FacilityRecord(Base):
    __tablename__ = "facilities"

    facility_id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, index=True)
    facility_type: Mapped[str] = mapped_column(String, index=True)
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    geometry_geojson: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String, default="DEMO")
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ObservationRecord(Base):
    __tablename__ = "observations"

    observation_id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    latitude: Mapped[float] = mapped_column(Float, index=True)
    longitude: Mapped[float] = mapped_column(Float, index=True)
    sensor: Mapped[str] = mapped_column(String)
    brightness_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    brightness_temperature_11: Mapped[float | None] = mapped_column(Float, nullable=True)
    frp: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String, nullable=True)
    day_night: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String, default="FIRMS")
    source_id: Mapped[str | None] = mapped_column(String, nullable=True)
    ingestion_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    quality_flags: Mapped[list] = mapped_column(JSON, default=list)
    satellite: Mapped[str | None] = mapped_column(String, nullable=True)
    instrument: Mapped[str | None] = mapped_column(String, nullable=True)
    scan: Mapped[float | None] = mapped_column(Float, nullable=True)
    track: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_product: Mapped[str | None] = mapped_column(String, nullable=True)
    event_id: Mapped[str | None] = mapped_column(String, ForeignKey("events.event_id"), nullable=True, index=True)

    __table_args__ = (Index("ix_observation_time_loc", "timestamp", "latitude", "longitude"),)


class EventRecord(Base):
    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    first_detected: Mapped[datetime] = mapped_column(DateTime, index=True)
    last_detected: Mapped[datetime] = mapped_column(DateTime, index=True)
    duration_hours: Mapped[float] = mapped_column(Float, default=0.0)
    observation_count: Mapped[int] = mapped_column(Integer, default=0)

    peak_frp: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_frp: Mapped[float | None] = mapped_column(Float, nullable=True)
    peak_bt: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_bt: Mapped[float | None] = mapped_column(Float, nullable=True)

    centroid_lat: Mapped[float] = mapped_column(Float, index=True)
    centroid_lon: Mapped[float] = mapped_column(Float, index=True)
    footprint_radius_km: Mapped[float] = mapped_column(Float, default=0.0)

    facility_id: Mapped[str | None] = mapped_column(String, ForeignKey("facilities.facility_id"), nullable=True, index=True)
    facility_distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    facility_context_quality: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(String, default="DETECTED", index=True)
    classification: Mapped[str | None] = mapped_column(String, nullable=True)
    ml_p_industrial: Mapped[float | None] = mapped_column(Float, nullable=True)
    ml_p_natural: Mapped[float | None] = mapped_column(Float, nullable=True)
    ml_anomaly_low_confidence: Mapped[bool] = mapped_column(Boolean, default=False)

    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    severity: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    trajectory_direction: Mapped[str | None] = mapped_column(String, nullable=True)

    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    observations = relationship("ObservationRecord", backref="event", lazy="select")


class ThermalTwinRecord(Base):
    __tablename__ = "thermal_twins"

    facility_id: Mapped[str] = mapped_column(String, ForeignKey("facilities.facility_id"), primary_key=True)
    baseline_confidence: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(JSON)  # full ThermalTwin schema, JSON-encoded
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DeviationRecord(Base):
    __tablename__ = "deviations"

    event_id: Mapped[str] = mapped_column(String, ForeignKey("events.event_id"), primary_key=True)
    facility_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    overall_deviation_score: Mapped[float] = mapped_column(Float, default=0.0)
    payload: Mapped[dict] = mapped_column(JSON)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EvidenceRecord(Base):
    __tablename__ = "evidence"

    event_id: Mapped[str] = mapped_column(String, ForeignKey("events.event_id"), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RiskAssessmentRecord(Base):
    __tablename__ = "risk_assessments"

    event_id: Mapped[str] = mapped_column(String, ForeignKey("events.event_id"), primary_key=True)
    risk_score: Mapped[float] = mapped_column(Float, index=True)
    severity: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RiskTrajectoryPointRecord(Base):
    __tablename__ = "risk_trajectory_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String, ForeignKey("events.event_id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    risk_score: Mapped[float] = mapped_column(Float)
    deviation_score: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String)


class AlertRecord(Base):
    __tablename__ = "alerts"

    event_id: Mapped[str] = mapped_column(String, ForeignKey("events.event_id"), primary_key=True)
    state: Mapped[str] = mapped_column(String, index=True, default="DETECTED")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AlertHistoryRecord(Base):
    __tablename__ = "alert_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String, ForeignKey("events.event_id"), index=True)
    from_state: Mapped[str | None] = mapped_column(String, nullable=True)
    to_state: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String, default="operator")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ConfirmedIncidentRecord(Base):
    __tablename__ = "confirmed_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String, ForeignKey("events.event_id"), index=True)
    confirmed_by: Mapped[str] = mapped_column(String)
    confirmation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DataQualityRecordORM(Base):
    __tablename__ = "data_quality_records"

    batch_id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    source: Mapped[str] = mapped_column(String)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    rows_received: Mapped[int] = mapped_column(Integer, default=0)
    rows_accepted: Mapped[int] = mapped_column(Integer, default=0)
    rows_flagged: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    issues: Mapped[dict] = mapped_column(JSON, default=dict)


class FirmsSyncStateRecord(Base):
    """Single-row (id=1) record of the last on-demand NASA FIRMS refresh -- kept separate from observations so
    'last sync' (when we asked NASA) and 'last acquisition' (when the satellite saw it) are never conflated."""
    __tablename__ = "firms_sync_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # last SUCCESSFUL sync
    last_status: Mapped[str | None] = mapped_column(String, nullable=True)          # OK | FAILED
    last_error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_product: Mapped[str | None] = mapped_column(String, nullable=True)
    satellites: Mapped[list] = mapped_column(JSON, default=list)
    last_acquisition: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received: Mapped[int] = mapped_column(Integer, default=0)
    new_observations: Mapped[int] = mapped_column(Integer, default=0)
    updated_observations: Mapped[int] = mapped_column(Integer, default=0)
