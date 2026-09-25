# API Reference

Base URL: `http://localhost:8000/api`. Interactive docs (Swagger UI) at `http://localhost:8000/docs` whenever the backend is running. All responses are JSON; Pydantic schemas in `backend/app/model/schemas.py` and `backend/app/agent/schemas.py` are the source of truth.

## Health

- `GET /health` -- `{status, mode, database}`

## Observations

- `GET /observations` -- all raw thermal observations

## Events

- `GET /events` -- filters: `severity`, `status`, `facility_id`, `trajectory`, `classification`. Each event is enriched (bulk-joined, not per-event) with `overall_deviation_score`, `facility_type`, and `baseline_confidence` so list/filter/sort views never need a second round-trip per event.
- `GET /events/{event_id}`
- `GET /events/{event_id}/timeline` -- observations for the event
- `GET /events/{event_id}/deviation`
- `GET /events/{event_id}/evidence`
- `GET /events/{event_id}/risk`
- `GET /events/{event_id}/trajectory`
- `GET /events/{event_id}/replay`
- `GET /events/{event_id}/investigation` -- the full aggregate payload
- `POST /events/{event_id}/transition` -- body `{to_state, actor, note?}`; validates the alert-lifecycle transition graph and forbids `actor in {agent, ai, system}` from ever setting `EXTINGUISHED`

## Facilities

- `GET /facilities` -- filter: `facility_type`
- `GET /facilities/{facility_id}`
- `GET /facilities/{facility_id}/thermal-twin`
- `GET /facilities/{facility_id}/events`

## Thermal twins

- `GET /thermal-twins` -- all computed twins
- `GET /thermal-twins/{facility_id}`

## Analytics

- `GET /analytics/overview` -- top-level KPIs
- `GET /analytics/events` -- by-state / by-facility-type / by-classification breakdowns, deviation score distribution, peak FRP values
- `GET /analytics/risk` -- risk scores, trajectory direction breakdown, current model evaluation metrics
- `GET /analytics/data-quality` -- every ingestion batch's `DataQualityRecord` (rows received/accepted/flagged/rejected + issue counts) and a coordinate-range validation breakdown of every stored observation against the configured ingestion bounding box (in-region / out-of-region counts, lat/lon range, sample out-of-region points). This is a bounding-box check, not administrative-boundary geometry, and is reported as exactly that -- points are never moved, clipped, or dropped because of it.

## Map

- `GET /map/events` -- GeoJSON FeatureCollection
- `GET /map/facilities` -- GeoJSON FeatureCollection

## Alerts

- `GET /alerts` -- all non-extinguished events with their current state
- `GET /alerts/{event_id}/history` -- full audited transition history

## Reports

- `POST /reports/event/{event_id}` -- generates the full incident report (JSON)
- `GET /reports/events.csv` -- all events as CSV (file download)
- `GET /reports/events.geojson` -- all events as GeoJSON

## Agent

- `POST /agent/query` -- body `{message}` -> `{text, tool_calls[], result_cards[], ui_action}`. Deterministic, read-only: no LLM is ever called. The sole route under `/agent` -- verified by a test that no other agent route exists.

Controlled read-only tool registry (`app/agent/tools.py::TOOL_REGISTRY`): `list_events`, `get_event`, `get_investigation`, `get_facility`, `get_thermal_twin`, `get_deviation`, `get_evidence`, `get_risk`, `get_trajectory`, `compare_events`, `compare_facilities`, `compare_event_to_baseline`, `list_high_risk_events`, `list_escalating_events`, `list_persistent_events`, `facility_event_frequency`, `get_event_statistics`, `get_facility_statistics`, `get_risk_statistics`, `generate_report`. No tool mutates state, runs SQL, executes shell, or calls an external URL -- see [docs/intelligence.md](intelligence.md) and `backend/app/agent/`.

## Pipeline (dev/admin convenience)

- `POST /pipeline/rebuild` -- body `{mode: "demo"}`; re-runs the full pipeline (equivalent to `scripts/rebuild_pipeline.py`)

## Error format

Unhandled exceptions return `{"error": "internal_error", "detail": "..."}` with HTTP 500 (see `app/main.py`'s exception handler). Domain 404s (`event/facility not found`) and 400/403/409 (invalid/forbidden alert transitions) use FastAPI's standard `{"detail": "..."}` shape.

## Reference data (historical + geographic) -- `/api/reference/*`

Read-only, file-backed (`data/reference/`), never stored in the operational DB, never used by the ML pipeline
(enforced by `backend/tests/reference/test_reference_isolation.py`). See `data/reference/README.md` for provenance.

| Endpoint | Purpose |
|---|---|
| `GET /reference/incidents?state=&kind=` | 30 historical reference incidents (`record_kind`, per-record provenance, caveats) |
| `GET /reference/incidents/summary` | counts by kind/state + provenance note (0/30 FIRMS-matched in the source prototype) |
| `GET /reference/incidents/near?lat=&lon=&radius_km=` | incidents near a point, sorted by distance |
| `GET /reference/incidents/{id}` , `/{id}/context` | record; context = admin region, facilities/events within radius, honest FIRMS-match check, known/unknown |
| `GET /reference/admin-regions?level=state\|district&state=` | real boundary GeoJSON (36 states / 760 districts) + provenance |
| `GET /reference/admin-regions/summary` , `/resolve?lat=&lon=` | boundary summary; point-in-polygon lookup |
| `POST /reports/historical-incident/{id}` | report for a historical record (labelled NOT A LIVE FIRMS DETECTION) |

`GET /health` now returns a **verified** `data_mode` (`LIVE_FIRMS` / `DEMO` / `MIXED` / `EMPTY`) derived from stored observations,
plus `live_firms_observations`, `demo_observations`, `firms_key_configured` (boolean only -- the key is never exposed).
`GET /analytics/events` gains `by_admin_state` (point-in-polygon of event centroids) and `by_region` (facility metadata).
The event report gains `historical_reference_context`. Agent tools added: `list_historical_incidents`, `get_historical_incident`,
`find_incidents_near_event`, `find_incidents_near_facility` (all read-only).

## NASA FIRMS refresh -- `/api/firms/*`

`POST /firms/refresh` fetches the India bounding box (`FIRMS_BBOX`, default `68,6,98,37`) from one VIIRS NRT product
(`FIRMS_SOURCE`, default `VIIRS_NOAA21_NRT`, `FIRMS_DAY_RANGE` default 2) using the server-side `FIRMS_MAP_KEY`, upserts
observations (stable id = source|sensor|lat|lon|acquisition time, so repeats never duplicate), and re-runs the existing event
stages over the stored real observations only. Demo data is never modified and demo facilities are not attached to real events.
Success returns real counts (`observations_received`, `new_observations`, `updated_observations`, `last_acquisition`); failure returns
`{status:"FAILED", code, message, showing:"last available data"}` (`NOT_CONFIGURED`, `INVALID_KEY`, `TIMEOUT`, `RATE_LIMITED`,
`HTTP_ERROR`, `MALFORMED`, `BUSY`) and leaves stored data unchanged. `GET /firms/status` and `/health` expose `last_sync_at`
(when we asked NASA) separately from `last_acquisition` (when the satellite observed), and a `sensor_label` derived from stored data.
`GET /observations?source=FIRMS` returns only real observations. The key is never returned by any endpoint.

### Live-first behaviour (supersedes the demo-first notes above)

* `POST /firms/refresh` now fetches every product in `FIRMS_SOURCES` (default `VIIRS_NOAA21_NRT,VIIRS_NOAA20_NRT`) for the India bbox and returns
  `observations_received`, `observations_stored`, `new_observations`, `updated_observations`, `events_created/updated/unchanged/total`,
  `first_acquisition`, `last_acquisition`, per-source counts and `demo_data_removed`. It is all-or-nothing: a failing product stores nothing.
* Every stored observation keeps the NASA fields (`satellite`, `instrument`, `scan`, `track`, `source_product`, confidence, BT I-4/I-5, FRP,
  acquisition time). Observations and events expose `is_live_firms` (true only for real FIRMS data).
* After the first successful live sync the synthetic demo dataset is removed from the primary database; `POST /pipeline/rebuild {"mode":"demo"}` is
  refused (409) while live data exists. With `FIRMS_AUTO_SYNC=true` the server performs one best-effort live sync at start; a failure is logged and
  never falls back to synthetic data. The MAP_KEY is never logged (httpx request logging is silenced) or returned by any endpoint.

### Facility context, baselines and stable event identity (live data)

* `data/facilities/osm_gppd_facilities.parquet` (OSM + GPPD, India bbox, non-thermal types excluded) is loaded into an in-memory BallTree
  (`app/context/facilities.py`). Events get their nearest facility within `FACILITY_CONTEXT_RADIUS_KM` (default 3); only referenced facilities are
  stored in the `facilities` table. `GET /context/events/{id}` returns nearest + nearby facilities with source/distance and association-only wording;
  `GET /context/facilities/near`; `GET /context/live-summary` (NASA confidence and OrbiFlare severity are separate distributions).
* Thermal Twin baselines are built only from stored real FIRMS events of a facility. `LIMITED` now needs >=2 historical events (>=3 observations);
  `ESTABLISHED` needs >=4 events and >=8 observations. Below that the twin is `INSUFFICIENT`, deviation is not computed and no anomaly is implied.
* Event identity is stable: a re-clustered event keeps the id of the existing event it overlaps most (older wins ties). Merges/splits are written to the
  audit trail (`alert_history`, actor `system`) and human-decided states are preserved.
* ML predictions are batched and memoised (identical results, ~150x faster reprocessing).

## Evidence policy (scientific hardening)

- `GET /api/events/{id}/risk` now also returns `baseline_status`, `deviation_contribution`, `deviation_contribution_cap`, `facility_context_quality`, `contributing`, `limiting`, `missing_evidence`, `escalation_evidence`, `severity_reason`.
- Baseline weighting: ESTABLISHED = full deviation contribution (max 35 pts); LIMITED = discounted by `risk_limited_baseline_factor` (0.4, max 14 pts); INSUFFICIENT / no facility = 0. Thresholds (35/60/80) are unchanged.
- `GET /api/context/events/{id}` returns facility `context_quality` (HIGH/MEDIUM/LOW, from dataset name/type only). LOW-quality (generic land-use) context contributes 0 to risk and is not shown to the ML model as a nearby facility.
- ML evidence uses proxy labels (nearest facility <= 5 km and persistence >= 2) and partially overlaps with facility/persistence factors; it is not independent confirmation.
