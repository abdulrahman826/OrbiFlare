# OrbiFlare -- Explainable Thermal Behaviour Intelligence

**SIH26162** -- AI-Based Detection and Classification of Industrial Fires and Persistent Thermal Sources Using NASA FIRMS, OSM & Satellite Data.

> "OrbiFlare doesn't just detect thermal anomalies -- it learns what normal thermal behaviour looks like and explains when an event meaningfully deviates from it."

Most systems treat a satellite hotspot as the unit of analysis. OrbiFlare treats the evolving **thermal event** as the unit of analysis: it learns a **Facility Thermal Twin** (what "normal" looks like at a given industrial site), measures **behavioural deviation** across six independent dimensions, fuses that with ML evidence into an **Evidence Stack**, computes an explainable **Risk** score and **Risk Trajectory**, and hands the whole thing to a human analyst through an **Investigation** workflow -- never an automated verdict.

## Architecture

```
THERMAL OBSERVATION -> THERMAL EVENT -> FACILITY CONTEXT -> FACILITY THERMAL TWIN
   -> BEHAVIOUR DEVIATION -> ML EVIDENCE -> EVIDENCE FUSION -> RISK -> RISK TRAJECTORY
   -> EVENT REPLAY -> INVESTIGATION -> HUMAN DECISION
```

See [docs/architecture.md](docs/architecture.md) for the full diagram and rationale, and [docs/intelligence.md](docs/intelligence.md) for how each stage is actually computed.

## Quickstart (no external services required)

The app runs fully offline with zero API keys, using a local SQLite database and a clearly labelled **DEMO / SYNTHETIC** scenario: a synthetic refinery with an established baseline and an escalating current event, a stable steel plant matching its own baseline, a chemical plant with INSUFFICIENT history, a mining site engineered to produce a genuinely low-confidence/ambiguous ML+evidence read (so the system can demonstrate "requires analyst validation" rather than forcing a verdict), and an unassociated agricultural-fire-shaped event with no nearby facility. Nothing about the demo data is presented as a real NASA observation.

### Backend

```bash
cd backend
python -m venv .venv
./.venv/Scripts/pip install -r requirements.txt   # (.venv/bin/pip on macOS/Linux)
./.venv/Scripts/uvicorn app.main:app --reload --port 8000
```

On first startup with an empty database, the backend automatically seeds the DEMO/SYNTHETIC scenario and runs the full intelligence pipeline. API docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Open http://localhost:3000 -- it redirects to the Command Center.

### Docker (Postgres + PostGIS, production-parity)

```bash
docker compose up --build
```

Backend on :8000, frontend on :3000, Postgres+PostGIS on :5432. The ORM (SQLAlchemy) works against either SQLite (default, zero-setup) or Postgres via `DATABASE_URL` -- no code changes required. See [.env.example](.env.example).

## Real FIRMS data

The app works without any API key (demo mode). To ingest real NASA FIRMS data:

1. Get a free MAP_KEY at https://firms.modaps.eosdis.nasa.gov/api/map_key/ and set `FIRMS_MAP_KEY` in `.env` -- or skip this and download an area CSV export manually into `data/raw/firms/` instead.
2. Live API: `python scripts/ingest_firms.py --live --sensor VIIRS --bbox 68.0 6.0 98.0 37.0 --days 1`
   Local file: `python scripts/ingest_firms.py --file data/raw/firms/export.csv --sensor VIIRS`
3. (Optional) `python scripts/ingest_facilities.py --geojson data/raw/facilities/osm_industrial.geojson` to load real facility context for enrichment.
4. `python scripts/build_events.py`
5. `python scripts/build_twins.py`

Every observation and event carries explicit provenance -- `source: FIRMS` + `is_demo: false` for live NASA data, vs. `source: DEMO` + `is_demo: true` for the seeded scenario -- so the UI can never mix them up; see [docs/limitations.md](docs/limitations.md). A FIRMS thermal anomaly is never described as a "confirmed fire": the pipeline and UI consistently say "thermal observation" / "thermal event" / "candidate event".

Or run the whole pipeline for demo mode with `python scripts/rebuild_pipeline.py --mode demo`. See [scripts/](scripts/) and [docs/intelligence.md](docs/intelligence.md).

## Testing

```bash
cd backend && ./.venv/Scripts/pytest -q     # 90+ tests across ingestion, intelligence, ML, alerts, agent, API
```

## Project structure

```
backend/    FastAPI app: ingestion, preprocessing, intelligence (the core), ML, storage, alerts, agent, reporting
frontend/   Next.js 15 + TypeScript + Tailwind + MapLibre + Recharts
data/       Raw/processed/feature/event Parquet storage (analytical layer)
scripts/    Standalone CLI pipeline scripts (seed_demo, ingest_firms, build_events, build_twins, rebuild_pipeline)
docs/       Architecture, data model, intelligence design, ML design, API reference, limitations, demo script
```

## Navigation

Command Center &middot; Events &middot; Investigation &middot; Event Replay &middot; Facilities &middot; Thermal Twins &middot; GIS Explorer &middot; Analytics &middot; Reports &middot; Model &middot; Agent &middot; Limitations

## What makes this different

1. **Living Thermal Events**, not raw hotspot pixels -- deterministic spatio-temporal clustering (see [docs/intelligence.md](docs/intelligence.md)).
2. **Facility Thermal Twin** -- a robust, multidimensional behavioural baseline per facility (FRP, BT, persistence, duration, recurrence, timing, spatial footprint), explicitly labelled ESTABLISHED / LIMITED / INSUFFICIENT. Never fabricated.
3. **Behaviour Deviation Engine** -- six independent deviation dimensions, computed with robust statistics (median/MAD), never collapsed directly into a "fire probability".
4. **Evidence Fusion** -- a structured Evidence Stack (supporting / contradicting / uncertain / unavailable) with explicit correlation notes so correlated signals aren't double-counted.
5. **Alternative Explanations** -- a primary hypothesis plus genuine alternatives and unknowns, not a single forced verdict.
6. **Risk Trajectory** -- observed risk evolution over an event's real lifetime (early risk warning language only -- never a future-fire prediction).
7. **Event Replay** -- deterministic chronological replay of an event's actual recorded observations.
8. **Human-in-the-loop Investigation** -- every alert-state transition is an explicit, audited operator action. The system can never autonomously mark an event Extinguished.

## Scientific honesty

OrbiFlare never claims a confirmed fire, causation from facility proximity, or a future outcome. See [docs/limitations.md](docs/limitations.md) and the in-app [Limitations page](frontend/src/app/limitations/page.tsx) for a full accounting of what this build can and cannot claim -- including that the Random Forest classifier is trained on **proxy labels**, not verified ground truth.

## Environment variables

See [.env.example](.env.example). Every value has a safe local default; `FIRMS_MAP_KEY` is optional (the app runs fully without it, using demo fixtures). The Fire Intelligence Agent is a deterministic, read-only agent -- it never calls an LLM and accepts no API key for its core execution path.
