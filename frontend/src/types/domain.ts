// Mirrors backend/app/model/schemas.py -- kept in sync by hand since this
// is a single-team hackathon-scoped project (no codegen step).

export type Severity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type TrajectoryDirection = "STABLE" | "INCREASING" | "ESCALATING" | "DECREASING" | "INSUFFICIENT_DATA";
export type AlertState = "DETECTED" | "VALIDATING" | "ALERTED" | "ESCALATED" | "MONITORING" | "EXTINGUISHED";
export type BaselineConfidence = "ESTABLISHED" | "LIMITED" | "INSUFFICIENT";
export type MLClass = "PERSISTENT_INDUSTRIAL_THERMAL_SOURCE" | "NATURAL_AGRICULTURAL_FIRE_CANDIDATE";
export type DeviationStatus = "COMPUTED" | "INSUFFICIENT_BASELINE";
export type EvidenceDirection = "SUPPORTING" | "CONTRADICTING" | "UNCERTAIN" | "UNAVAILABLE";
export type EvidenceCategory = "THERMAL" | "TEMPORAL" | "BEHAVIOURAL" | "FACILITY" | "GIS" | "ML";

export interface ThermalObservation {
  observation_id: string;
  timestamp: string;
  latitude: number;
  longitude: number;
  sensor: string;
  brightness_temperature: number | null;
  brightness_temperature_11: number | null;
  frp: number | null;
  confidence: string | null;
  day_night: string | null;
  source: string;
  source_id: string | null;
  quality_flags: string[];
  satellite: string | null;
  instrument: string | null;
  scan: number | null;
  track: number | null;
  source_product: string | null;
  is_live_firms: boolean;
}

export interface ThermalEvent {
  event_id: string;
  first_detected: string;
  last_detected: string;
  duration_hours: number;
  observation_count: number;
  peak_frp: number | null;
  mean_frp: number | null;
  peak_bt: number | null;
  mean_bt: number | null;
  centroid_lat: number;
  centroid_lon: number;
  footprint_radius_km: number;
  facility_id: string | null;
  facility_distance_km: number | null;
  facility_context_quality: ContextQuality | null;
  status: AlertState;
  classification: MLClass | null;
  ml_p_industrial: number | null;
  ml_p_natural: number | null;
  ml_anomaly_low_confidence: boolean;
  risk_score: number | null;
  severity: Severity | null;
  trajectory_direction: TrajectoryDirection | null;
  is_demo: boolean;
  is_live_firms: boolean;
  source_observation_ids: string[];
  overall_deviation_score: number | null;
  facility_type: string | null;
  baseline_confidence: BaselineConfidence | null;
}

export interface Facility {
  facility_id: string;
  name: string;
  facility_type: string;
  industry: string | null;
  latitude: number;
  longitude: number;
  source: string;
  country: string | null;
  state: string | null;
  region: string | null;
  is_demo: boolean;
}

export interface DistributionSummary {
  n: number;
  median: number | null;
  mad: number | null;
  q25: number | null;
  q75: number | null;
  min: number | null;
  max: number | null;
}

export interface ThermalTwin {
  facility_id: string;
  baseline_confidence: BaselineConfidence;
  history_start: string | null;
  history_end: string | null;
  historical_event_count: number;
  historical_observation_count: number;
  normal_frp: DistributionSummary;
  normal_bt: DistributionSummary;
  normal_persistence: DistributionSummary;
  normal_duration: DistributionSummary;
  normal_recurrence_days: number | null;
  normal_day_night_pattern: Record<string, number>;
  normal_hour_pattern: Record<string, number>;
  normal_seasonal_pattern: Record<string, number>;
  normal_spatial_centroid_lat: number | null;
  normal_spatial_centroid_lon: number | null;
  normal_spatial_radius_km: number | null;
  is_demo: boolean;
  computed_at: string;
}

export interface DimensionDeviation {
  dimension: string;
  status: DeviationStatus;
  observed_value: number | null;
  expected_median: number | null;
  expected_range: [number, number] | null;
  robust_z: number | null;
  is_notable: boolean;
  is_significant: boolean;
  explanation: string;
}

export interface Deviation {
  event_id: string;
  facility_id: string | null;
  baseline_confidence: BaselineConfidence;
  intensity: DimensionDeviation;
  persistence: DimensionDeviation;
  duration: DimensionDeviation;
  temporal: DimensionDeviation;
  spatial: DimensionDeviation;
  recurrence: DimensionDeviation;
  overall_deviation_score: number;
  explanations: string[];
}

export interface EvidenceItem {
  category: EvidenceCategory;
  name: string;
  observed_value: string | null;
  expected_value: string | null;
  source: string;
  direction: EvidenceDirection;
  strength: "WEAK" | "MODERATE" | "STRONG" | null;
  explanation: string;
  related_to: string[];
}

export interface EvidenceStack {
  event_id: string;
  supporting_evidence: EvidenceItem[];
  contradicting_evidence: EvidenceItem[];
  uncertain_evidence: EvidenceItem[];
  unavailable_evidence: EvidenceItem[];
  correlation_notes: string[];
}

export interface Hypothesis {
  label: string;
  rationale: string;
  supporting_evidence_names: string[];
  contradicting_evidence_names: string[];
}

export interface AlternativeExplanations {
  event_id: string;
  primary_hypothesis: Hypothesis;
  alternatives: Hypothesis[];
  unknowns: string[];
}

export type ContextQuality = "HIGH" | "MEDIUM" | "LOW";

export interface RiskFactor {
  name: string;
  contribution: number;
  explanation: string;
}

export interface Risk {
  event_id: string;
  risk_score: number;
  severity: Severity;
  risk_factors: RiskFactor[];
  explanation: string;
  caveats: string[];
  baseline_status?: BaselineConfidence | null;
  deviation_contribution?: number | null;
  deviation_contribution_cap?: number | null;
  facility_context_quality?: ContextQuality | null;
  contributing?: string[];
  limiting?: string[];
  missing_evidence?: string[];
  escalation_evidence?: string[];
  severity_reason?: string;
}

export interface TrajectoryPoint {
  timestamp: string;
  risk_score: number;
  deviation_score: number;
  severity: Severity;
}

export interface RiskTrajectory {
  event_id: string;
  points: TrajectoryPoint[];
  direction: TrajectoryDirection;
  explanation: string;
}

export interface MLPrediction {
  event_id: string;
  p_persistent_industrial: number;
  p_natural_candidate: number;
  predicted_class: MLClass;
  low_confidence: boolean;
  feature_values: Record<string, number>;
  feature_importance: Record<string, number>;
  model_version: string;
  is_proxy_label_model: boolean;
  facility_context_state?: "USABLE" | "LOW_QUALITY" | "NONE";
  model_variant?: "full" | "no_facility";
}

export interface ReplayFrame {
  step: number;
  observation: ThermalObservation;
  cumulative_observation_count: number;
  cumulative_peak_frp: number | null;
  cumulative_mean_frp: number | null;
  cumulative_peak_bt: number | null;
  centroid_lat: number;
  centroid_lon: number;
  footprint_radius_km: number;
  deviation_score: number;
  risk_score: number;
  severity: Severity;
}

export interface EventReplay {
  event_id: string;
  frames: ReplayFrame[];
  is_deterministic: boolean;
  note: string;
}

export interface OperatorHistoryEntry {
  from_state: string | null;
  to_state: string;
  actor: string;
  note: string | null;
  changed_at: string;
}

export interface Investigation {
  event: ThermalEvent;
  observations: ThermalObservation[];
  facility: Facility | null;
  thermal_twin: ThermalTwin | null;
  deviation: Deviation | null;
  ml_prediction: MLPrediction | null;
  evidence: EvidenceStack | null;
  alternative_explanations: AlternativeExplanations | null;
  risk: Risk | null;
  trajectory: RiskTrajectory | null;
  uncertainty_notes: string[];
  operator_state: AlertState;
  operator_history: OperatorHistoryEntry[];
}

export interface AnalyticsOverview {
  total_events: number;
  total_facilities: number;
  by_severity: Record<string, number>;
  escalating_events: number;
  high_risk_events: number;
  facilities_with_established_baseline: number;
  demo_events: number;
}

export interface EvaluationMetrics {
  model_version: string;
  trained_at: string;
  n_train: number;
  n_val: number;
  split_strategy: string;
  accuracy: number;
  precision: Record<string, number>;
  recall: Record<string, number>;
  f1: Record<string, number>;
  roc_auc: number | null;
  confusion_matrix: { labels: string[]; matrix: number[][] };
  feature_importance: Record<string, number>;
  is_proxy_label_model: boolean;
  caveats: string[];
  balanced_accuracy?: number | null;
  macro_f1?: number | null;
  weighted_f1?: number | null;
  evaluation_kind?: string;
  feature_schema_version?: string;
  label_rule_inputs?: string[];
  features_overlapping_label_rule?: string[];
  no_facility_model?: { macro_f1: number; accuracy: number; balanced_accuracy: number; roc_auc: number | null; features: string[] } | null;
  ablations?: { without_facility_distance: { macro_f1: number }; without_persistence: { macro_f1: number } } | null;
}

export interface AgentResultCard {
  type: string;
  title: string;
  subtitle: string | null;
  data: Record<string, unknown>;
}

export interface GeoFeatureCollection {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: Record<string, unknown>;
  }[];
}

export interface AgentResponse {
  text: string;
  tool_calls: { tool: string; arguments: Record<string, unknown>; result_summary: string }[];
  result_cards: AgentResultCard[];
  ui_action: { action: string; target_id: string | null } | null;
}

// ---------------------------------------------------------------------------
// Reference data (HISTORICAL / GEOGRAPHIC) -- never live, never FIRMS detections.
// ---------------------------------------------------------------------------

export type IncidentKind =
  | "REPORTED_INDUSTRIAL_INCIDENT"
  | "PERSISTENT_THERMAL_SOURCE_REFERENCE"
  | "AGRICULTURAL_BURNING_REFERENCE"
  | "MEMORIAL_SITE_REFERENCE";

export interface HistoricalIncident {
  incident_id: string;
  name: string;
  date: string;
  latitude: number;
  longitude: number;
  state: string;
  facility_type: string;
  description: string;
  record_kind: IncidentKind;
  record_kind_label: string;
  coordinate_precision: "APPROXIMATE";
  coordinate_notes: string[];
  provenance: {
    source_label: string;
    data_mode: "HISTORICAL_REFERENCE";
    status: "HISTORICAL";
    is_live_firms: boolean;
    is_demo: boolean;
    used_for_ml_training: boolean;
    per_record_verification: string;
  };
  caveats: string[];
}

export interface IncidentContext {
  incident: HistoricalIncident;
  admin: { state: string | null; district: string | null; resolved: boolean };
  radius_km: number;
  nearby_facilities: { facility_id: string; name: string; facility_type: string; distance_km: number; is_demo: boolean }[];
  nearby_current_events: { event_id: string; severity: Severity | null; risk_score: number | null; distance_km: number; first_detected: string; is_demo: boolean }[];
  firms_match: {
    checked_against: string; spatial_buffer_km: number; temporal_window_days: number;
    matching_firms_observations: number; status: "NO_FIRMS_MATCH" | "FIRMS_OBSERVATIONS_PRESENT"; note: string;
  };
  known: string[];
  unknown: string[];
}

export interface IncidentSummary {
  total: number;
  by_record_kind: Record<string, number>;
  by_state: Record<string, number>;
  date_range: [string, string] | null;
  provenance: { data_mode: string; status: string; is_live_firms: boolean; used_for_ml_training: boolean; firms_match_note: string };
}

export interface AdminFeatureCollection {
  type: "FeatureCollection";
  features: { type: "Feature"; geometry: unknown; properties: { kind: string; state: string; district?: string } }[];
  provenance: { dataset: string; level: string; data_mode: string; note: string; feature_count: number };
}

export type DataMode = "LIVE_FIRMS" | "DEMO" | "MIXED" | "EMPTY";

export interface Health {
  status: string;
  mode: string;
  database: string;
  data_mode: DataMode;
  live_firms_observations: number;
  demo_observations: number;
  firms_key_configured: boolean;
  sensor_label: string;
  firms: FirmsStatus;
}

export interface FirmsStatus {
  configured: boolean;
  manual_refresh_enabled?: boolean;
  source_products: string[];
  last_attempt_at: string | null;
  last_sync_at: string | null;
  last_status: "OK" | "FAILED" | null;
  last_error_code: string | null;
  last_error_message: string | null;
  last_acquisition: string | null;
  satellites: string[];
}

export interface FirmsRefreshSummary {
  status: "OK";
  synced_at: string;
  sources: { product: string; satellites: string[]; received: number; rejected: number }[];
  satellites: string[];
  observations_received: number;
  observations_stored: number;
  new_observations: number;
  updated_observations: number;
  rejected_rows: number;
  events_total: number;
  events_created: number;
  events_updated: number;
  events_unchanged: number;
  events_merged?: number;
  events_split?: number;
  events_with_facility_context?: number;
  first_acquisition: string | null;
  last_acquisition: string | null;
  demo_data_removed: { events: number; facilities: number; observations: number };
  note: string;
}

export interface FirmsRefreshFailure {
  status: "FAILED";
  code: string;
  message: string;
  showing: string;
}

// ---------------------------------------------------------------------------
// Facility context (spatial association -- never causation) + live summary
// ---------------------------------------------------------------------------

export interface ContextFacility {
  facility_id: string;
  name: string;
  facility_type: string;
  latitude: number;
  longitude: number;
  distance_km: number;
  source: string;
  country: string | null;
  context_quality?: ContextQuality;
  context_quality_reason?: string;
}

export interface FacilityContext {
  event_id: string;
  radius_km: number;
  nearest: ContextFacility | null;
  nearby: ContextFacility[];
  nearby_count: number;
  quality_counts?: Record<string, number>;
  quality_note?: string;
  statement: string;
  note: string;
  distance_note?: string;
}

export interface LiveSummary {
  firms_observations: {
    total: number;
    by_satellite: Record<string, number>;
    by_nasa_confidence: Record<string, number>;
    first_acquisition: string | null;
    last_acquisition: string | null;
  };
  events: {
    live_total: number;
    by_orbiflare_severity: Record<string, number>;
    with_facility_context: number;
    without_facility_context: number;
    by_baseline: Record<string, number>;
    multi_observation: number;
    by_facility_context_quality: Record<string, number>;
  };
  facilities_with_context: { referenced: number; twins_by_baseline: Record<string, number> };
  purity: { demo_observations: number; demo_events: number };
}
