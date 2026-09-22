"""Risk Engine -- operational prioritization, NOT a fire-probability model.

Combines behavioural deviation, ML evidence, raw thermal persistence/
duration/intensity, and facility context into one explainable 0-100 score.
Every score decomposes into named, weighted factors so severity is never a
black box.
"""
from __future__ import annotations

from app.config import get_settings
from app.model.schemas import (
    BaselineConfidence,
    Deviation,
    MLClass,
    MLPrediction,
    Risk,
    RiskFactor,
    Severity,
    ThermalEvent,
)

settings = get_settings()

_WEIGHTS = {
    "behaviour_deviation": 0.35,
    "ml_signal": 0.15,
    "persistence": 0.15,
    "duration": 0.15,
    "intensity": 0.10,
    "facility_context": 0.10,
}


def _severity_for(score: float) -> Severity:
    if score >= settings.risk_threshold_critical:
        return Severity.CRITICAL
    if score >= settings.risk_threshold_high:
        return Severity.HIGH
    if score >= settings.risk_threshold_medium:
        return Severity.MEDIUM
    return Severity.LOW


def compute_risk(
    event: ThermalEvent, deviation: Deviation | None, ml: MLPrediction | None, facility_present: bool,
    recent_frp: float | None = None,
) -> Risk:
    """recent_frp: optional most-recent-observation FRP, used only for the
    intensity component's replay/trajectory sensitivity. event.peak_frp
    (the all-time high for the event) is cumulative and never decreases as
    an event unfolds; recent_frp lets the risk trajectory respond when later
    readings taper off, rather than being purely monotonic. Defaults to
    event.peak_frp so a one-shot risk call behaves exactly as before."""
    components: dict[str, tuple[float, str]] = {}

    dev_score = deviation.overall_deviation_score if deviation else 0.0
    components["behaviour_deviation"] = (dev_score, f"Composite behavioural deviation from facility baseline: {dev_score:.0f}/100.")

    if ml is not None:
        ml_score = ml.p_persistent_industrial * 100
        note = "low-confidence" if ml.low_confidence else "moderate-to-high-confidence"
        components["ml_signal"] = (ml_score, f"ML classifier P(persistent industrial)={ml.p_persistent_industrial:.2f} ({note}).")
    else:
        components["ml_signal"] = (0.0, "ML classification unavailable.")

    persistence_score = min(100.0, event.observation_count * 8.0)
    components["persistence"] = (persistence_score, f"{event.observation_count} observation(s) recorded for this event.")

    duration_score = min(100.0, event.duration_hours * 12.0)
    components["duration"] = (duration_score, f"Event duration of {event.duration_hours:.1f} hour(s).")

    effective_frp = recent_frp if recent_frp is not None else event.peak_frp
    intensity_score = min(100.0, (effective_frp or 0.0) / 1.5)
    components["intensity"] = (intensity_score, f"Most recent FRP reading of {effective_frp or 0:.0f} MW.")

    facility_score = 15.0 if facility_present else 0.0
    components["facility_context"] = (facility_score, "Industrial facility located nearby." if facility_present else "No nearby facility context.")

    composite = sum(components[k][0] * _WEIGHTS[k] for k in _WEIGHTS)
    composite = round(min(100.0, max(0.0, composite)), 1)
    severity = _severity_for(composite)

    factors = [
        RiskFactor(name=k, contribution=round(components[k][0] * _WEIGHTS[k], 2), explanation=components[k][1])
        for k in _WEIGHTS if components[k][0] * _WEIGHTS[k] >= 3.0
    ]
    factors.sort(key=lambda f: f.contribution, reverse=True)

    caveats = ["Risk reflects operational prioritization for analyst review, not a confirmed fire probability."]
    if deviation is None or deviation.baseline_confidence == BaselineConfidence.INSUFFICIENT:
        caveats.append("Facility baseline is INSUFFICIENT -- behavioural deviation could not fully inform this score.")
    if ml is not None and ml.low_confidence:
        caveats.append("ML classifier confidence is below the reliability threshold for this event.")
    caveats.append("Facility proximity is contextual and does not establish causation.")

    explanation_parts = [f"{f.name.replace('_', ' ').title()} (+{f.contribution:.0f})" for f in factors[:4]]
    explanation = (
        "Driven primarily by: " + ", ".join(explanation_parts) + "."
        if explanation_parts else "No single factor dominates this score."
    )

    return Risk(event_id=event.event_id, risk_score=composite, severity=severity, risk_factors=factors,
                explanation=explanation, caveats=caveats)
