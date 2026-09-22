# Intelligence Layer

All code referenced here lives in `backend/app/intelligence/`.

## Event formation (`events.py`)

Deterministic spatio-temporal single-linkage clustering: two observations join the same event if they are within `EVENT_SPATIAL_RADIUS_KM` (default 1.5km, haversine) **and** `EVENT_TEMPORAL_GAP_HOURS` (default 12h) of each other, via union-find over all pairs (sorted by time, so the temporal check short-circuits early). `event_id` is a stable hash of the sorted member observation ids, so re-running clustering on the same data always produces the same events. This is a computational grouping -- never asserted as a confirmed single physical fire.

## Facility enrichment (`facility_enrichment.py`)

A `BallTree` (haversine metric, `scikit-learn`) over facility coordinates finds the nearest facility to an event's centroid. Beyond `MAX_CONTEXT_DISTANCE_KM` (15km) no facility is attached. The event only ever gets `facility_id` + `facility_distance_km` -- rendered everywhere as "~X km away", never as attribution.

## Facility Thermal Twin (`thermal_twin.py`)

For each facility, the **chronologically last event is always excluded from its own baseline** (`pipeline.py::build_thermal_twins_stage`) -- a twin must never be built from the event it will be compared against. From the remaining historical events:

- Robust `DistributionSummary` (median, MAD, IQR, min/max) for FRP, BT, persistence (observations/event), and duration.
- `normal_recurrence_days` -- median gap between consecutive historical events' start times.
- `normal_hour_pattern` / `normal_seasonal_pattern` / `normal_day_night_pattern` -- normalized frequency histograms.
- `normal_spatial_centroid` + `normal_spatial_radius_km` -- centroid of historical event centroids, radius = 90th-percentile distance from it (robust to one outlier event).
- `baseline_confidence` = ESTABLISHED (>=4 historical events AND >=8 observations), LIMITED (>=3 observations), else INSUFFICIENT. Thresholds are config (`app/config.py`).

## Behaviour Deviation Engine (`deviation.py`)

Six independent dimensions, each producing a `DimensionDeviation`:

- **Intensity** -- robust z-score of peak FRP vs. the twin's FRP distribution.
- **Persistence** -- robust z-score of observation count vs. normal persistence.
- **Duration** -- robust z-score of event duration vs. normal duration.
- **Temporal** -- fraction of the event's observation hours falling outside the facility's "typical" hours (hours with above-uniform historical frequency).
- **Spatial** -- distance from the event centroid to the twin's normal spatial centroid, as a ratio of the normal spatial radius.
- **Recurrence** -- how much sooner the event started after the twin's `history_end` than the normal recurrence interval.

Robust z-score: `(observed - median) / (1.4826 * MAD)`, falling back to an IQR-derived scale if MAD is ~0. `is_notable` at |z| >= 1.5, `is_significant` at |z| >= 3.0 (config). If the twin is INSUFFICIENT, every dimension reports `INSUFFICIENT_BASELINE` with no numeric deviation -- never a fabricated number. `overall_deviation_score` (0-100) is a weighted count of notable/significant dimensions among those computed.

## ML classification (`classification.py` + `app/model/`)

See [docs/ml.md](ml.md).

## Evidence Fusion (`evidence.py`)

Converts deviation dimensions + ML output + facility context into an `EvidenceStack`: `supporting` / `contradicting` / `uncertain` / `unavailable` buckets of `EvidenceItem`s, each with a category, direction, strength, and explanation. Standing uncertainty items (satellite resolution, no visual confirmation) are always present. `correlation_notes` explicitly flags when two evidence items share an underlying signal (e.g. intensity deviation and the ML classifier both being driven by FRP) so they are never silently double-counted as independent confirmation.

## Alternative Explanations (`alternative_explanations.py`)

A pure function of (deviation, ML output, facility presence) that returns a `primary_hypothesis` plus `alternatives[]` and `unknowns[]` -- never a single forced verdict, never a calibrated probability the model doesn't actually support.

## Risk Engine (`risk.py`)

A weighted composite of six named, explainable components (behaviour deviation 35%, ML signal 15%, persistence 15%, duration 15%, intensity 10%, facility context 10%), each contributing a 0-100 sub-score. `severity` is a threshold lookup on the composite (config: medium=35, high=60, critical=80). Every `Risk` carries `risk_factors[]` (the components that actually mattered) and `caveats[]` (always includes "not a confirmed fire probability" and "proximity is not causation").

## Risk Trajectory (`trajectory.py`) and Event Replay (`replay.py`)

Both are built on the same `evolve_event()` stepper: re-run event-formation + deviation + classification + risk on successive **prefixes** of an event's real, sorted observations. Nothing is interpolated or fabricated between real observations. `direction` (STABLE/INCREASING/ESCALATING/DECREASING/INSUFFICIENT_DATA) is classified from the resulting risk-score sequence's net change and monotonicity. The risk engine's intensity component uses the *most recent* observation's FRP during replay (rather than the cumulative peak) specifically so a genuinely tapering-off event can register DECREASING, not just STABLE/INCREASING.

## Investigation (`investigation.py`)

Reads precomputed twin/deviation/evidence/risk from storage (written by the pipeline) and computes trajectory + alternative explanations fresh (cheap, pure functions of the event's own data) to assemble the full `Investigation` payload served by `GET /api/events/{id}/investigation`.

## Pipeline orchestration (`pipeline.py`)

`run_full_pipeline()` calls each stage in order -- `ingest -> clean -> feature_engineer -> form_events -> enrich_facilities -> build_thermal_twins -> calculate_deviations -> classify -> build_evidence -> calculate_risk -> calculate_trajectory -> persist` -- and every stage is independently callable and independently tested (see `backend/tests/intelligence/test_pipeline_integration.py`).
