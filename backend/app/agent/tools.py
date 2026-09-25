"""Controlled, read-only tool registry for the Fire Intelligence Agent.

Every tool here does exactly one thing: read real data through the same
repository/intelligence layers the REST API uses. Nothing here mutates
database state, runs arbitrary SQL, executes shell commands, or edits
files -- the agent can explain and report, never act.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.intelligence.investigation import get_investigation
from app.reporting.incident_report import build_incident_report
from app.storage import repositories as repo


def list_events(db: Session, severity: str | None = None, status: str | None = None, limit: int | None = 20) -> list[dict]:
    rows = repo.list_events(db, severity=severity, status=status)
    events = repo.attach_derived_event_fields(db, [repo.event_to_schema(r) for r in rows[:limit]])
    return [_event_summary(e) for e in events]


def list_high_risk_events(db: Session, limit: int | None = 10) -> list[dict]:
    rows = repo.list_events(db)
    events = sorted((repo.event_to_schema(r) for r in rows), key=lambda e: e.risk_score or 0, reverse=True)
    high_risk = [e for e in events if (e.severity and e.severity.value in ("HIGH", "CRITICAL"))][:limit]
    return [_event_summary(e) for e in repo.attach_derived_event_fields(db, high_risk)]


def list_escalating_events(db: Session, limit: int | None = 10) -> list[dict]:
    rows = repo.list_events(db, trajectory="ESCALATING")
    events = repo.attach_derived_event_fields(db, [repo.event_to_schema(r) for r in rows[:limit]])
    return [_event_summary(e) for e in events]


def list_insufficient_baseline_events(db: Session, limit: int | None = 10) -> list[dict]:
    """Events whose facility Thermal Twin has INSUFFICIENT history (or that have no facility
    baseline at all) -- i.e. events for which behavioural deviation cannot be assessed."""
    rows = repo.list_events(db)
    events = repo.attach_derived_event_fields(db, [repo.event_to_schema(r) for r in rows])
    picked = [e for e in events if getattr(e, "baseline_confidence", None) in (None, "INSUFFICIENT")
              or str(getattr(e, "baseline_confidence", "")).endswith("INSUFFICIENT")]
    picked.sort(key=lambda e: e.risk_score or 0, reverse=True)
    return [_event_summary(e) for e in picked[:limit]]


# --- Historical reference incidents (READ-ONLY; separate from FIRMS observations, events and demo data) ---

_INTERNAL_KEYS = {"source_dataset", "reference_repository", "boundary_source"}


def _public(obj):
    """Strip internal repository/file provenance from anything the console returns (kept in storage for traceability)."""
    if isinstance(obj, dict):
        return {k: _public(v) for k, v in obj.items() if k not in _INTERNAL_KEYS}
    if isinstance(obj, list):
        return [_public(v) for v in obj]
    return obj


def list_historical_incidents(db: Session, state: str | None = None, kind: str | None = None, limit: int = 30) -> list[dict]:
    from app.reference import incidents as ref
    return [_public(i.model_dump(mode="json")) for i in ref.list_incidents(state=state, kind=kind)[:limit]]


def get_historical_incident(db: Session, incident_id: str) -> dict | None:
    from app.reference import context, incidents as ref
    inc = ref.get_incident(incident_id)
    return _public(context.incident_context(db, inc).model_dump(mode="json")) if inc else None


def find_incidents_near_event(db: Session, event_id: str, radius_km: float = 50.0) -> dict | None:
    from app.reference import context
    row = repo.get_event(db, event_id)
    if row is None:
        return None
    e = repo.event_to_schema(row)
    return {"event_id": event_id, "radius_km": radius_km,
            "incidents": [{"distance_km": round(d, 1), **_public(i.model_dump(mode="json"))} for i, d in context.incidents_near(e.centroid_lat, e.centroid_lon, radius_km)]}


def find_incidents_near_facility(db: Session, facility_id: str, radius_km: float = 50.0) -> dict | None:
    from app.reference import context
    row = repo.get_facility(db, facility_id)
    if row is None:
        return None
    return {"facility_id": facility_id, "radius_km": radius_km,
            "incidents": [{"distance_km": round(d, 1), **_public(i.model_dump(mode="json"))} for i, d in context.incidents_near(row.latitude, row.longitude, radius_km)]}


def get_event(db: Session, event_id: str) -> dict | None:
    row = repo.get_event(db, event_id)
    if row is None:
        return None
    event = repo.attach_derived_event_fields(db, [repo.event_to_schema(row)])[0]
    return _event_summary(event)


def get_investigation_tool(db: Session, event_id: str) -> dict | None:
    inv = get_investigation(db, event_id)
    if inv is None:
        return None
    return {
        "event": _event_summary(inv.event),
        "facility": inv.facility.model_dump(mode="json") if inv.facility else None,
        "deviation": inv.deviation.model_dump(mode="json") if inv.deviation else None,
        "risk": inv.risk.model_dump(mode="json") if inv.risk else None,
        "trajectory": inv.trajectory.model_dump(mode="json") if inv.trajectory else None,
        "evidence": inv.evidence.model_dump(mode="json") if inv.evidence else None,
        "alternative_explanations": inv.alternative_explanations.model_dump(mode="json") if inv.alternative_explanations else None,
        "uncertainty_notes": inv.uncertainty_notes,
        "operator_state": inv.operator_state.value,
    }


def get_facility(db: Session, facility_id: str) -> dict | None:
    row = repo.get_facility(db, facility_id)
    return repo.facility_to_schema(row).model_dump(mode="json") if row else None


def get_thermal_twin(db: Session, facility_id: str) -> dict | None:
    twin = repo.get_thermal_twin(db, facility_id)
    return twin.model_dump(mode="json") if twin else None


def get_deviation(db: Session, event_id: str) -> dict | None:
    d = repo.get_deviation(db, event_id)
    return d.model_dump(mode="json") if d else None


def get_evidence(db: Session, event_id: str) -> dict | None:
    ev = repo.get_evidence(db, event_id)
    return ev.model_dump(mode="json") if ev else None


def get_risk(db: Session, event_id: str) -> dict | None:
    r = repo.get_risk(db, event_id)
    return r.model_dump(mode="json") if r else None


def get_trajectory(db: Session, event_id: str) -> dict | None:
    points = repo.get_trajectory_points(db, event_id)
    if not points:
        return None
    return {
        "event_id": event_id,
        "points": [{"timestamp": p.timestamp.isoformat(), "risk_score": p.risk_score,
                    "deviation_score": p.deviation_score, "severity": p.severity} for p in points],
    }


def compare_events(db: Session, event_id_a: str, event_id_b: str) -> dict | None:
    a, b = repo.get_event(db, event_id_a), repo.get_event(db, event_id_b)
    if a is None or b is None:
        return None
    ea, eb = repo.attach_derived_event_fields(db, [repo.event_to_schema(a), repo.event_to_schema(b)])
    return {"event_a": _event_summary(ea), "event_b": _event_summary(eb),
            "risk_delta": round((ea.risk_score or 0) - (eb.risk_score or 0), 1)}


def compare_facilities(db: Session, facility_id_a: str, facility_id_b: str) -> dict | None:
    twin_a, twin_b = repo.get_thermal_twin(db, facility_id_a), repo.get_thermal_twin(db, facility_id_b)
    if twin_a is None or twin_b is None:
        return None
    return {"facility_a": twin_a.model_dump(mode="json"), "facility_b": twin_b.model_dump(mode="json")}


def generate_report(db: Session, event_id: str) -> dict | None:
    inv = get_investigation(db, event_id)
    return build_incident_report(inv) if inv else None


# A ThermalEvent is treated as "persistent" once it accumulates 6+ source
# observations -- the same threshold the Command Center KPI uses
# (frontend/src/app/command-center/page.tsx), kept in sync deliberately.
PERSISTENT_OBSERVATION_THRESHOLD = 6


def list_persistent_events(db: Session, limit: int | None = 10) -> list[dict]:
    rows = repo.list_events(db)
    events = [repo.event_to_schema(r) for r in rows if r.status != "EXTINGUISHED"]
    persistent = sorted(
        (e for e in events if e.observation_count >= PERSISTENT_OBSERVATION_THRESHOLD),
        key=lambda e: e.observation_count, reverse=True,
    )[:limit]
    return [_event_summary(e) for e in repo.attach_derived_event_fields(db, persistent)]


def facility_event_frequency(db: Session, limit: int = 10) -> list[dict]:
    """Aggregate event (and persistent-event) counts per facility -- answers
    "which facility has the most persistent thermal activity" without ever
    claiming a cause, only counting what is already stored."""
    rows = repo.list_events(db)
    events = [repo.event_to_schema(r) for r in rows]
    counts: dict[str, dict] = {}
    for e in events:
        if not e.facility_id:
            continue
        c = counts.setdefault(e.facility_id, {"facility_id": e.facility_id, "event_count": 0, "persistent_event_count": 0})
        c["event_count"] += 1
        if e.observation_count >= PERSISTENT_OBSERVATION_THRESHOLD:
            c["persistent_event_count"] += 1
    ranked = sorted(counts.values(), key=lambda c: (c["persistent_event_count"], c["event_count"]), reverse=True)
    for c in ranked:
        f = repo.get_facility(db, c["facility_id"])
        c["name"] = f.name if f else c["facility_id"]
    return ranked[:limit]


def get_event_statistics(db: Session) -> dict:
    """Deterministic aggregate statistics computed directly from stored
    events -- nothing here is hardcoded or estimated."""
    rows = repo.list_events(db)
    events = [repo.event_to_schema(r) for r in rows]
    active = [e for e in events if e.status.value != "EXTINGUISHED"]
    high_risk = [e for e in active if e.severity and e.severity.value in ("HIGH", "CRITICAL")]
    critical = [e for e in active if e.severity and e.severity.value == "CRITICAL"]
    escalating = [e for e in active if e.trajectory_direction and e.trajectory_direction.value == "ESCALATING"]
    persistent = [e for e in active if e.observation_count >= PERSISTENT_OBSERVATION_THRESHOLD]
    frps = [e.peak_frp for e in events if e.peak_frp is not None]
    durations = [e.duration_hours for e in events]

    by_facility_type: dict[str, int] = {}
    by_region: dict[str, int] = {}
    for e in events:
        if e.facility_id:
            f = repo.get_facility(db, e.facility_id)
            if f:
                by_facility_type[f.facility_type] = by_facility_type.get(f.facility_type, 0) + 1
                region_key = f.region or f.state or "UNKNOWN"
                by_region[region_key] = by_region.get(region_key, 0) + 1

    severity_dist: dict[str, int] = {}
    for e in events:
        if e.severity:
            severity_dist[e.severity.value] = severity_dist.get(e.severity.value, 0) + 1

    return {
        "total_events": len(events),
        "active_events": len(active),
        "high_risk_events": len(high_risk),
        "critical_events": len(critical),
        "escalating_events": len(escalating),
        "persistent_events": len(persistent),
        "average_frp": round(sum(frps) / len(frps), 1) if frps else None,
        "peak_frp": round(max(frps), 1) if frps else None,
        "average_duration_hours": round(sum(durations) / len(durations), 1) if durations else None,
        "maximum_duration_hours": round(max(durations), 1) if durations else None,
        "events_by_facility_type": by_facility_type,
        "events_by_region": by_region,
        "risk_severity_distribution": severity_dist,
    }


def get_facility_statistics(db: Session, facility_id: str) -> dict | None:
    row = repo.get_facility(db, facility_id)
    if row is None:
        return None
    facility = repo.facility_to_schema(row)
    events = [repo.event_to_schema(r) for r in repo.list_events(db, facility_id=facility_id)]
    twin = repo.get_thermal_twin(db, facility_id)
    frps = [e.peak_frp for e in events if e.peak_frp is not None]
    return {
        "facility_id": facility_id,
        "name": facility.name,
        "facility_type": facility.facility_type,
        "total_events": len(events),
        "active_events": sum(1 for e in events if e.status.value != "EXTINGUISHED"),
        "high_risk_events": sum(1 for e in events if e.severity and e.severity.value in ("HIGH", "CRITICAL")),
        "persistent_events": sum(1 for e in events if e.observation_count >= PERSISTENT_OBSERVATION_THRESHOLD),
        "average_frp": round(sum(frps) / len(frps), 1) if frps else None,
        "baseline_confidence": twin.baseline_confidence.value if twin else "INSUFFICIENT",
    }


def get_risk_statistics(db: Session) -> dict:
    rows = repo.list_events(db)
    events = [repo.event_to_schema(r) for r in rows]
    scores = [e.risk_score for e in events if e.risk_score is not None]
    severity_dist: dict[str, int] = {}
    trajectory_dist: dict[str, int] = {}
    for e in events:
        if e.severity:
            severity_dist[e.severity.value] = severity_dist.get(e.severity.value, 0) + 1
        if e.trajectory_direction:
            trajectory_dist[e.trajectory_direction.value] = trajectory_dist.get(e.trajectory_direction.value, 0) + 1
    return {
        "scored_event_count": len(scores),
        "average_risk_score": round(sum(scores) / len(scores), 1) if scores else None,
        "peak_risk_score": round(max(scores), 1) if scores else None,
        "severity_distribution": severity_dist,
        "trajectory_distribution": trajectory_dist,
    }


def compare_event_to_baseline(db: Session, event_id: str) -> dict | None:
    """NORMAL vs. CURRENT vs. DEVIATION, read directly from the stored
    Deviation + ThermalTwin -- never fabricates a baseline that doesn't
    exist; if the facility's history is INSUFFICIENT this says so plainly."""
    event_row = repo.get_event(db, event_id)
    if event_row is None:
        return None
    event = repo.event_to_schema(event_row)
    deviation = repo.get_deviation(db, event_id)

    if deviation is None or deviation.baseline_confidence.value == "INSUFFICIENT":
        return {
            "event_id": event_id,
            "facility_id": event.facility_id,
            "baseline_status": "INSUFFICIENT_BASELINE",
            "message": "Insufficient baseline data.",
        }

    dims = {}
    for key in ("intensity", "persistence", "duration", "temporal", "spatial", "recurrence"):
        d = getattr(deviation, key)
        dims[key] = {
            "normal": d.expected_median,
            "current": d.observed_value,
            "deviation_z": d.robust_z,
            "is_notable": d.is_notable,
            "is_significant": d.is_significant,
            "explanation": d.explanation,
        }
    return {
        "event_id": event_id,
        "facility_id": event.facility_id,
        "baseline_status": deviation.baseline_confidence.value,
        "overall_deviation_score": deviation.overall_deviation_score,
        "dimensions": dims,
    }


def _deviation_label(score: float | None) -> str:
    """A coarse, honest label derived directly from the real, already-computed
    overall_deviation_score -- never a separate fabricated classification.
    None means no Deviation record exists yet for this event (e.g. no
    facility match), distinct from a real INSUFFICIENT-baseline score of 0."""
    if score is None:
        return "UNAVAILABLE"
    if score >= 50:
        return "SIGNIFICANT"
    if score > 0:
        return "NOTABLE"
    return "NORMAL"


def _event_summary(e) -> dict:
    return {
        "event_id": e.event_id, "status": e.status.value, "severity": e.severity.value if e.severity else None,
        "risk_score": e.risk_score, "trajectory_direction": e.trajectory_direction.value if e.trajectory_direction else None,
        "facility_id": e.facility_id, "facility_type": getattr(e, "facility_type", None),
        "baseline_confidence": getattr(e, "baseline_confidence", None),
        "overall_deviation_score": getattr(e, "overall_deviation_score", None),
        "deviation_label": _deviation_label(getattr(e, "overall_deviation_score", None)),
        "peak_frp": e.peak_frp, "duration_hours": e.duration_hours,
        "observation_count": e.observation_count, "is_demo": e.is_demo,
        "first_detected": e.first_detected.isoformat(), "classification": e.classification.value if e.classification else None,
    }


TOOL_REGISTRY: dict[str, Any] = {
    "list_events": list_events,
    "get_event": get_event,
    "get_investigation": get_investigation_tool,
    "get_facility": get_facility,
    "get_thermal_twin": get_thermal_twin,
    "get_deviation": get_deviation,
    "get_evidence": get_evidence,
    "get_risk": get_risk,
    "get_trajectory": get_trajectory,
    "compare_events": compare_events,
    "compare_facilities": compare_facilities,
    "list_high_risk_events": list_high_risk_events,
    "list_escalating_events": list_escalating_events,
    "list_persistent_events": list_persistent_events,
    "list_insufficient_baseline_events": list_insufficient_baseline_events,
    "list_historical_incidents": list_historical_incidents,
    "get_historical_incident": get_historical_incident,
    "find_incidents_near_event": find_incidents_near_event,
    "find_incidents_near_facility": find_incidents_near_facility,
    "facility_event_frequency": facility_event_frequency,
    "get_event_statistics": get_event_statistics,
    "get_facility_statistics": get_facility_statistics,
    "get_risk_statistics": get_risk_statistics,
    "compare_event_to_baseline": compare_event_to_baseline,
    "generate_report": generate_report,
}
