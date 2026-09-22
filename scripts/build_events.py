#!/usr/bin/env python
"""Form thermal events from all currently unclustered observations in the
database (e.g. after running ingest_firms.py), and enrich them with nearest-
facility context. Run build_twins.py afterwards to (re)build thermal twins
for any newly-touched facilities.
"""
from __future__ import annotations

import json

import _pathsetup  # noqa: F401

from app.intelligence.events import form_events
from app.intelligence.facility_enrichment import enrich_events
from app.storage import repositories as repo
from app.storage.database import SessionLocal, init_db


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        obs_rows = repo.list_unclustered_observations(db)
        observations = [repo.observation_to_schema(r) for r in obs_rows]
        if not observations:
            print("No unclustered observations found -- nothing to do.")
            return

        events = form_events(observations)
        facilities = [repo.facility_to_schema(r) for r in repo.list_facilities(db)]
        events = enrich_events(events, facilities)

        for e in events:
            repo.upsert_event(db, e)
            repo.assign_observations_to_event(db, e.event_id, e.source_observation_ids)
            repo.get_or_create_alert(db, e.event_id)
        db.commit()

        print(json.dumps({"observations_clustered": len(observations), "events_formed": len(events)}, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
