# OrbiFlare reference data (read-only)

These files are **historical / geographic reference data**. They are NOT FIRMS observations, NOT thermal events,
NOT demo fixtures and NOT training data. The ML pipeline (`backend/app/model`, `backend/app/intelligence`) never
imports or reads them (enforced by `backend/tests/reference/test_reference_isolation.py`).

Imported from the earlier OrbiFlare prototype, `github.com/siddiquezain/zero1` @ `6059958` (2026-09-04).
The reference repository itself was not modified.

| File | What it is | Records | Notes |
|---|---|---|---|
| `incidents/confirmed_incidents_india.csv` | Curated list of historical Indian industrial/thermal-context incidents (2019-2023). Fields: `incident_id,name,date,lat,lon,state,facility_type,description,source` | 30 | Per-record `source` is a news/agency label (e.g. "Wikipedia/News", "NTPC"). Coordinates are approximate (site/city level; two records share identical coordinates). Not every row is a fire: some are persistent thermal-source references, agricultural stubble-burning reference points, or a memorial site. OrbiFlare classifies each row (`record_kind`) instead of calling all of them "fires". |
| `geo/india_admin.geojson` | 36 dissolved state polygons + 760 district polygons, simplified (~1.3 km). Source per file: `udit-001/india-maps-data`. | 796 | Simplified geometry for orientation and point-in-polygon lookup only; not a survey-grade or official boundary product. |

**FIRMS matching.** The prototype's own matching run (`match_summary.json`, spatial buffer 1 km, window 1 day) found 0 of 30
incidents matched to a FIRMS detection (the incident dates 2019-2023 predate the near-real-time window that was ingested).
OrbiFlare therefore reports *"no FIRMS match available"* for these records and never fabricates one.

**Deliberately not imported:** `stage7_incident_scores.parquet` (scores from an older model on records that have no thermal
features), `stage6_india_scores.parquet`, `facilities.parquet` (72k OSM/GPPD rows; a separate facility-ingestion decision),
and all Streamlit code.
