"""Evidence Fusion -- assembles the structured Evidence Stack from
deviation, ML output and facility context.

Correlated evidence is explicitly flagged in `correlation_notes` rather than
silently counted as independent support (e.g. FRP drives both the intensity
deviation AND the ML model's strongest feature -- treating them as two
independent confirmations would double-count the same signal).
"""
from __future__ import annotations

from app.model.schemas import (
    BaselineConfidence,
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


def _dim_to_evidence(name: str, category: EvidenceCategory, dev, source: str, baseline: BaselineConfidence | None = None) -> EvidenceItem | None:
    if dev.status == DeviationStatus.INSUFFICIENT_BASELINE:
        return EvidenceItem(category=category, name=f"{name}_deviation", source=source,
                             direction=EvidenceDirection.UNAVAILABLE, explanation=dev.explanation)
    strength = EvidenceStrength.STRONG if dev.is_significant else (EvidenceStrength.MODERATE if dev.is_notable else EvidenceStrength.WEAK)
    direction = EvidenceDirection.SUPPORTING if (dev.is_notable or dev.is_significant) else EvidenceDirection.CONTRADICTING
    explanation = dev.explanation
    if baseline == BaselineConfidence.LIMITED:
        # A comparison with LIMITED history is cautious by construction: its strength is lowered one step and it says so.
        strength = {EvidenceStrength.STRONG: EvidenceStrength.MODERATE, EvidenceStrength.MODERATE: EvidenceStrength.WEAK}.get(strength, strength)
        if dev.is_notable or dev.is_significant:
            explanation += " (Compared with a LIMITED baseline: insufficient history for strong behavioural inference.)"
    return EvidenceItem(
        category=category, name=f"{name}_deviation",
        observed_value=str(dev.observed_value), expected_value=str(dev.expected_median),
        source=source, direction=direction, strength=strength, explanation=explanation,
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
            item = _dim_to_evidence(name, category, dev, source, deviation.baseline_confidence)
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
        # Without facility information the model only restates persistence/thermal inputs already counted elsewhere: it is never listed as
        # supporting or contradicting evidence, only as an uncertain, weak component.
        facility_blind = ml.model_variant == "no_facility"
        strong_industrial = ml.predicted_class == MLClass.PERSISTENT_INDUSTRIAL and not ml.low_confidence and not facility_blind
        strong_natural = ml.predicted_class == MLClass.NATURAL_CANDIDATE and not ml.low_confidence and not facility_blind
        ml_item = EvidenceItem(
            category=EvidenceCategory.ML, name="rf_classification",
            observed_value=f"P(industrial)={ml.p_persistent_industrial:.2f}, P(natural)={ml.p_natural_candidate:.2f}",
            source=f"Random Forest classifier ({ml.model_version}, heuristic development labels)",
            direction=(EvidenceDirection.SUPPORTING if strong_industrial else
                       EvidenceDirection.CONTRADICTING if strong_natural else EvidenceDirection.UNCERTAIN),
            strength=EvidenceStrength.MODERATE if not (ml.low_confidence or facility_blind) else EvidenceStrength.WEAK,
            explanation=(
                f"Model assigns P(persistent industrial)={ml.p_persistent_industrial:.2f} vs. "
                f"P(natural/agricultural candidate)={ml.p_natural_candidate:.2f}."
                + (" Confidence is low -- treat as an anomaly candidate signal only, not a classification." if ml.low_confidence else "")
                + ("" if ml.facility_context_state == "USABLE" else " No usable facility context was available, so the model was run without any facility-distance input (missing facility information is not treated as a distance.)")
            ),
            related_to=["intensity_deviation"],
        )
        if strong_industrial:
            supporting.append(ml_item)
        elif strong_natural:
            contradicting.append(ml_item)
        else:
            uncertain.append(ml_item)

        correlation_notes.append(
            "ML evidence uses proxy labels derived from facility proximity (<= 5 km) and persistence (>= 2). It therefore partially overlaps with the "
            "facility-context and persistence evidence and must not be read as an independent confirmation. Evidence sources may be correlated; ML output is treated as one evidence component."
        )
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
                f"{event.facility_distance_km:.2f} km from the event"
                + (f" ({event.facility_context_quality.lower()}-quality context)" if event.facility_context_quality else "")
                + ". This is spatial CONTEXT only -- proximity does not by itself establish that the facility is the thermal source."
            ),
        ))
    else:
        unavailable.append(EvidenceItem(
            category=EvidenceCategory.FACILITY, name="facility_proximity_unavailable", source="Facility spatial index",
            direction=EvidenceDirection.UNAVAILABLE,
            explanation="No relevant facility context within the configured radius. Absence of facility context does not indicate a natural fire.",
        ))

    return EvidenceStack(
        event_id=event.event_id, supporting_evidence=supporting, contradicting_evidence=contradicting,
        uncertain_evidence=uncertain, unavailable_evidence=unavailable, correlation_notes=correlation_notes,
    )
