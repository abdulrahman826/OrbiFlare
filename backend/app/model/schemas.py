"""Core domain schemas shared across ingestion, intelligence, storage and API.

These are the typed contracts described in the OrbiFlare data model: a
thermal OBSERVATION is raw satellite data; observations are grouped into
living thermal EVENTS; each event is enriched with FACILITY context; a
facility's historical behaviour is summarized as a THERMAL TWIN; the event is
compared against the twin to produce a DEVIATION; deviation + ML output are
fused into EVIDENCE; evidence drives a RISK score; risk over time is a
TRAJECTORY.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Sensor(str, Enum):
    VIIRS = "VIIRS"
    MODIS = "MODIS"
    SYNTHETIC = "SYNTHETIC"


class DayNight(str, Enum):
    DAY = "D"
    NIGHT = "N"


class DataSource(str, Enum):
    FIRMS = "FIRMS"
    DEMO = "DEMO"
    MANUAL = "MANUAL"


class QualityFlag(str, Enum):
    OK = "OK"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    MISSING_BT = "MISSING_BT"
    MISSING_FRP = "MISSING_FRP"
    INTERPOLATED_TIMESTAMP = "INTERPOLATED_TIMESTAMP"
    DUPLICATE_SUSPECTED = "DUPLICATE_SUSPECTED"
    OUT_OF_RANGE_COORDINATES = "OUT_OF_RANGE_COORDINATES"


class BaselineConfidence(str, Enum):
    ESTABLISHED = "ESTABLISHED"
    LIMITED = "LIMITED"
    INSUFFICIENT = "INSUFFICIENT"


class DeviationStatus(str, Enum):
    COMPUTED = "COMPUTED"
    INSUFFICIENT_BASELINE = "INSUFFICIENT_BASELINE"


class EvidenceCategory(str, Enum):
    THERMAL = "THERMAL"
    TEMPORAL = "TEMPORAL"
    BEHAVIOURAL = "BEHAVIOURAL"
    FACILITY = "FACILITY"
    GIS = "GIS"
    ML = "ML"


class EvidenceDirection(str, Enum):
    SUPPORTING = "SUPPORTING"
    CONTRADICTING = "CONTRADICTING"
    UNCERTAIN = "UNCERTAIN"
    UNAVAILABLE = "UNAVAILABLE"


class EvidenceStrength(str, Enum):
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TrajectoryDirection(str, Enum):
    STABLE = "STABLE"
    INCREASING = "INCREASING"
    ESCALATING = "ESCALATING"
    DECREASING = "DECREASING"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class AlertState(str, Enum):
    DETECTED = "DETECTED"
    VALIDATING = "VALIDATING"
    ALERTED = "ALERTED"
    ESCALATED = "ESCALATED"
    MONITORING = "MONITORING"
    EXTINGUISHED = "EXTINGUISHED"


# Valid forward transitions for the alert lifecycle state machine.
ALERT_TRANSITIONS: dict[AlertState, set[AlertState]] = {
    AlertState.DETECTED: {AlertState.VALIDATING, AlertState.ALERTED},
    AlertState.VALIDATING: {AlertState.ALERTED, AlertState.MONITORING, AlertState.EXTINGUISHED},
    AlertState.ALERTED: {AlertState.ESCALATED, AlertState.MONITORING, AlertState.EXTINGUISHED},
    AlertState.ESCALATED: {AlertState.MONITORING, AlertState.EXTINGUISHED},
    AlertState.MONITORING: {AlertState.ESCALATED, AlertState.EXTINGUISHED, AlertState.ALERTED},
    AlertState.EXTINGUISHED: set(),
}


class MLClass(str, Enum):
    PERSISTENT_INDUSTRIAL = "PERSISTENT_INDUSTRIAL_THERMAL_SOURCE"
    NATURAL_CANDIDATE = "NATURAL_AGRICULTURAL_FIRE_CANDIDATE"


# ---------------------------------------------------------------------------
# Thermal observation
# ---------------------------------------------------------------------------

class ThermalObservation(BaseModel):
    observation_id: str
    timestamp: datetime
    latitude: float
    longitude: float
    sensor: Sensor
    brightness_temperature: Optional[float] = Field(None, description="BT (I-4/Ch21), Kelvin")
    brightness_temperature_11: Optional[float] = Field(None, description="BT (I-5/Ch31), Kelvin")
    frp: Optional[float] = Field(None, description="Fire Radiative Power, MW")
    confidence: Optional[str] = None
    day_night: Optional[DayNight] = None
    source: DataSource = DataSource.FIRMS
    source_id: Optional[str] = None
    ingestion_time: datetime = Field(default_factory=datetime.utcnow)
    quality_flags: list[QualityFlag] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Thermal event
# ---------------------------------------------------------------------------

class ThermalEvent(BaseModel):
    event_id: str
    first_detected: datetime
    last_detected: datetime
    duration_hours: float
    observation_count: int

    peak_frp: Optional[float] = None
    mean_frp: Optional[float] = None
    peak_bt: Optional[float] = None
    mean_bt: Optional[float] = None

    centroid_lat: float
    centroid_lon: float
    footprint_radius_km: float = 0.0

    facility_id: Optional[str] = None
    facility_distance_km: Optional[float] = None

    status: AlertState = AlertState.DETECTED
    classification: Optional[MLClass] = None
    ml_p_industrial: Optional[float] = None
    ml_p_natural: Optional[float] = None
    ml_anomaly_low_confidence: bool = False

    risk_score: Optional[float] = None
    severity: Optional[Severity] = None
    trajectory_direction: Optional[TrajectoryDirection] = None

    is_demo: bool = False

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    source_observation_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Facility
# ---------------------------------------------------------------------------

class Facility(BaseModel):
    facility_id: str
    name: str
    facility_type: str
    industry: Optional[str] = None
    latitude: float
    longitude: float
    source: str = "DEMO"
    country: Optional[str] = None
    state: Optional[str] = None
    region: Optional[str] = None
    is_demo: bool = False


# ---------------------------------------------------------------------------
# Thermal twin (facility behavioural baseline)
# ---------------------------------------------------------------------------

class DistributionSummary(BaseModel):
    """Robust distribution summary: median + MAD/IQR rather than mean/stdev."""
    n: int
    median: Optional[float] = None
    mad: Optional[float] = None
    q25: Optional[float] = None
    q75: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None


class ThermalTwin(BaseModel):
    facility_id: str
    baseline_confidence: BaselineConfidence

    history_start: Optional[datetime] = None
    history_end: Optional[datetime] = None
    historical_event_count: int = 0
    historical_observation_count: int = 0

    normal_frp: DistributionSummary
    normal_bt: DistributionSummary
    normal_persistence: DistributionSummary
    normal_duration: DistributionSummary
    normal_recurrence_days: Optional[float] = None

    normal_day_night_pattern: dict[str, float] = Field(default_factory=dict)
    normal_hour_pattern: dict[str, float] = Field(default_factory=dict)
    normal_seasonal_pattern: dict[str, float] = Field(default_factory=dict)

    normal_spatial_centroid_lat: Optional[float] = None
    normal_spatial_centroid_lon: Optional[float] = None
    normal_spatial_radius_km: Optional[float] = None

    is_demo: bool = False
    computed_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Deviation
# ---------------------------------------------------------------------------

class DimensionDeviation(BaseModel):
    dimension: str
    status: DeviationStatus
    observed_value: Optional[float] = None
    expected_median: Optional[float] = None
    expected_range: Optional[tuple[float, float]] = None
    robust_z: Optional[float] = None
    is_notable: bool = False
    is_significant: bool = False
    explanation: str


class Deviation(BaseModel):
    event_id: str
    facility_id: Optional[str] = None
    baseline_confidence: BaselineConfidence

    intensity: DimensionDeviation
    persistence: DimensionDeviation
    duration: DimensionDeviation
    temporal: DimensionDeviation
    spatial: DimensionDeviation
    recurrence: DimensionDeviation

    overall_deviation_score: float = 0.0
    explanations: list[str] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

class EvidenceItem(BaseModel):
    category: EvidenceCategory
    name: str
    observed_value: Optional[str] = None
    expected_value: Optional[str] = None
    source: str
    direction: EvidenceDirection
    strength: Optional[EvidenceStrength] = None
    explanation: str
    related_to: list[str] = Field(default_factory=list, description="Names of correlated evidence items")


class EvidenceStack(BaseModel):
    event_id: str
    supporting_evidence: list[EvidenceItem] = Field(default_factory=list)
    contradicting_evidence: list[EvidenceItem] = Field(default_factory=list)
    uncertain_evidence: list[EvidenceItem] = Field(default_factory=list)
    unavailable_evidence: list[EvidenceItem] = Field(default_factory=list)
    correlation_notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Alternative explanations
# ---------------------------------------------------------------------------

class Hypothesis(BaseModel):
    label: str
    rationale: str
    supporting_evidence_names: list[str] = Field(default_factory=list)
    contradicting_evidence_names: list[str] = Field(default_factory=list)


class AlternativeExplanations(BaseModel):
    event_id: str
    primary_hypothesis: Hypothesis
    alternatives: list[Hypothesis] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------

class RiskFactor(BaseModel):
    name: str
    contribution: float
    explanation: str


class Risk(BaseModel):
    event_id: str
    risk_score: float
    severity: Severity
    risk_factors: list[RiskFactor] = Field(default_factory=list)
    explanation: str
    caveats: list[str] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Trajectory
# ---------------------------------------------------------------------------

class TrajectoryPoint(BaseModel):
    timestamp: datetime
    risk_score: float
    deviation_score: float
    severity: Severity


class RiskTrajectory(BaseModel):
    event_id: str
    points: list[TrajectoryPoint] = Field(default_factory=list)
    direction: TrajectoryDirection
    explanation: str


# ---------------------------------------------------------------------------
# ML output
# ---------------------------------------------------------------------------

class MLPrediction(BaseModel):
    event_id: str
    p_persistent_industrial: float
    p_natural_candidate: float
    predicted_class: MLClass
    low_confidence: bool
    feature_values: dict[str, float] = Field(default_factory=dict)
    feature_importance: dict[str, float] = Field(default_factory=dict)
    model_version: str
    is_proxy_label_model: bool = True


# ---------------------------------------------------------------------------
# Investigation (full aggregate)
# ---------------------------------------------------------------------------

class Investigation(BaseModel):
    event: ThermalEvent
    observations: list[ThermalObservation]
    facility: Optional[Facility] = None
    thermal_twin: Optional[ThermalTwin] = None
    deviation: Optional[Deviation] = None
    ml_prediction: Optional[MLPrediction] = None
    evidence: Optional[EvidenceStack] = None
    alternative_explanations: Optional[AlternativeExplanations] = None
    risk: Optional[Risk] = None
    trajectory: Optional[RiskTrajectory] = None
    uncertainty_notes: list[str] = Field(default_factory=list)
    operator_state: AlertState = AlertState.DETECTED
    operator_history: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Event Replay
# ---------------------------------------------------------------------------

class ReplayFrame(BaseModel):
    step: int
    observation: ThermalObservation
    cumulative_observation_count: int
    cumulative_peak_frp: Optional[float] = None
    cumulative_mean_frp: Optional[float] = None
    cumulative_peak_bt: Optional[float] = None
    centroid_lat: float
    centroid_lon: float
    footprint_radius_km: float
    deviation_score: float
    risk_score: float
    severity: Severity


class EventReplay(BaseModel):
    event_id: str
    frames: list[ReplayFrame]
    is_deterministic: bool = True
    note: str = "Replay shows only real recorded observations in chronological order; no intermediate data is fabricated."


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------

class DataQualityRecord(BaseModel):
    batch_id: str
    source: DataSource
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    rows_received: int
    rows_accepted: int
    rows_flagged: int
    rows_rejected: int
    issues: dict[str, int] = Field(default_factory=dict)
