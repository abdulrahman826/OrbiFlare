"""Evidence Fusion -- assembles the structured Evidence Stack from
deviation, ML output and facility context.

Correlated evidence is explicitly flagged in `correlation_notes` rather than
silently counted as independent support (e.g. FRP drives both the intensity
deviation AND the ML model's strongest feature -- treating them as two
independent confirmations would double-count the same signal).
"""
from __future__ import annotations

from app.model.schemas import (
    Deviation,
    DeviationStatus,
    EvidenceCategory,
    EvidenceDirection,
    EvidenceItem,
    EvidenceStack,
    EvidenceStrength,
    Facility,
    MLClass,
    MLPrediction,
    ThermalEvent,
)

_STANDING_UNCERTAINTIES = [
    EvidenceItem(
        category=EvidenceCategory.GIS, name="satellite_resolution_limits",
        source="Domain knowledge (VIIRS/MODIS spatial resolution)",
        direction=EvidenceDirection.UNCERTAIN, strength=EvidenceStrength.MODERATE,
        explanation="Satellite thermal-anomaly pixel resolution (~375m VIIRS / ~1km MODIS) limits exact "
                    "attribution of the thermal source within that footprint.",
    ),
    EvidenceItem(
        category=EvidenceCategory.GIS, name="no_visual_confirmation",
        source="app.ingestion.satellite (no imagery provider configured)",
        direction=EvidenceDirection.UNAVAILABLE, strength=None,
        explanation="No direct visual/high-resolution imagery confirmation is available for this event.",
    ),
]


def _dim_to_evidence(name: str, category: EvidenceCategory, dev, source: str) -> EvidenceItem | None:
    if dev.status == DeviationStatus.INSUFFICIENT_BASELINE:
        return EvidenceItem(category=category, name=f"{name}_deviation", source=source,
                             direction=EvidenceDirection.UNAVAILABLE, explanation=dev.explanation)
    strength = EvidenceStrength.STRONG if dev.is_significant else (EvidenceStrength.MODERATE if dev.is_notable else EvidenceStrength.WEAK)
    direction = EvidenceDirection.SUPPORTING if (dev.is_notable or dev.is_significant) else EvidenceDirection.CONTRADICTING
    return EvidenceItem(
        category=category, name=f"{name}_deviation",
        observed_value=str(dev.observed_value), expected_value=str(dev.expected_median),
        source=source, direction=direction, strength=strength, explanation=dev.explanation,
    )


def build_evidence_stack(
    event: ThermalEvent, deviation: Deviation | None, ml: MLPrediction | None, facility: Facility | None,
) -> EvidenceStack:
    supporting: list[EvidenceItem] = []
    contradicting: list[EvidenceItem] = []
    uncertain: list[EvidenceItem] = list(_STANDING_UNCERTAINTIES)
    unavailable: list[EvidenceItem] = []
    correlation_notes: list[str] = []

    if deviation is not None:
        dims = [
            ("intensity", EvidenceCategory.THERMAL, deviation.intensity, "Behaviour Deviation Engine: intensity"),
            ("persistence", EvidenceCategory.BEHAVIOURAL, deviation.persistence, "Behaviour Deviation Engine: persistence"),
            ("duration", EvidenceCategory.BEHAVIOURAL, deviation.duration, "Behaviour Deviation Engine: duration"),
            ("temporal", EvidenceCategory.TEMPORAL, deviation.temporal, "Behaviour Deviation Engine: temporal"),
            ("spatial", EvidenceCategory.GIS, deviation.spatial, "Behaviour Deviation Engine: spatial footprint"),
            ("recurrence", EvidenceCategory.BEHAVIOURAL, deviation.recurrence, "Behaviour Deviation Engine: recurrence"),
        ]
        for name, category, dev, source in dims:
            item = _dim_to_evidence(name, category, dev, source)
            if item is None:
                continue
            if item.direction == EvidenceDirection.SUPPORTING:
                supporting.append(item)
            elif item.direction == EvidenceDirection.CONTRADICTING:
                contradicting.append(item)
            else:
                unavailable.append(item)
    else:
        unavailable.append(EvidenceItem(
            category=EvidenceCategory.BEHAVIOURAL, name="deviation_unavailable",
            source="Behaviour Deviation Engine", direction=EvidenceDirection.UNAVAILABLE,
            explanation="No facility association -- behavioural deviation could not be assessed.",
        ))

    if ml is not None:
        strong_industrial = ml.predicted_class == MLClass.PERSISTENT_INDUSTRIAL and not ml.low_confidence
        strong_natural = ml.predicted_class == MLClass.NATURAL_CANDIDATE and not ml.low_confidence
        ml_item = EvidenceItem(
            category=EvidenceCategory.ML, name="rf_classification",
            observed_value=f"P(industrial)={ml.p_persistent_industrial:.2f}, P(natural)={ml.p_natural_candidate:.2f}",
            source=f"Random Forest classifier ({ml.model_version}, proxy-labelled training data)",
            direction=(EvidenceDirection.SUPPORTING if strong_industrial else
                       EvidenceDirection.CONTRADICTING if strong_natural else EvidenceDirection.UNCERTAIN),
            strength=EvidenceStrength.MODERATE if not ml.low_confidence else EvidenceStrength.WEAK,
            explanation=(
                f"Model assigns P(persistent industrial)={ml.p_persistent_industrial:.2f} vs. "
                f"P(natural/agricultural candidate)={ml.p_natural_candidate:.2f}."
                + (" Confidence is low -- treat as an anomaly candidate signal only, not a classification." if ml.low_confidence else "")
            ),
            related_to=["intensity_deviation"],
        )
        if strong_industrial:
            supporting.append(ml_item)
        elif strong_natural:
            contradicting.append(ml_item)
        else:
            uncertain.append(ml_item)

        if deviation is not None and deviation.intensity.status == DeviationStatus.COMPUTED and deviation.intensity.is_notable:
            correlation_notes.append(
                "The thermal intensity deviation and the ML classifier's signal are correlated (both are "
                "heavily influenced by observed FRP) -- they should not be read as fully independent confirmations."
            )
    else:
        unavailable.append(EvidenceItem(
            category=EvidenceCategory.ML, name="rf_classification_unavailable", source="Random Forest classifier",
            direction=EvidenceDirection.UNAVAILABLE, explanation="ML classification could not be computed for this event.",
        ))

    if facility is not None and event.facility_distance_km is not None:
        uncertain.append(EvidenceItem(
            category=EvidenceCategory.FACILITY, name="facility_proximity",
            observed_value=f"{event.facility_distance_km:.2f} km", source="Facility spatial index (nearest-neighbour)",
            direction=EvidenceDirection.UNCERTAIN, strength=EvidenceStrength.MODERATE,
            explanation=(
                f"{facility.name} ({facility.facility_type.replace('_', ' ')}) is located approximately "
                f"{event.facility_distance_km:.2f} km from the event. This is spatial CONTEXT only -- "
                f"proximity does not by itself establish that the facility is the thermal source."
            ),
        ))
    else:
        unavailable.append(EvidenceItem(
            category=EvidenceCategory.FACILITY, name="facility_proximity_unavailable", source="Facility spatial index",
            direction=EvidenceDirection.UNAVAILABLE,
            explanation="No known industrial facility was found within the configured context radius of this event.",
        ))

    return EvidenceStack(
        event_id=event.event_id, supporting_evidence=supporting, contradicting_evidence=contradicting,
        uncertain_evidence=uncertain, unavailable_evidence=unavailable, correlation_notes=correlation_notes,
    )
