# API Reference

Base URL: `http://localhost:8000/api`. Interactive docs (Swagger UI) at `http://localhost:8000/docs` whenever the backend is running. All responses are JSON; Pydantic schemas in `backend/app/model/schemas.py` and `backend/app/agent/schemas.py` are the source of truth.

## Health

- `GET /health` -- `{status, mode, database}`

## Observations

- `GET /observations` -- all raw thermal observations

## Events

- `GET /events` -- filters: `severity`, `status`, `facility_id`, `trajectory`, `classification`
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

- `POST /agent/query` -- body `{message}` -> `{text, tool_calls[], result_cards[], ui_action}`. Deterministic, read-only: no LLM is ever called. See [docs/intelligence.md](intelligence.md) and `backend/app/agent/`.

## Pipeline (dev/admin convenience)

- `POST /pipeline/rebuild` -- body `{mode: "demo"}`; re-runs the full pipeline (equivalent to `scripts/rebuild_pipeline.py`)

## Error format

Unhandled exceptions return `{"error": "internal_error", "detail": "..."}` with HTTP 500 (see `app/main.py`'s exception handler). Domain 404s (`event/facility not found`) and 400/403/409 (invalid/forbidden alert transitions) use FastAPI's standard `{"detail": "..."}` shape.
