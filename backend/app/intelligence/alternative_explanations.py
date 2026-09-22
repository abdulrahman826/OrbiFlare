"""Generates a primary hypothesis plus alternative explanations for an
event, rather than a single forced conclusion. Uses uncertainty-aware
language throughout -- no calibrated probabilities are attached to
hypotheses since the model isn't calibrated for that.
"""
from __future__ import annotations

from app.model.schemas import (
    AlternativeExplanations,
    BaselineConfidence,
    Deviation,
    DeviationStatus,
    Facility,
    Hypothesis,
    MLClass,
    MLPrediction,
    ThermalEvent,
)


def build_alternative_explanations(
    event: ThermalEvent, deviation: Deviation | None, ml: MLPrediction | None, facility: Facility | None,
) -> AlternativeExplanations:
    notable_dims = []
    if deviation is not None:
        for name, dim in (
            ("intensity", deviation.intensity), ("persistence", deviation.persistence),
            ("duration", deviation.duration), ("temporal", deviation.temporal),
            ("spatial", deviation.spatial), ("recurrence", deviation.recurrence),
        ):
            if dim.status == DeviationStatus.COMPUTED and (dim.is_notable or dim.is_significant):
                notable_dims.append(f"{name}_deviation")

    has_baseline = deviation is not None and deviation.baseline_confidence != BaselineConfidence.INSUFFICIENT
    ml_industrial = ml is not None and ml.predicted_class == MLClass.PERSISTENT_INDUSTRIAL and not ml.low_confidence
    ml_natural = ml is not None and ml.predicted_class == MLClass.NATURAL_CANDIDATE and not ml.low_confidence

    alternatives: list[Hypothesis] = []

    if not has_baseline:
        primary = Hypothesis(
            label="Unknown thermal source (insufficient baseline)",
            rationale="Not enough historical data exists for this location to compare current behaviour "
                       "against a facility baseline, so the interpretation is left open.",
            supporting_evidence_names=[], contradicting_evidence_names=[],
        )
        alternatives.append(Hypothesis(
            label="Persistent industrial thermal source", rationale="Plausible given facility proximity, but unverifiable without baseline history.",
            supporting_evidence_names=["facility_proximity"] if facility else [],
        ))
        alternatives.append(Hypothesis(
            label="Natural / agricultural fire candidate", rationale="Also plausible in the absence of a baseline; cannot be ruled out.",
        ))
    elif facility is not None and len(notable_dims) >= 2:
        primary = Hypothesis(
            label="Abnormal industrial thermal event",
            rationale=f"Facility context is present and {len(notable_dims)} behavioural dimension(s) "
                      f"deviate notably from the facility's established baseline.",
            supporting_evidence_names=notable_dims + (["rf_classification"] if ml_industrial else []),
            contradicting_evidence_names=["rf_classification"] if ml_natural else [],
        )
        alternatives.append(Hypothesis(
            label="Persistent industrial thermal source (elevated but routine)",
            rationale="Facility processes can occasionally run hotter/longer than typical without indicating an incident.",
            contradicting_evidence_names=notable_dims,
        ))
        alternatives.append(Hypothesis(
            label="Unknown thermal source", rationale="Deviation from baseline does not, by itself, identify the physical cause.",
        ))
    elif facility is not None:
        primary = Hypothesis(
            label="Persistent industrial thermal source",
            rationale="Facility context is present and observed behaviour is broadly consistent with the "
                       "facility's established historical baseline.",
            supporting_evidence_names=(["rf_classification"] if ml_industrial else []),
        )
        alternatives.append(Hypothesis(
            label="Early-stage abnormal event", rationale="A deviation may not yet be statistically detectable this early in the event.",
        ))
    else:
        primary = Hypothesis(
            label="Natural / agricultural fire candidate" if ml_natural or not ml else "Unknown thermal source",
            rationale="No industrial facility was found within the configured context radius of this event.",
            supporting_evidence_names=["rf_classification"] if ml_natural else [],
        )
        alternatives.append(Hypothesis(
            label="Unregistered or unmapped industrial activity",
            rationale="Facility datasets (OSM-derived) are known to be incomplete -- absence of a mapped facility does not rule out an industrial source.",
        ))
        alternatives.append(Hypothesis(label="Mining or other unclassified thermal source"))

    unknowns = [
        "Exact combustion source cannot be confirmed without ground inspection or high-resolution imagery.",
        "Facility proximity does not establish causation, even when a facility is nearby.",
        "Satellite pixel resolution limits precise spatial attribution.",
    ]
    if ml is not None and ml.low_confidence:
        unknowns.append("ML classifier confidence is below the reliability threshold for this event -- treat its signal as weak.")

    return AlternativeExplanations(event_id=event.event_id, primary_hypothesis=primary, alternatives=alternatives, unknowns=unknowns)
