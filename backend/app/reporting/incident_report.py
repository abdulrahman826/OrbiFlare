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
        "data_label": "DEMO / SYNTHETIC" if e.is_demo else "REAL (FIRMS-derived)",
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
        "disclaimer": (
            "This report reflects satellite-derived thermal observations and computed intelligence. "
            "It does not constitute confirmation of a fire or attribution of causation. Operator "
            "validation is required before acting on this report."
        ),
    }
