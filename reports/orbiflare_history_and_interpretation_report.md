# Historical FIRMS baseline + source interpretation — implementation report

All numbers were measured on the local live database (2,499 FIRMS observations, 1,449 events, refreshed 2026-09-26) and the historical cache built the same day.

## B. Historical ingestion
`backend/app/ingestion/firms_history.py`, run by `python scripts/ingest_firms_history.py` (admin only; never by the dashboard or the live refresh).
* India bbox only (68,6,98,37); 5-day area chunks (the API maximum), **73 requests for 180 days x 2 satellites**, never one per facility.
* Product per date from NASA's own `data_availability` table: **NOAA-20 Standard Processing** (2018-04-01 → 2026-06-30) for older dates, **NOAA-20 NRT** (from 2026-07-01), **NOAA-21 NRT** (from 2024-01-17). NOAA-21 has no Standard Processing product yet; Suomi-NPP is not used.
* Window = last 180 days minus the days owned by the live pipeline (`firms_day_range + 1`): 2026-03-25 → 2026-09-20. `FIRMS_HISTORY_DAYS` (90 / 180 / 365) is a setting.
* Resumable and idempotent: a cached chunk is never re-downloaded (second run: 0 downloaded, 73 cached, identical output). Chunk failures are recorded, the run continues, coverage is reported per satellite. No key = `NOT_CONFIGURED`, never an exception. The key is only ever in the request URL; errors are mapped to short key-free messages.

## C. Storage
`data/firms/historical/` — `raw/<product>/<start>_<n>d.parquet` (26 MB, re-creatable, git-ignored), `fetch_manifest.json`, and the small precomputed files the app reads: `history_events.parquet` (2 MB), `history_observations.parquet` (4 MB), `history_manifest.json`. Rows keep every FIRMS field returned (lat/lon, date/time, satellite, instrument, scan, track, confidence, I-4/I-5 brightness, FRP, day/night, product, `type` where provided) and `data_origin = FIRMS_HISTORICAL`. De-duplication key: satellite + lat + lon + date + time (SP wins over NRT). Historical rows are never written to the live observations/events tables.

## D/E. Baseline calculation and Thermal Twin
* Historical rows → in-memory observations → the **existing** clustering (`form_events`, unchanged) → the **existing** facility index and radius → per-facility historical events (`HIST-…` ids; observation ids `HIST|…`).
* Only events near an eligible facility are kept (prefilter with the same spatial index). Pipeline: `build_thermal_twins_stage` now prepends the facility's historical events to its earlier live events and calls the **existing** `build_thermal_twin`; states and thresholds are unchanged (ESTABLISHED >= 4 events and >= 8 observations, LIMITED >= 2 and >= 3, else INSUFFICIENT).
* Leakage guard: historical events that end at/after the first live observation are excluded, and a live event is never in its own history (tested). Partial history coverage (< 50 % of the window) caps ESTABLISHED to LIMITED.
* Missing/corrupt history files ⇒ exactly the previous behaviour; status `UNAVAILABLE` (`GET /api/history/status`); live ingestion is untouched.
* UI: Thermal Twin detail shows History / Span / Typical FRP / Persistence (dashes for insufficient, never zeros); Thermal Twins page shows a coverage line or "Historical baseline: UNAVAILABLE".

## F. Source interpretation (`backend/app/intelligence/source_interpretation.py`)
A separate, descriptive layer — no risk points, no ML change, no state change. Five candidate classes (Industrial-source, Agricultural/vegetation-fire, Persistent thermal-source, Natural/other, Uncertain) with strength HIGH/MODERATE/LOW/UNCERTAIN and an evidence list (supporting, against/limiting, unavailable, alternatives). Rules: an industrial candidate needs >= 2 distinct signals; an agricultural candidate needs >= 2 positive signals and no usable facility; **absence of a facility is never evidence**; natural/other needs positive non-industrial context; conflicts ⇒ Uncertain; ML counts at half weight (facility-informed). Signals used: facility context (quality/type/distance), persistence, recurrence at the facility (history), crop-burning season, transience, FIRMS `type`, ML class. FIRMS `type` (0 vegetation, 1 volcano, 2 other static land source, 3 offshore) exists only in Standard Processing rows, not NRT, so it is used only through the historical record at a facility (>= 5 typed detections). No land-use dataset is configured (listed as unavailable).
API: `source_interpretation` on each event (label + strength), `GET /api/events/{id}/interpretation` (full evidence), and on the investigation.

## G. Map
Marker **fill = source interpretation**, **ring + letter = operational priority** (two separate dimensions; thin ring for LOW so the fill stays readable). Two-section legend, compact hover tooltip (interpretation / priority / FRP / persistence), popup with interpretation, strength, priority, thermal evidence, spatial context, behaviour, ML evidence, both disclaimers and an "Open investigation" link (marker click now opens the popup instead of navigating). Investigation shows a Source interpretation panel at the top; priority-feed cards show it too.

## H. Intelligence Console
New read-only intents on the existing deterministic parser/tool registry: "show industrial-source candidates", "show agricultural thermal candidates", "show uncertain thermal events", "how many persistent thermal-source candidates are active?", "why is EVT-… classified as an industrial-source candidate?", "classify EVT-…", "is EVT-… an industrial fire?" (answers "… industrial-source candidate … not a confirmed fire"). Mutation-like requests change nothing (tested).

## Metrics (measured)
| | |
|---|---|
| Historical observations | 938,775 (NOAA-20 SP/NRT + NOAA-21 NRT), 465,300 with a FIRMS `type` |
| Historical date coverage | 180 / 180 days (2026-03-25 → 2026-09-20), both satellites |
| Historical events (all / near a facility) | 67,205 / 38,702 (9,383 facilities) |
| Facilities with history by baseline | ESTABLISHED 1,672, LIMITED 2,615, INSUFFICIENT 5,096 |
| Live events by baseline | ESTABLISHED 410, LIMITED 40, INSUFFICIENT 80, no facility context 919 |
| Facility twins (facilities with live events) | ESTABLISHED 221, LIMITED 38, INSUFFICIENT 77 |
| Source interpretation (1,449 live events) | Industrial-source 44, Persistent thermal-source 52, Uncertain 1,353, Agricultural 0, Natural/other 0 |
| Live severity | LOW 1,430, MEDIUM 17, HIGH 2 (was 1,007 / 5 / 0 with no history) |

The two HIGH events arise naturally: an ESTABLISHED baseline now lets behavioural deviation count fully (max +17.5 of a possible 35 points). Thresholds, weights and the risk engine were not touched.

## Tests / verification
* Backend **319 passed** (was 276; +43: history 20, risk/baseline regression 7, source interpretation 16). Frontend **70 passed** (was 54; +16). `tsc` clean; production build passes.
* Validation script (unmodified): risk/trajectory mismatch **0 / 1,449**, severity-vs-threshold 100 %, limited cap 40 events / max 5.84 of 14 / 0 violations, insufficient non-zero deviation 0, FIRMS ingestion fidelity 1,437 / 1,437, RF macro-F1 0.810 (unchanged), refresh idempotent (20.7 s).
* Facility association recomputation: 1,448 / 1,449. The one mismatch (EVT-A7D6EF65A0) is a tie: two facility records at identical coordinates (an industrial land-use record and a bus depot) are equidistant, and the BallTree and the brute-force check pick different ones. The pre-existing facility logic was not changed; a deterministic tie-break would be a separate decision.
* Browser (local): Command Center map/legend/markers, popup (opened on an industrial-source marker: Qadirpur Gas Plant, high evidence), priority feed, Intelligence Console queries, Investigation (industrial and uncertain events), Thermal Twins list and detail. Only console message: the extension-injected `fdprocessedid` hydration warning seen before; no duplicate-key warnings, no API errors, no repeated requests, no history download on page load.

## Unchanged (confirmed by diff)
`app/ingestion/firms_refresh.py`, `app/intelligence/risk.py`, `app/intelligence/events.py` (clustering), `app/model/train.py`/`predict.py` (ML), `scripts/validate_accuracy.py`, risk thresholds, database schema. Additive changes only: config settings, new modules, an optional `source_interpretation` field on the event/investigation read models, and the historical stage inside `build_thermal_twins_stage`.

## Remaining limitations
* 93 % of live events are "Uncertain": most are single, short detections with no facility context, and absence of context is deliberately not treated as evidence. No agricultural or natural/other candidates appear now (September is outside the crop-burning months and no land-use data exists).
* The FIRMS `type` field covers only the Standard-Processing part of history (NOAA-20, through 2026-06-30).
* History depth is 180 days of VIIRS detections; a facility's "normal" is only as good as that window (seasonality is not established from < 1 year).
* Historical events are built only near eligible facilities; the OSM facility set is incomplete and 80 % of its records are generic land-use.
* Render deployment: the small precomputed history files (6 MB) must be committed for the hosted API to have baselines; the raw cache is not committed.
