"""Precomputed-friendly analytics endpoints. At this data scale we compute
on read; if/when data volume grows, these aggregations are the natural place
to swap in cached materialized views without changing the response shape.
"""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.model.evaluate import get_latest_metrics
from app.storage import repositories as repo
from app.storage.database import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    events = [repo.event_to_schema(r) for r in repo.list_events(db)]
    facilities = repo.list_facilities(db)
    severities = Counter(e.severity.value for e in events if e.severity)
    twins = [repo.get_thermal_twin(db, f.facility_id) for f in facilities]
    established = sum(1 for t in twins if t and t.baseline_confidence.value == "ESTABLISHED")
    return {
        "total_events": len(events),
        "total_facilities": len(facilities),
        "by_severity": dict(severities),
        "escalating_events": sum(1 for e in events if e.trajectory_direction and e.trajectory_direction.value == "ESCALATING"),
        "high_risk_events": sum(1 for e in events if e.severity and e.severity.value in ("HIGH", "CRITICAL")),
        "facilities_with_established_baseline": established,
        "demo_events": sum(1 for e in events if e.is_demo),
    }


@router.get("/events")
def events_analytics(db: Session = Depends(get_db)) -> dict:
    events = [repo.event_to_schema(r) for r in repo.list_events(db)]
    by_state = Counter(e.status.value for e in events)
    by_facility_type = Counter()
    for e in events:
        if e.facility_id:
            f = repo.get_facility(db, e.facility_id)
            if f:
                by_facility_type[f.facility_type] += 1
    by_classification = Counter(e.classification.value for e in events if e.classification)
    return {
        "by_state": dict(by_state), "by_facility_type": dict(by_facility_type),
        "by_classification": dict(by_classification),
        "deviation_scores": [repo.get_deviation(db, e.event_id).overall_deviation_score
                              for e in events if repo.get_deviation(db, e.event_id)],
        "peak_frp_values": [e.peak_frp for e in events if e.peak_frp is not None],
    }


@router.get("/risk")
def risk_analytics(db: Session = Depends(get_db)) -> dict:
    events = [repo.event_to_schema(r) for r in repo.list_events(db)]
    return {
        "risk_scores": [{"event_id": e.event_id, "risk_score": e.risk_score, "severity": e.severity.value if e.severity else None}
                         for e in events if e.risk_score is not None],
        "trajectory_directions": dict(Counter(e.trajectory_direction.value for e in events if e.trajectory_direction)),
        "model_metrics": get_latest_metrics().model_dump(),
    }
