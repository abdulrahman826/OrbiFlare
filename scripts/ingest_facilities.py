#!/usr/bin/env python
"""Load real facility/industrial-site context (OSM extract or WRI Global
Power Plant Database CSV) into the database, for use by facility enrichment
in the real-data pipeline. Facilities enrich an event's context -- proximity
is never treated as causation; see app.intelligence.facility_enrichment.

Usage:
    python scripts/ingest_facilities.py --geojson data/raw/facilities/osm_industrial.geojson
    python scripts/ingest_facilities.py --wri-csv data/raw/facilities/global_power_plant_database.csv
"""
from __future__ import annotations

import argparse
import csv

import _pathsetup  # noqa: F401

from app.ingestion.facilities import load_facilities_from_geojson, load_facilities_from_wri_csv
from app.storage import repositories as repo
from app.storage.database import SessionLocal, init_db


def main() -> None:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--geojson", help="Path to an OSM-extract-shaped GeoJSON FeatureCollection of Point facilities")
    source.add_argument("--wri-csv", help="Path to a WRI Global Power Plant Database CSV export")
    args = parser.parse_args()

    if args.geojson:
        facilities = load_facilities_from_geojson(args.geojson)
    else:
        with open(args.wri_csv, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        facilities = load_facilities_from_wri_csv(rows)

    init_db()
    db = SessionLocal()
    try:
        for f in facilities:
            repo.upsert_facility(db, f)
        db.commit()
        print(f"Upserted {len(facilities)} facilit(y/ies).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
