#!/usr/bin/env python
"""Reset the database and seed the DEMO/SYNTHETIC scenario. Equivalent to
`rebuild_pipeline.py --mode demo` but named for discoverability, and drops
existing data first so re-running always gives a clean demo state.
"""
from __future__ import annotations

import json

import _pathsetup  # noqa: F401

from app.intelligence.pipeline import run_full_pipeline
from app.storage.database import Base, SessionLocal, engine, init_db


def main() -> None:
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    try:
        result = run_full_pipeline(db, mode="demo")
        print("Seeded DEMO / SYNTHETIC scenario:")
        print(json.dumps(result, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
