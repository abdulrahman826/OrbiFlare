#!/usr/bin/env python
"""Run the full OrbiFlare pipeline end to end: ingest -> clean -> feature
engineer -> form events -> enrich facilities -> build thermal twins ->
calculate deviations -> classify -> build evidence -> calculate risk ->
calculate trajectory -> persist.

Usage:
    python scripts/rebuild_pipeline.py --mode demo
"""
from __future__ import annotations

import argparse
import json

import _pathsetup  # noqa: F401

from app.intelligence.pipeline import run_full_pipeline
from app.storage.database import SessionLocal, init_db


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="demo", choices=["demo"], help="Data source mode (real mode: use ingest_firms.py first)")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        result = run_full_pipeline(db, mode=args.mode)
        print(json.dumps(result, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
