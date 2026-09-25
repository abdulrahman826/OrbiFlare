"""Full event incident report: identity, coordinates, timestamps,
observations, facility context, thermal twin, deviation, ML evidence,
evidence stack, risk, trajectory, uncertainty and operator status -- the
complete traceable record for one event.
"""
from __future__ import annotations

from datetime import datetime

from app.model.schemas import Investigation


def build_incident_report(investigation: Investigation) -> dict:
    e = investigation.event
    return {
        "report_generated_at": datetime.utcnow().isoformat(),
        "data_label": "DEMO" if e.is_demo else "REAL (FIRMS-derived)",
        "identity": {"event_id": e.event_id, "status": e.status.value, "classification": e.classification.value if e.classification else None},
        "location": {
            "centroid_lat": e.centroid_lat, "centroid_lon": e.centroid_lon,
            "footprint_radius_km": e.footprint_radius_km,
        },
        "timing": {
            "first_detected": e.first_detected.isoformat(), "last_detected": e.last_detected.isoformat(),
            "duration_hours": e.duration_hours,
        },
        "observations": [o.model_dump(mode="json") for o in investigation.observations],
        "facility_context": investigation.facility.model_dump(mode="json") if investigation.facility else None,
        "facility_distance_km": e.facility_distance_km,
        "thermal_twin": investigation.thermal_twin.model_dump(mode="json") if investigation.thermal_twin else None,
        "deviation": investigation.deviation.model_dump(mode="json") if investigation.deviation else None,
        "ml_evidence": investigation.ml_prediction.model_dump(mode="json") if investigation.ml_prediction else None,
        "evidence_stack": investigation.evidence.model_dump(mode="json") if investigation.evidence else None,
        "alternative_explanations": investigation.alternative_explanations.model_dump(mode="json") if investigation.alternative_explanations else None,
        "risk": investigation.risk.model_dump(mode="json") if investigation.risk else None,
        "trajectory": investigation.trajectory.model_dump(mode="json") if investigation.trajectory else None,
        "uncertainty_notes": investigation.uncertainty_notes,
        "operator_state": investigation.operator_state.value,
        "operator_history": investigation.operator_history,
        "historical_reference_context": _historical_context(e.centroid_lat, e.centroid_lon),
        "disclaimer": (
            "This report reflects satellite-derived thermal observations and computed intelligence. "
            "It does not constitute confirmation of a fire or attribution of causation. Operator "
            "validation is required before acting on this report."
        ),
    }


def _historical_context(lat: float, lon: float, radius_km: float = 50.0) -> dict:
    """Nearby HISTORICAL reference incidents -- context only, clearly separated from the current event."""
    from app.reference import context
    hits = context.incidents_near(lat, lon, radius_km)
    return {
        "label": "HISTORICAL REFERENCE CONTEXT -- not part of this event and not FIRMS detections",
        "radius_km": radius_km,
        "incidents": [{"incident_id": i.incident_id, "name": i.name, "date": i.date, "record_kind": i.record_kind,
                       "distance_km": round(d, 1), "source_label": i.provenance.source_label} for i, d in hits],
        "note": "Proximity to a historical record is not evidence of causation or recurrence.",
    }


INTERNAL_PROVENANCE_KEYS = ("source_dataset", "reference_repository", "boundary_source")


def _public_incident(inc) -> dict:
    """User-facing view of a historical incident: internal repository/file provenance stays in storage and the raw
    API for traceability, but is not printed in exported documents."""
    d = inc.model_dump(mode="json")
    prov = {k: v for k, v in d["provenance"].items() if k not in INTERNAL_PROVENANCE_KEYS}
    prov.update({
        "source": "Historical incident reference",
        "dataset": "Historical incident record",
        "status_label": "Historical reference \u2014 not a live FIRMS detection",
    })
    d["provenance"] = prov
    return d


def build_historical_incident_report(ctx) -> dict:
    """Report for ONE historical reference incident. Deliberately cannot be mistaken for a current FIRMS detection."""
    inc = ctx.incident
    return {
        "report_generated_at": datetime.utcnow().isoformat(),
        "report_type": "HISTORICAL_REFERENCE_INCIDENT",
        "data_label": "HISTORICAL REFERENCE -- NOT A LIVE FIRMS DETECTION",
        "incident": _public_incident(inc),
        "administrative_context": ctx.admin.model_dump(mode="json", exclude={"boundary_source"}),
        "facility_context": [f.model_dump(mode="json") for f in ctx.nearby_facilities],
        "current_thermal_events_nearby": [e.model_dump(mode="json") for e in ctx.nearby_current_events],
        "firms_match_check": ctx.firms_match.model_dump(mode="json"),
        "known": ctx.known,
        "unknown": ctx.unknown,
        "disclaimer": (
            "This is a historical reference record from a curated dataset. It has not been verified by OrbiFlare, "
            "is not a satellite detection, and is not used for model training. Nearby facilities or events are spatial "
            "context only and do not establish causation."
        ),
    }
