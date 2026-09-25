#!/usr/bin/env python
"""Ingest NASA FIRMS active-fire data (VIIRS or MODIS) into the database as
raw, unclustered observations, and archive the raw+processed data to
Parquet. Does NOT form events -- run build_events.py next, or just run
rebuild_pipeline.py for the real-data path end to end.

Two sources are supported:
  --file <path>   a local FIRMS area-CSV export (offline / analyst-supplied)
  --live          the live NASA FIRMS area-CSV API, authenticated with the
                   FIRMS_MAP_KEY environment variable (never hardcoded, never
                   logged, never sent anywhere but the FIRMS request itself)

Usage:
    python scripts/ingest_firms.py --file data/raw/firms/my_export.csv --sensor VIIRS
    python scripts/ingest_firms.py --live --sensor VIIRS --bbox 68.0 6.0 98.0 37.0 --days 1
"""
from __future__ import annotations

import argparse
import json
import sys

import _pathsetup  # noqa: F401
import pandas as pd

from app.config import get_settings
from app.ingestion.firms import INDIA_BBOX, ingest_from_live_api, ingest_from_local_file
from app.model.schemas import Sensor
from app.storage import repositories as repo
from app.storage.database import SessionLocal, init_db
from app.storage.parquet import append_parquet


def main() -> None:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", help="Path to a local FIRMS area-CSV export")
    source.add_argument("--live", action="store_true", help="Fetch from the live NASA FIRMS API using FIRMS_MAP_KEY")
    parser.add_argument("--sensor", default="VIIRS", choices=["VIIRS", "MODIS"])
    parser.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"),
                         default=INDIA_BBOX, help="--live only: bounding box (default: India)")
    parser.add_argument("--days", type=int, default=1, help="--live only: day range 1-10 (default: 1)")
    args = parser.parse_args()

    if args.live:
        settings = get_settings()
        if not settings.firms_map_key:
            print("FIRMS_MAP_KEY is not configured. Set it in your environment (see .env.example) "
                  "and re-run, or use --file for a local CSV export / demo mode instead.", file=sys.stderr)
            raise SystemExit(1)
        try:
            observations, quality = ingest_from_live_api(bbox=tuple(args.bbox), day_range=args.days, sensor=Sensor(args.sensor))
        except Exception as exc:
            print(f"Live FIRMS request failed: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
    else:
        observations, quality = ingest_from_local_file(args.file, Sensor(args.sensor))

    print(f"Accepted {len(observations)} observation(s); quality report:")
    print(json.dumps(quality.model_dump(mode="json"), indent=2))

    init_db()
    db = SessionLocal()
    try:
        n = repo.bulk_insert_observations(db, observations)
        repo.record_data_quality(db, quality)
        db.commit()
        print(f"Persisted {n} new observation(s) to the database (unclustered; {len(observations) - n} were already present).")
    finally:
        db.close()

    df = pd.DataFrame([o.model_dump(mode="json") for o in observations])
    if not df.empty:
        append_parquet(df, "raw", "firms_observations")
        print("Archived to data/raw/firms_observations.parquet")


if __name__ == "__main__":
    main()
