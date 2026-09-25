"""Facility Thermal Twin -- OrbiFlare's central differentiator.

A Thermal Twin is a multidimensional, robust-statistics summary of what
"normal" thermal behaviour looks like for a facility, built ONLY from
observations/events that predate the event under investigation (never from
the event itself -- otherwise an anomaly would corrupt its own baseline).

Never fabricates history: if there isn't enough of it, baseline_confidence
is INSUFFICIENT and every downstream consumer must surface that explicitly
rather than silently computing a deviation against noise.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from statistics import median

import numpy as np

from app.config import get_settings
from app.intelligence.clustering import haversine_km
from app.model.schemas import (
    BaselineConfidence,
    DistributionSummary,
    ThermalEvent,
    ThermalObservation,
    ThermalTwin,
)

settings = get_settings()


def _distribution_summary(values: list[float]) -> DistributionSummary:
    if not values:
        return DistributionSummary(n=0)
    arr = np.array(values, dtype=float)
    med = float(np.median(arr))
    mad = float(np.median(np.abs(arr - med)))
    return DistributionSummary(
        n=len(arr), median=round(med, 3), mad=round(mad, 3),
        q25=round(float(np.percentile(arr, 25)), 3), q75=round(float(np.percentile(arr, 75)), 3),
        min=round(float(arr.min()), 3), max=round(float(arr.max()), 3),
    )


def _normalized_histogram(values: list[int], buckets: list[int]) -> dict[str, float]:
    if not values:
        return {}
    counts = Counter(values)
    total = len(values)
    return {str(b): round(counts.get(b, 0) / total, 4) for b in buckets if counts.get(b, 0) > 0}


def _baseline_confidence(n_events: int, n_observations: int) -> BaselineConfidence:
    if (n_events >= settings.baseline_min_events_established and
            n_observations >= settings.baseline_min_observations_established):
        return BaselineConfidence.ESTABLISHED
    if n_observations >= settings.baseline_min_observations_limited and n_events >= settings.baseline_min_events_limited:
        return BaselineConfidence.LIMITED
    return BaselineConfidence.INSUFFICIENT


def build_thermal_twin(
    facility_id: str,
    historical_events: list[ThermalEvent],
    observations_by_event: dict[str, list[ThermalObservation]],
) -> ThermalTwin:
    all_obs: list[ThermalObservation] = []
    for e in historical_events:
        all_obs.extend(observations_by_event.get(e.event_id, []))

    n_events = len(historical_events)
    n_obs = len(all_obs)
    confidence = _baseline_confidence(n_events, n_obs)

    frp_values = [e.peak_frp for e in historical_events if e.peak_frp is not None]
    bt_values = [e.mean_bt for e in historical_events if e.mean_bt is not None]
    persistence_values = [float(e.observation_count) for e in historical_events]
    duration_values = [e.duration_hours for e in historical_events]

    recurrence_days = None
    if n_events >= 2:
        starts = sorted(e.first_detected for e in historical_events)
        gaps = [(b - a).total_seconds() / 86400.0 for a, b in zip(starts, starts[1:])]
        if gaps:
            recurrence_days = round(median(gaps), 2)

    hours = [o.timestamp.hour for o in all_obs]
    months = [o.timestamp.month for o in all_obs]
    day_night_counts = Counter(o.day_night.value for o in all_obs if o.day_night is not None)
    dn_total = sum(day_night_counts.values())
    day_night_pattern = {k: round(v / dn_total, 4) for k, v in day_night_counts.items()} if dn_total else {}

    spatial_centroid_lat = spatial_centroid_lon = spatial_radius_km = None
    if historical_events:
        spatial_centroid_lat = float(np.mean([e.centroid_lat for e in historical_events]))
        spatial_centroid_lon = float(np.mean([e.centroid_lon for e in historical_events]))
        dists = [haversine_km(spatial_centroid_lat, spatial_centroid_lon, e.centroid_lat, e.centroid_lon) for e in historical_events]
        # Robust radius: 90th percentile distance rather than max, so a single
        # historical outlier doesn't blow out the "normal footprint".
        spatial_radius_km = round(float(np.percentile(dists, 90)) if len(dists) > 1 else (dists[0] if dists else 0.0), 3)

    is_demo = any(o.source.value == "DEMO" for o in all_obs) if all_obs else False

    return ThermalTwin(
        facility_id=facility_id,
        baseline_confidence=confidence,
        history_start=min((e.first_detected for e in historical_events), default=None),
        history_end=max((e.last_detected for e in historical_events), default=None),
        historical_event_count=n_events,
        historical_observation_count=n_obs,
        normal_frp=_distribution_summary(frp_values),
        normal_bt=_distribution_summary(bt_values),
        normal_persistence=_distribution_summary(persistence_values),
        normal_duration=_distribution_summary(duration_values),
        normal_recurrence_days=recurrence_days,
        normal_day_night_pattern=day_night_pattern,
        normal_hour_pattern=_normalized_histogram(hours, list(range(24))),
        normal_seasonal_pattern=_normalized_histogram(months, list(range(1, 13))),
        normal_spatial_centroid_lat=round(spatial_centroid_lat, 6) if spatial_centroid_lat is not None else None,
        normal_spatial_centroid_lon=round(spatial_centroid_lon, 6) if spatial_centroid_lon is not None else None,
        normal_spatial_radius_km=spatial_radius_km,
        is_demo=is_demo,
        computed_at=datetime.utcnow(),
    )
