"""Behaviour Deviation Engine -- compares a live ThermalEvent against its
Facility Thermal Twin across six independent dimensions: intensity,
persistence, duration, temporal timing, spatial footprint, and recurrence.

Deviation is its own intelligence layer. It never collapses directly into a
fire probability or a risk score -- see app/intelligence/risk.py for how it
is later combined (as one signal among several) into an operational risk
score. If the baseline is insufficient, every dimension reports
INSUFFICIENT_BASELINE rather than a fabricated number.
"""
from __future__ import annotations

from datetime import datetime

from app.config import get_settings
from app.intelligence.clustering import haversine_km
from app.model.schemas import (
    BaselineConfidence,
    DeviationStatus,
    Deviation,
    DimensionDeviation,
    DistributionSummary,
    ThermalEvent,
    ThermalObservation,
    ThermalTwin,
)

settings = get_settings()


def _robust_z(observed: float, dist: DistributionSummary) -> float | None:
    if dist.median is None or dist.mad is None:
        return None
    scale = dist.mad * 1.4826  # MAD -> std-equivalent under normality
    if scale < 1e-6:
        # Degenerate (near-zero spread) baseline: fall back to IQR-based scale.
        iqr = (dist.q75 or 0) - (dist.q25 or 0)
        scale = max(iqr / 1.349, 0.5)
    return (observed - dist.median) / scale


def _classify(z: float | None) -> tuple[bool, bool]:
    if z is None:
        return False, False
    az = abs(z)
    return (az >= settings.deviation_notable_threshold, az >= settings.deviation_significant_threshold)


def _insufficient(dimension: str, reason: str) -> DimensionDeviation:
    return DimensionDeviation(
        dimension=dimension, status=DeviationStatus.INSUFFICIENT_BASELINE,
        explanation=f"Insufficient historical baseline to assess {dimension} deviation: {reason}",
    )


def _intensity(event: ThermalEvent, twin: ThermalTwin) -> DimensionDeviation:
    observed = event.peak_frp
    if observed is None:
        return _insufficient("intensity", "event has no FRP measurement")
    z = _robust_z(observed, twin.normal_frp)
    notable, significant = _classify(z)
    expected_range = (twin.normal_frp.q25, twin.normal_frp.q75) if twin.normal_frp.q25 is not None else None
    if significant:
        explanation = f"Observed peak FRP ({observed:.0f} MW) is substantially above the facility's historical range."
    elif notable:
        explanation = f"Observed peak FRP ({observed:.0f} MW) is somewhat above the facility's typical range."
    else:
        explanation = f"Observed peak FRP ({observed:.0f} MW) is within the facility's historical range."
    return DimensionDeviation(dimension="intensity", status=DeviationStatus.COMPUTED, observed_value=observed,
                               expected_median=twin.normal_frp.median, expected_range=expected_range,
                               robust_z=round(z, 2) if z is not None else None, is_notable=notable,
                               is_significant=significant, explanation=explanation)


def _persistence(event: ThermalEvent, twin: ThermalTwin) -> DimensionDeviation:
    observed = float(event.observation_count)
    z = _robust_z(observed, twin.normal_persistence)
    notable, significant = _classify(z)
    expected_range = (twin.normal_persistence.q25, twin.normal_persistence.q75) if twin.normal_persistence.q25 is not None else None
    if significant:
        explanation = f"Event persisted across {event.observation_count} observations, well above the facility's normal persistence."
    elif notable:
        explanation = f"Event persisted across {event.observation_count} observations, somewhat above normal."
    else:
        explanation = f"Persistence ({event.observation_count} observations) is consistent with normal behaviour."
    return DimensionDeviation(dimension="persistence", status=DeviationStatus.COMPUTED, observed_value=observed,
                               expected_median=twin.normal_persistence.median, expected_range=expected_range,
                               robust_z=round(z, 2) if z is not None else None, is_notable=notable,
                               is_significant=significant, explanation=explanation)


def _duration(event: ThermalEvent, twin: ThermalTwin) -> DimensionDeviation:
    observed = event.duration_hours
    z = _robust_z(observed, twin.normal_duration)
    notable, significant = _classify(z)
    expected_range = (twin.normal_duration.q25, twin.normal_duration.q75) if twin.normal_duration.q25 is not None else None
    if significant:
        explanation = f"Event duration ({observed:.1f}h) is substantially longer than the facility's normal event duration."
    elif notable:
        explanation = f"Event duration ({observed:.1f}h) is somewhat longer than normal."
    else:
        explanation = f"Event duration ({observed:.1f}h) is consistent with normal behaviour."
    return DimensionDeviation(dimension="duration", status=DeviationStatus.COMPUTED, observed_value=observed,
                               expected_median=twin.normal_duration.median, expected_range=expected_range,
                               robust_z=round(z, 2) if z is not None else None, is_notable=notable,
                               is_significant=significant, explanation=explanation)


def _temporal(event: ThermalEvent, twin: ThermalTwin, observations: list[ThermalObservation]) -> DimensionDeviation:
    if not twin.normal_hour_pattern:
        return _insufficient("temporal", "no historical hour-of-day pattern available")
    # "Typical" hours = any hour with above-uniform historical frequency (>1/24).
    typical_hours = {int(h) for h, freq in twin.normal_hour_pattern.items() if freq > (1 / 24)}
    event_hours = [o.timestamp.hour for o in observations] or [event.first_detected.hour]
    outside = sum(1 for h in event_hours if h not in typical_hours)
    outside_fraction = outside / len(event_hours)
    notable, significant = outside_fraction >= 0.34, outside_fraction >= 0.6
    typical_str = ", ".join(f"{h:02d}:00" for h in sorted(typical_hours)) or "no clear pattern"
    if significant:
        explanation = f"Event activity occurs substantially outside the facility's typical hours ({typical_str})."
    elif notable:
        explanation = f"Event activity partially extends beyond the facility's typical hours ({typical_str})."
    else:
        explanation = "Event timing is consistent with the facility's normal activity hours."
    return DimensionDeviation(dimension="temporal", status=DeviationStatus.COMPUTED,
                               observed_value=round(outside_fraction, 3), expected_median=0.0,
                               robust_z=round(outside_fraction * 4, 2), is_notable=notable,
                               is_significant=significant, explanation=explanation)


def _spatial(event: ThermalEvent, twin: ThermalTwin) -> DimensionDeviation:
    if twin.normal_spatial_centroid_lat is None or twin.normal_spatial_radius_km is None:
        return _insufficient("spatial", "no historical spatial footprint available")
    distance = haversine_km(twin.normal_spatial_centroid_lat, twin.normal_spatial_centroid_lon,
                             event.centroid_lat, event.centroid_lon)
    radius = max(twin.normal_spatial_radius_km, 0.05)
    ratio = distance / radius
    notable, significant = ratio >= 1.5, ratio >= 3.0
    if significant:
        explanation = (f"Thermal activity is occurring well outside the facility's historical thermal footprint "
                        f"(~{distance:.2f} km from the normal zone, vs. a typical radius of ~{radius:.2f} km).")
    elif notable:
        explanation = f"Thermal activity is somewhat outside the facility's usual thermal footprint (~{distance:.2f} km from the normal zone)."
    else:
        explanation = "Thermal activity is within the facility's historical spatial footprint."
    return DimensionDeviation(dimension="spatial", status=DeviationStatus.COMPUTED, observed_value=round(distance, 3),
                               expected_median=0.0, expected_range=(0.0, radius), robust_z=round(ratio, 2),
                               is_notable=notable, is_significant=significant, explanation=explanation)


def _recurrence(event: ThermalEvent, twin: ThermalTwin) -> DimensionDeviation:
    if twin.normal_recurrence_days is None or twin.history_end is None:
        return _insufficient("recurrence", "not enough historical events to establish a recurrence interval")
    observed_gap_days = max(0.0, (event.first_detected - twin.history_end).total_seconds() / 86400.0)
    expected = twin.normal_recurrence_days
    ratio = observed_gap_days / expected if expected > 0 else 1.0
    notable, significant = ratio <= 0.4, ratio <= 0.15
    if significant:
        explanation = f"Event recurred much sooner ({observed_gap_days:.1f}d) than the facility's typical ~{expected:.0f}d interval."
    elif notable:
        explanation = f"Event recurred somewhat sooner ({observed_gap_days:.1f}d) than the facility's typical ~{expected:.0f}d interval."
    else:
        explanation = f"Time since the last comparable event (~{observed_gap_days:.1f}d) is consistent with the normal recurrence pattern."
    return DimensionDeviation(dimension="recurrence", status=DeviationStatus.COMPUTED, observed_value=round(observed_gap_days, 2),
                               expected_median=expected, robust_z=round((1 - ratio) * 3, 2), is_notable=notable,
                               is_significant=significant, explanation=explanation)


def compute_deviation(event: ThermalEvent, twin: ThermalTwin | None, observations: list[ThermalObservation]) -> Deviation:
    if twin is None or twin.baseline_confidence == BaselineConfidence.INSUFFICIENT:
        reason = "facility has too little recorded history" if twin else "no thermal twin exists for this facility"
        dims = {name: _insufficient(name, reason) for name in
                ("intensity", "persistence", "duration", "temporal", "spatial", "recurrence")}
        return Deviation(
            event_id=event.event_id, facility_id=event.facility_id,
            baseline_confidence=twin.baseline_confidence if twin else BaselineConfidence.INSUFFICIENT,
            intensity=dims["intensity"], persistence=dims["persistence"], duration=dims["duration"],
            temporal=dims["temporal"], spatial=dims["spatial"], recurrence=dims["recurrence"],
            overall_deviation_score=0.0,
            explanations=["INSUFFICIENT BASELINE: not enough historical data exists for this facility to assess deviation from normal behaviour."],
        )

    intensity = _intensity(event, twin)
    persistence = _persistence(event, twin)
    duration = _duration(event, twin)
    temporal = _temporal(event, twin, observations)
    spatial = _spatial(event, twin)
    recurrence = _recurrence(event, twin)

    dims = [intensity, persistence, duration, temporal, spatial, recurrence]
    computed = [d for d in dims if d.status == DeviationStatus.COMPUTED]
    if computed:
        weight = sum((2 if d.is_significant else 1 if d.is_notable else 0) for d in computed)
        overall = round(min(100.0, weight / (2 * len(computed)) * 100), 1)
    else:
        overall = 0.0

    explanations = [d.explanation for d in dims if d.is_notable or d.is_significant]
    if not explanations:
        explanations = ["No dimension shows a notable deviation from the facility's established baseline."]

    return Deviation(
        event_id=event.event_id, facility_id=event.facility_id, baseline_confidence=twin.baseline_confidence,
        intensity=intensity, persistence=persistence, duration=duration, temporal=temporal,
        spatial=spatial, recurrence=recurrence, overall_deviation_score=overall, explanations=explanations,
    )
