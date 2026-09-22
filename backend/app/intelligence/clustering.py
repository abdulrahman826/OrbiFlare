"""Spatial primitives shared across the intelligence layer: haversine
distance and a BallTree-backed nearest-neighbour index (used for
facility-proximity lookups over potentially large facility sets).
"""
from __future__ import annotations

import math

import numpy as np
from sklearn.neighbors import BallTree

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


class FacilitySpatialIndex:
    """BallTree over facility coordinates (haversine metric, radians)."""

    def __init__(self, facility_ids: list[str], lats: list[float], lons: list[float]):
        self.facility_ids = facility_ids
        if facility_ids:
            coords_rad = np.radians(np.column_stack([lats, lons]))
            self.tree = BallTree(coords_rad, metric="haversine")
        else:
            self.tree = None

    def nearest(self, lat: float, lon: float) -> tuple[str | None, float | None]:
        if self.tree is None:
            return None, None
        point = np.radians([[lat, lon]])
        dist_rad, idx = self.tree.query(point, k=1)
        dist_km = float(dist_rad[0][0]) * EARTH_RADIUS_KM
        facility_id = self.facility_ids[int(idx[0][0])]
        return facility_id, dist_km
