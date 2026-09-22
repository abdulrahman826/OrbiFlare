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
  status: AlertState;
  classification: MLClass | null;
  ml_p_industrial: number | null;
  ml_p_natural: number | null;
  ml_anomaly_low_confidence: boolean;
  risk_score: number | null;
  severity: Severity | null;
  trajectory_direction: TrajectoryDirection | null;
  is_demo: boolean;
  source_observation_ids: string[];
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
