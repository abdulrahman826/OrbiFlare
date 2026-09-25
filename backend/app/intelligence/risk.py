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


# Saturation points of the raw-evidence components (score reaches 100 here): used only to say what WOULD raise a score.
_PERSISTENCE_SATURATION_OBS = 100.0 / 8.0
_DURATION_SATURATION_H = 100.0 / 12.0
_INTENSITY_SATURATION_MW = 150.0
_NEXT_TIER = {Severity.LOW: ("MEDIUM", "risk_threshold_medium"), Severity.MEDIUM: ("HIGH", "risk_threshold_high"), Severity.HIGH: ("CRITICAL", "risk_threshold_critical")}


def baseline_factor(baseline: BaselineConfidence | None) -> float:
    """Evidence policy: how much of the behaviour-deviation signal may count, by baseline strength.
    ESTABLISHED = fully, LIMITED = discounted (limited history != strong anomaly evidence), INSUFFICIENT/none = not at all."""
    if baseline == BaselineConfidence.ESTABLISHED:
        return 1.0
    if baseline == BaselineConfidence.LIMITED:
        return settings.risk_limited_baseline_factor
    return 0.0


def latest_observation_frp(observations) -> float | None:
    """FRP of the most recent observation of an event (ties broken by observation id, so the result never depends on storage order).

    CANONICAL RISK DEFINITION: the intensity component of an event's risk always uses the FRP of its latest observation (the
    "most recent FRP reading" the explanation quotes). The stored event risk and the last point of its risk trajectory are
    both computed this way, so they can never disagree."""
    obs = sorted(observations or [], key=lambda o: (o.timestamp, o.observation_id))
    return obs[-1].frp if obs and obs[-1].frp is not None else None


def compute_risk(
    event: ThermalEvent, deviation: Deviation | None, ml: MLPrediction | None, facility_present: bool,
    recent_frp: float | None = None,
) -> Risk:
    """recent_frp: FRP of the event's most recent observation (see latest_observation_frp). It is the intensity input for BOTH the
    stored event risk and every trajectory point, so the event risk equals the last trajectory point. event.peak_frp (the
    cumulative all-time high) is only the fallback when no observation FRP is available, so a bare one-shot call still works."""
    components: dict[str, tuple[float, str]] = {}

    base = deviation.baseline_confidence if deviation else None
    raw_dev = deviation.overall_deviation_score if deviation else 0.0
    factor = baseline_factor(base)
    dev_score = raw_dev * factor
    if base == BaselineConfidence.ESTABLISHED:
        dev_note = f"Behavioural deviation from an ESTABLISHED facility baseline: {raw_dev:.0f}/100 (counts fully)."
    elif base == BaselineConfidence.LIMITED:
        dev_note = (f"Behavioural deviation from a LIMITED facility baseline: {raw_dev:.0f}/100, counted at {factor:.0%} "
                    f"({dev_score:.0f}/100) because limited history is not strong evidence of an anomaly.")
    else:
        dev_note = "No usable facility baseline (insufficient history or no facility context): deviation contributes 0."
    components["behaviour_deviation"] = (dev_score, dev_note)

    if ml is not None and ml.model_variant == "no_facility":
        # The distance-free model only sees persistence, FRP, brightness temperature and season/time -- inputs the risk engine already
        # scores directly (persistence, duration, intensity). Adding it again would count the same observations twice, so it is
        # shown as evidence but carries no additional weight in the score.
        components["ml_signal"] = (0.0, "ML ran without facility information; it restates persistence and intensity, which are already scored, so it adds no extra weight.")
    elif ml is not None:
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

    quality = event.facility_context_quality
    if facility_present and quality == "LOW":
        facility_score, facility_note = 0.0, "A generic industrial land-use record is nearby (low-quality context): shown as context, not counted as evidence."
    elif facility_present:
        facility_score, facility_note = 15.0, "Identified facility located nearby (spatial association only)."
    else:
        facility_score, facility_note = 0.0, "No nearby facility context."
    components["facility_context"] = (facility_score, facility_note)

    composite = sum(components[k][0] * _WEIGHTS[k] for k in _WEIGHTS)
    composite = round(min(100.0, max(0.0, composite)), 1)
    severity = _severity_for(composite)

    factors = [
        RiskFactor(name=k, contribution=round(components[k][0] * _WEIGHTS[k], 2), explanation=components[k][1])
        for k in _WEIGHTS if components[k][0] * _WEIGHTS[k] >= 3.0
    ]
    factors.sort(key=lambda f: f.contribution, reverse=True)

    caveats = ["Risk reflects operational prioritization for analyst review, not a confirmed fire probability."]
    if deviation is None or base is None or base == BaselineConfidence.INSUFFICIENT:
        caveats.append("Facility baseline is INSUFFICIENT -- behavioural deviation could not fully inform this score.")
    elif base == BaselineConfidence.LIMITED:
        caveats.append("Facility baseline is LIMITED -- deviation is discounted; limited history is not strong evidence of an anomaly.")
    if ml is not None and ml.low_confidence:
        caveats.append("ML classifier confidence is below the reliability threshold for this event.")
    if ml is not None:
        caveats.append("ML evidence uses proxy labels derived from facility proximity (<= 5 km) and persistence (>= 2); it partially overlaps with the "
                       "facility-context and persistence factors and is not independent confirmation. Evidence sources may be correlated; ML output is treated as one "
                       "evidence component.")
    caveats.append("Facility proximity is contextual and does not establish causation.")

    explanation_parts = [f"{f.name.replace('_', ' ').title()} (+{f.contribution:.0f})" for f in factors[:4]]
    explanation = (
        "Driven primarily by: " + ", ".join(explanation_parts) + "."
        if explanation_parts else "No single factor dominates this score."
    )

    # ---- analyst-facing explanation: what contributes, what limits, what is missing, what would raise it (conditional, not a forecast) ----
    contributing: list[str] = []
    for f in factors:
        c = f"+{f.contribution:.0f}"
        if f.name == "behaviour_deviation":
            contributing.append(f"behavioural deviation vs a {(base.value if base else 'n/a').lower()} facility baseline ({c})")
        elif f.name == "persistence":
            contributing.append(f"{event.observation_count} persistent observations ({c})")
        elif f.name == "duration":
            contributing.append(f"sustained duration of {event.duration_hours:.1f} h ({c})")
        elif f.name == "intensity":
            contributing.append(f"FRP up to {effective_frp or 0:.0f} MW ({c})")
        elif f.name == "ml_signal":
            contributing.append(f"ML class-A probability {ml.p_persistent_industrial:.2f}, one evidence component, from heuristic development labels that overlap with facility/persistence ({c})" if ml else f"ML ({c})")
        elif f.name == "facility_context":
            contributing.append(f"identified facility nearby, spatial association only ({c})")

    limiting: list[str] = []
    if base == BaselineConfidence.LIMITED:
        limiting.append(f"limited baseline: deviation counts at {factor:.0%} (insufficient history for strong behavioural inference)")
    elif base == BaselineConfidence.INSUFFICIENT:
        limiting.append("insufficient baseline: deviation contributes 0 (this is not evidence of normal or abnormal behaviour)")
    elif base is None:
        limiting.append("no facility baseline: there is no facility context to compare against (this is not evidence of a natural fire)")
    if not facility_present:
        limiting.append("no relevant facility context within the search radius (absence does not indicate a natural fire)")
    elif quality == "LOW":
        limiting.append("weak facility context: a generic industrial land-use record, not an identified installation")
    if ml is not None and ml.model_variant == "no_facility":
        limiting.append("ML ran without facility information (restates persistence and intensity), so it adds no extra weight to the score")
    elif ml is not None and ml.low_confidence:
        limiting.append("ML confidence is low")
    elif ml is not None and ml.p_natural_candidate > ml.p_persistent_industrial:
        limiting.append("ML evidence leans natural/agricultural candidate; not a verdict either way")
    if event.observation_count <= 1:
        limiting.append("single observation: no persistence yet")
    limiting.append("no independent incident confirmation (imagery, ground truth)")

    missing: list[str] = []
    if base != BaselineConfidence.ESTABLISHED:
        missing.append("an established facility baseline (enough real historical events)")
    if not facility_present or quality == "LOW":
        missing.append("an identified facility within the context radius")
    missing.append("independent confirmation of an incident")

    escalation: list[str] = []
    if event.observation_count < _PERSISTENCE_SATURATION_OBS:
        escalation.append(f"more persistent observations (now {event.observation_count}; the persistence factor saturates at {_PERSISTENCE_SATURATION_OBS:.0f})")
    if event.duration_hours < _DURATION_SATURATION_H:
        escalation.append(f"longer sustained duration (now {event.duration_hours:.1f} h; the duration factor saturates at {_DURATION_SATURATION_H:.1f} h)")
    if (effective_frp or 0.0) < _INTENSITY_SATURATION_MW:
        escalation.append(f"higher radiative power (now {effective_frp or 0:.0f} MW; the intensity factor saturates at {_INTENSITY_SATURATION_MW:.0f} MW)")
    if base != BaselineConfidence.ESTABLISHED:
        escalation.append("an established facility baseline, so behavioural deviation can count fully")
    if not facility_present or quality == "LOW":
        escalation.append("an identified facility within the context radius")

    if severity in _NEXT_TIER:
        tier, attr = _NEXT_TIER[severity]
        gap = getattr(settings, attr) - composite
        reason = f"{severity.value}: score {composite:.1f} is {gap:.1f} points below the {tier} threshold ({getattr(settings, attr):.0f})."
    else:
        reason = f"{severity.value}: score {composite:.1f} is at or above the CRITICAL threshold ({settings.risk_threshold_critical:.0f})."
    if limiting:
        reason += f" Main limit: {limiting[0]}."

    return Risk(event_id=event.event_id, risk_score=composite, severity=severity, risk_factors=factors,
                explanation=explanation, caveats=caveats,
                baseline_status=base.value if base else None, deviation_contribution=round(dev_score * _WEIGHTS["behaviour_deviation"], 2),
                deviation_contribution_cap=round(100.0 * factor * _WEIGHTS["behaviour_deviation"], 2), facility_context_quality=quality,
                contributing=contributing, limiting=limiting, missing_evidence=missing, escalation_evidence=escalation, severity_reason=reason)
