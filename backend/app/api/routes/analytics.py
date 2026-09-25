"""Precomputed-friendly analytics endpoints. At this data scale we compute
on read; if/when data volume grows, these aggregations are the natural place
to swap in cached materialized views without changing the response shape.
"""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ingestion.firms import INDIA_BBOX
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
    by_region = Counter()
    by_admin_state = Counter()
    from app.reference import admin as admin_ref
    for e in events:
        r = admin_ref.resolve(e.centroid_lat, e.centroid_lon)
        by_admin_state[r.state if r.resolved else "Outside boundary data"] += 1
    for e in events:
        if e.facility_id:
            f = repo.get_facility(db, e.facility_id)
            if f:
                by_facility_type[f.facility_type] += 1
                by_region[f.region or f.state or "Unspecified"] += 1
            else:
                by_region["No facility context"] += 1
        else:
            by_region["No facility context"] += 1
    by_classification = Counter(e.classification.value for e in events if e.classification)
    return {
        "by_state": dict(by_state), "by_region": dict(by_region), "by_admin_state": dict(by_admin_state), "by_facility_type": dict(by_facility_type),
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


@router.get("/data-quality")
def data_quality(db: Session = Depends(get_db)) -> dict:
    """Surfaces two things that already exist but were previously computed
    and stored without ever being exposed anywhere: (1) every ingestion
    batch's DataQualityRecord (rows received/accepted/flagged/rejected +
    issue counts), and (2) a coordinate-range breakdown of every stored
    observation against the configured ingestion bounding box.

    This is deliberately a BOUNDING-BOX check, not administrative-boundary
    (state/district) geometry -- there is no such polygon dataset in this
    build, and this endpoint never claims that precision. Points are never
    moved, clipped, or dropped because of this check; it is read-only
    reporting over what was actually ingested."""
    batches = [
        {
            "batch_id": b.batch_id, "source": b.source, "ingested_at": b.ingested_at.isoformat(),
            "rows_received": b.rows_received, "rows_accepted": b.rows_accepted,
            "rows_flagged": b.rows_flagged, "rows_rejected": b.rows_rejected, "issues": b.issues,
        }
        for b in repo.list_data_quality(db)
    ]

    observations = repo.list_all_observations(db)
    west, south, east, north = INDIA_BBOX
    in_region = 0
    outside_samples: list[dict] = []
    lats: list[float] = []
    lons: list[float] = []
    for o in observations:
        lats.append(o.latitude)
        lons.append(o.longitude)
        inside = (south <= o.latitude <= north) and (west <= o.longitude <= east)
        if inside:
            in_region += 1
        elif len(outside_samples) < 10:
            outside_samples.append({
                "observation_id": o.observation_id, "latitude": o.latitude, "longitude": o.longitude,
                "source": o.source, "timestamp": o.timestamp.isoformat(),
            })

    return {
        "ingestion_batches": batches,
        "coordinate_validation": {
            "region_bbox": {"west": west, "south": south, "east": east, "north": north, "label": "configured ingestion bounding box (not administrative boundaries)"},
            "total_observations": len(observations),
            "in_region_count": in_region,
            "outside_region_count": len(observations) - in_region,
            "latitude_range": [min(lats), max(lats)] if lats else None,
            "longitude_range": [min(lons), max(lons)] if lons else None,
            "outside_region_samples": outside_samples,
        },
    }
