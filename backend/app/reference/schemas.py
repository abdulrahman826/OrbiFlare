"""Domain models for read-only REFERENCE data.

Reference data is deliberately a different concept from the operational data model:

  HistoricalIncident   != ThermalObservation (FIRMS)  != ThermalEvent  != Facility  != demo fixture

Nothing here is ever written to the operational database, fed to the ML pipeline, or shown as live.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

RecordKind = Literal[
    "REPORTED_INDUSTRIAL_INCIDENT",
    "PERSISTENT_THERMAL_SOURCE_REFERENCE",
    "AGRICULTURAL_BURNING_REFERENCE",
    "MEMORIAL_SITE_REFERENCE",
]

RECORD_KIND_LABEL: dict[str, str] = {
    "REPORTED_INDUSTRIAL_INCIDENT": "Reported industrial incident",
    "PERSISTENT_THERMAL_SOURCE_REFERENCE": "Persistent / flare thermal-source reference",
    "AGRICULTURAL_BURNING_REFERENCE": "Agricultural burning reference",
    "MEMORIAL_SITE_REFERENCE": "Memorial / site reference",
}

SOURCE_DATASET = "confirmed_incidents_india.csv"
REFERENCE_REPOSITORY = "siddiquezain/zero1@6059958"


class IncidentProvenance(BaseModel):
    source_dataset: str = SOURCE_DATASET
    reference_repository: str = REFERENCE_REPOSITORY
    source_label: str = Field(description="Per-record source string exactly as supplied (news/agency label).")
    data_mode: Literal["HISTORICAL_REFERENCE"] = "HISTORICAL_REFERENCE"
    status: Literal["HISTORICAL"] = "HISTORICAL"
    is_live_firms: bool = False
    is_demo: bool = False
    used_for_ml_training: bool = False
    per_record_verification: Literal["NOT_VERIFIED_BY_ORBIFLARE"] = "NOT_VERIFIED_BY_ORBIFLARE"


class HistoricalIncident(BaseModel):
    incident_id: str
    name: str
    date: str
    latitude: float
    longitude: float
    state: str
    facility_type: str
    description: str
    record_kind: RecordKind
    record_kind_label: str
    coordinate_precision: Literal["APPROXIMATE"] = "APPROXIMATE"
    coordinate_notes: list[str] = Field(default_factory=list)
    provenance: IncidentProvenance
    caveats: list[str]


class AdminResolution(BaseModel):
    state: Optional[str] = None
    district: Optional[str] = None
    resolved: bool = False
    boundary_source: str = "india_admin.geojson (udit-001/india-maps-data, simplified ~1.3 km)"


class NearbyFacility(BaseModel):
    facility_id: str
    name: str
    facility_type: str
    distance_km: float
    is_demo: bool


class NearbyEvent(BaseModel):
    event_id: str
    severity: Optional[str]
    risk_score: Optional[float]
    distance_km: float
    first_detected: str
    is_demo: bool


class FirmsMatchCheck(BaseModel):
    """Result of an honest spatial/temporal lookup against STORED non-demo FIRMS observations."""
    checked_against: str
    spatial_buffer_km: float
    temporal_window_days: int
    matching_firms_observations: int
    status: Literal["NO_FIRMS_MATCH", "FIRMS_OBSERVATIONS_PRESENT"]
    note: str


class IncidentContext(BaseModel):
    incident: HistoricalIncident
    admin: AdminResolution
    radius_km: float
    nearby_facilities: list[NearbyFacility]
    nearby_current_events: list[NearbyEvent]
    firms_match: FirmsMatchCheck
    known: list[str]
    unknown: list[str]
