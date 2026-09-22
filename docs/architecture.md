# Architecture

## The core pipeline

```
THERMAL OBSERVATION
        |
        v
THERMAL EVENT               (deterministic spatio-temporal clustering)
        |
        v
FACILITY CONTEXT             (nearest-facility enrichment -- context, not causation)
        |
        v
FACILITY THERMAL TWIN        (robust multidimensional behavioural baseline)
        |
        v
BEHAVIOUR DEVIATION           (6 independent dimensions vs. the twin)
        |
        v
ML EVIDENCE                   (Random Forest: 2-class, proxy-labelled)
        |
        v
EVIDENCE FUSION                (supporting / contradicting / uncertain / unavailable)
        |
        v
RISK                           (explainable, weighted composite score)
        |
        v
RISK TRAJECTORY                (risk re-computed across the event's real history)
        |
        v
EVENT REPLAY                   (deterministic chronological playback)
        |
        v
INVESTIGATION                  (full aggregate payload)
        |
        v
HUMAN DECISION                  (explicit, audited operator action)
```

Every arrow above is a real function call chain in `backend/app/intelligence/`, not a conceptual diagram divorced from the code:

- `events.py` -- Thermal Event Engine
- `facility_enrichment.py` -- nearest-facility context
- `thermal_twin.py` -- Facility Thermal Twin
- `deviation.py` -- Behaviour Deviation Engine
- `classification.py` + `app/model/` -- ML adapter
- `evidence.py` -- Evidence Fusion
- `alternative_explanations.py` -- Alternative Explanations
- `risk.py` -- Risk Engine
- `trajectory.py` -- Risk Trajectory
- `replay.py` -- Event Replay
- `investigation.py` -- Investigation aggregator
- `pipeline.py` -- orchestrates every stage above, each independently callable

## Layered system view

```
+-----------------------------------------------------------------------+
|  Frontend (Next.js)                                                    |
|  Command Center / Events / Investigation / Replay / Facilities /       |
|  Thermal Twins / GIS / Analytics / Reports / Model / Agent /           |
|  Limitations                                                           |
|  -- typed API client only; NO intelligence computed client-side --     |
+------------------------------------+-----------------------------------+
                                      | HTTP (JSON)
+------------------------------------v-----------------------------------+
|  Backend API (FastAPI)                                                 |
|  api/routes/*  ->  intelligence/*, storage/repositories.py             |
+------------------------------------+-----------------------------------+
                                      |
        +-----------------------------+------------------------------+
        |                             |                              |
+-------v--------+          +---------v---------+          +---------v--------+
| Ingestion        |         | Intelligence layer |          | Storage           |
| firms.py          |        | (the pipeline above)|         | SQLAlchemy ORM     |
| facilities.py      |       |                      |        | (SQLite / Postgres)|
| osm.py, satellite.py|      |                      |        | + Parquet          |
+--------------------+       +----------------------+        +--------------------+
```

## Why the event, not the hotspot, is the unit of analysis

A single VIIRS/MODIS detection is noisy, sparse, and by itself says almost nothing about behaviour over time. OrbiFlare's Thermal Event Engine groups raw detections using deterministic spatio-temporal chaining (configurable radius/gap) into a **Living Thermal Event** -- a computational grouping, explicitly not proof of a single physical fire. Everything downstream (twin comparison, deviation, evidence, risk, trajectory, replay) operates on the event, so the system can reason about *how a thermal signature evolves*, not just where a pixel lit up once.

## Deliberate scope decisions

- **Database default is SQLite**, not PostgreSQL+PostGIS, for zero-setup local/demo operation. The ORM models (`backend/app/storage/models.py`) use plain lat/lon columns + JSON payload columns so pointing `DATABASE_URL` at Postgres (see `docker-compose.yml`) is a config change, not a rewrite. PostGIS geometry columns are an additive migration for a future iteration, not required for the current feature set.
- **GeoPandas is an optional extra** (`pip install .[geo]`), not a hard runtime dependency -- spatial operations that matter for this build (nearest-facility, haversine distance, spatial deviation) are done with `shapely` + `scikit-learn`'s `BallTree` (haversine metric), which install reliably everywhere including Windows without a GDAL toolchain. GeoPandas remains the documented path for parsing richer real-world OSM/WRI extracts in `app/ingestion/facilities.py`.
- **No Kafka/Spark/Kubernetes/Redis/Celery** -- appropriate for the data volumes here (hundreds to low-thousands of observations); the pipeline stages in `intelligence/pipeline.py` are structured so a future scale-up can slot in a task queue or streaming layer around the same stage functions without redesigning them.
- **shadcn/ui-style primitives were hand-built** (`frontend/src/components/Panel.tsx`, badges, etc.) directly against Tailwind rather than pulling in the full Radix/shadcn toolchain, to keep the dependency surface small for a from-scratch build. They follow the same "small, composable, accessible" philosophy.
