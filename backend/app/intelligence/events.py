"""Thermal Event Engine.

Groups raw thermal observations into LIVING THERMAL EVENTS using
deterministic spatio-temporal chaining: two observations belong to the same
event if they are within `spatial_radius_km` AND `temporal_gap_hours` of
each other (single-linkage over both dimensions simultaneously). This is a
computational grouping only -- it is NOT a confirmation that a fire
occurred, and the resulting ThermalEvent objects are re-derivable from the
same observation set every time (deterministic connected components).
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from statistics import mean

from app.config import get_settings
from app.intelligence.clustering import haversine_km
from app.model.schemas import AlertState, ThermalEvent, ThermalObservation

settings = get_settings()


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def _deterministic_event_id(observation_ids: list[str]) -> str:
    key = "|".join(sorted(observation_ids))
    return "EVT-" + hashlib.sha1(key.encode()).hexdigest()[:10].upper()


def cluster_observations(
    observations: list[ThermalObservation],
    spatial_radius_km: float | None = None,
    temporal_gap_hours: float | None = None,
) -> list[list[ThermalObservation]]:
    """Deterministic spatio-temporal connected-components clustering.

    Sorted by time so the temporal-gap check can short-circuit; still a
    single-linkage chain over BOTH space and time, matching how real
    satellite hotspot streams get "smeared" across successive overpasses.
    """
    radius = spatial_radius_km if spatial_radius_km is not None else settings.event_spatial_radius_km
    gap_hours = temporal_gap_hours if temporal_gap_hours is not None else settings.event_temporal_gap_hours

    obs_sorted = sorted(observations, key=lambda o: o.timestamp)
    n = len(obs_sorted)
    uf = _UnionFind(n)

    for i in range(n):
        for j in range(i + 1, n):
            dt_hours = (obs_sorted[j].timestamp - obs_sorted[i].timestamp).total_seconds() / 3600.0
            if dt_hours > gap_hours:
                break  # sorted by time: no later j can be within gap either
            dist_km = haversine_km(obs_sorted[i].latitude, obs_sorted[i].longitude,
                                    obs_sorted[j].latitude, obs_sorted[j].longitude)
            if dist_km <= radius:
                uf.union(i, j)

    groups: dict[int, list[ThermalObservation]] = {}
    for i, obs in enumerate(obs_sorted):
        root = uf.find(i)
        groups.setdefault(root, []).append(obs)

    # Stable order: earliest first_detected first
    return sorted(groups.values(), key=lambda g: min(o.timestamp for o in g))


def build_event_from_group(group: list[ThermalObservation]) -> ThermalEvent:
    timestamps = [o.timestamp for o in group]
    first_detected, last_detected = min(timestamps), max(timestamps)
    duration_hours = max(0.0, (last_detected - first_detected).total_seconds() / 3600.0)

    frps = [o.frp for o in group if o.frp is not None]
    bts = [o.brightness_temperature for o in group if o.brightness_temperature is not None]

    centroid_lat = mean(o.latitude for o in group)
    centroid_lon = mean(o.longitude for o in group)
    footprint_radius_km = max(
        (haversine_km(centroid_lat, centroid_lon, o.latitude, o.longitude) for o in group),
        default=0.0,
    )

    obs_ids = [o.observation_id for o in group]
    is_demo = any(o.source.value == "DEMO" for o in group)

    return ThermalEvent(
        event_id=_deterministic_event_id(obs_ids),
        first_detected=first_detected,
        last_detected=last_detected,
        duration_hours=round(duration_hours, 3),
        observation_count=len(group),
        peak_frp=max(frps) if frps else None,
        mean_frp=round(mean(frps), 2) if frps else None,
        peak_bt=max(bts) if bts else None,
        mean_bt=round(mean(bts), 2) if bts else None,
        centroid_lat=round(centroid_lat, 6),
        centroid_lon=round(centroid_lon, 6),
        footprint_radius_km=round(footprint_radius_km, 3),
        status=AlertState.DETECTED,
        is_demo=is_demo,
        source_observation_ids=obs_ids,
    )


def form_events(observations: list[ThermalObservation]) -> list[ThermalEvent]:
    groups = cluster_observations(observations)
    return [build_event_from_group(g) for g in groups]
