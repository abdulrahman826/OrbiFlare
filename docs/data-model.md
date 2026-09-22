# Data Model

Canonical Pydantic schemas live in `backend/app/model/schemas.py`; SQLAlchemy ORM mirrors in `backend/app/storage/models.py`; the frontend's hand-maintained TypeScript mirror is `frontend/src/types/domain.ts`.

## Thermal Observation

Raw, per-detection satellite data. `observation_id`, `timestamp`, `latitude`/`longitude`, `sensor` (VIIRS/MODIS/SYNTHETIC), `brightness_temperature` (+ the 11-micron channel), `frp`, `confidence`, `day_night`, `source` (FIRMS/DEMO/MANUAL), `source_id`, `ingestion_time`, `quality_flags[]`.

## Thermal Event

A computational grouping of observations (see `intelligence/events.py`). `event_id` (deterministic hash of its member observation ids), `first_detected`/`last_detected`/`duration_hours`, `observation_count`, `peak_frp`/`mean_frp`/`peak_bt`/`mean_bt`, `centroid_lat`/`centroid_lon`/`footprint_radius_km`, `facility_id`/`facility_distance_km` (context, not causation), `status` (alert lifecycle state), `classification` + ML probabilities, `risk_score`/`severity`/`trajectory_direction`, `is_demo`, `source_observation_ids[]`.

## Facility

`facility_id`, `name`, `facility_type`, `industry`, `latitude`/`longitude`, `source` (OSM/WRI_GPPD/DEMO/MANUAL), `country`/`state`/`region`, `is_demo`.

## Thermal Twin

A facility's behavioural baseline, built ONLY from history that predates the event under investigation. `baseline_confidence` (ESTABLISHED/LIMITED/INSUFFICIENT), `history_start`/`history_end`, `historical_event_count`/`historical_observation_count`, robust `DistributionSummary` (n, median, MAD, q25/q75, min/max) for FRP/BT/persistence/duration, `normal_recurrence_days`, `normal_day_night_pattern`/`normal_hour_pattern`/`normal_seasonal_pattern` (frequency maps), `normal_spatial_centroid_lat/lon` + `normal_spatial_radius_km`.

## Deviation

Per-event comparison against its facility's twin, across six `DimensionDeviation` objects (intensity, persistence, duration, temporal, spatial, recurrence), each with `status` (COMPUTED/INSUFFICIENT_BASELINE), `observed_value`, `expected_median`/`expected_range`, `robust_z`, `is_notable`/`is_significant`, and a plain-English `explanation`. Plus `overall_deviation_score` (0-100) and `explanations[]`.

## Evidence

`EvidenceStack`: four buckets of `EvidenceItem` (supporting/contradicting/uncertain/unavailable), each with `category` (THERMAL/TEMPORAL/BEHAVIOURAL/FACILITY/GIS/ML), `observed_value`/`expected_value`, `source`, `direction`, `strength`, `explanation`, and `related_to[]` for flagging correlated evidence. Plus `correlation_notes[]`.

## Risk

`risk_score` (0-100), `severity` (LOW/MEDIUM/HIGH/CRITICAL), `risk_factors[]` (named, weighted, explained contributions), `explanation`, `caveats[]`.

## Risk Trajectory

`points[]` (timestamp, risk_score, deviation_score, severity) computed by literally re-running the pipeline on successive prefixes of an event's real observations, `direction` (STABLE/INCREASING/ESCALATING/DECREASING/INSUFFICIENT_DATA), `explanation`.

## Alert lifecycle

`AlertState`: DETECTED -> VALIDATING -> ALERTED -> ESCALATED -> MONITORING -> EXTINGUISHED, with a strict transition graph (`app/model/schemas.py::ALERT_TRANSITIONS`) and a full audit trail (`AlertHistoryRecord`). The agent is programmatically forbidden from ever setting EXTINGUISHED (`app/alerts/lifecycle.py`).

## Database tables (SQLAlchemy / `backend/app/storage/models.py`)

`facilities`, `observations`, `events`, `thermal_twins`, `deviations`, `evidence`, `risk_assessments`, `risk_trajectory_points`, `alerts`, `alert_history`, `confirmed_incidents`, `data_quality_records`. Structured/filterable fields (timestamp, location, facility_id, event_id, severity, status) are real indexed columns; rich nested payloads (evidence items, distribution summaries, trajectory points as a unit) are stored as JSON columns keyed by their Pydantic schema and re-hydrated on read.

## Provenance

Every observation carries `source` + `source_id` + `ingestion_time`. Every derived object traces back to its inputs: event -> observations; thermal twin -> historical events (explicitly excluding the event under investigation); deviation -> event + twin; evidence -> deviation + ML + facility; risk -> evidence; trajectory -> risk history. The full chain is visible in the Investigation payload (`GET /api/events/{id}/investigation`) and the exported incident report.
