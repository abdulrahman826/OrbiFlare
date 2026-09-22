#!/usr/bin/env python
"""(Re)build thermal twins, deviations, ML classification, evidence, risk
and trajectory for every event currently in the database. Run after
build_events.py in the real-data workflow.
"""
from __future__ import annotations

import json

import _pathsetup  # noqa: F401

from app.intelligence import classification
from app.intelligence import evidence as evidence_mod
from app.intelligence import risk as risk_mod
from app.intelligence.deviation import compute_deviation
from app.intelligence.pipeline import build_thermal_twins_stage
from app.intelligence.trajectory import compute_trajectory
from app.storage import repositories as repo
from app.storage.database import SessionLocal, init_db


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        event_rows = repo.list_events(db)
        events = [repo.event_to_schema(r) for r in event_rows]
        if not events:
            print("No events found -- run build_events.py first.")
            return

        all_obs = [repo.observation_to_schema(r) for r in repo.list_all_observations(db)]
        twins, _current, obs_by_event = build_thermal_twins_stage(events, all_obs)
        for twin in twins.values():
            repo.upsert_thermal_twin(db, twin)

        facilities_by_id = {f.facility_id: repo.facility_to_schema(f) for f in repo.list_facilities(db)}

        for e in events:
            twin = twins.get(e.facility_id) if e.facility_id else None
            obs = obs_by_event.get(e.event_id, [])
            deviation = compute_deviation(e, twin, obs)
            repo.upsert_deviation(db, deviation)

            pred = classification.classify_event(e)
            e.classification, e.ml_p_industrial = pred.predicted_class, pred.p_persistent_industrial
            e.ml_p_natural, e.ml_anomaly_low_confidence = pred.p_natural_candidate, pred.low_confidence

            facility = facilities_by_id.get(e.facility_id) if e.facility_id else None
            stack = evidence_mod.build_evidence_stack(e, deviation, pred, facility)
            repo.upsert_evidence(db, stack)

            r = risk_mod.compute_risk(e, deviation, pred, facility_present=e.facility_id is not None)
            e.risk_score, e.severity = r.risk_score, r.severity
            repo.upsert_risk(db, r)

            traj, _ = compute_trajectory(obs, twin, e.facility_id, e.facility_distance_km, e.event_id)
            e.trajectory_direction = traj.direction
            repo.replace_trajectory_points(db, e.event_id, traj.points)

            repo.upsert_event(db, e)

        db.commit()
        print(json.dumps({"thermal_twins_built": len(twins), "events_updated": len(events)}, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
