"""India administrative boundaries (real geometry) -- loading, serving and point-in-polygon lookup."""
from __future__ import annotations

import json
from functools import lru_cache

from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from app.config import REPO_ROOT
from app.reference.schemas import AdminResolution

ADMIN_GEOJSON = REPO_ROOT / "data" / "reference" / "geo" / "india_admin.geojson"
SOURCE_NOTE = "Administrative boundary geometry, simplified (~1.3 km). For orientation and lookup only; not a survey-grade or official boundary product."
# Internal traceability only -- never rendered in the UI or exported documents.
ORIGIN = "udit-001/india-maps-data via siddiquezain/zero1"


@lru_cache
def _raw() -> dict:
    with open(ADMIN_GEOJSON, encoding="utf-8") as fh:
        return json.load(fh)


class _Index:
    def __init__(self, level: str):
        self.feats = [f for f in _raw()["features"] if f["properties"].get("kind") == level]
        self.geoms = [shape(f["geometry"]) for f in self.feats]
        self.tree = STRtree(self.geoms)

    def find(self, lat: float, lon: float) -> dict | None:
        pt = Point(lon, lat)
        for idx in self.tree.query(pt):
            if self.geoms[int(idx)].covers(pt):
                return self.feats[int(idx)]["properties"]
        return None


@lru_cache
def _index(level: str) -> _Index:
    return _Index(level)


def resolve(lat: float, lon: float) -> AdminResolution:
    state = _index("state").find(lat, lon)
    district = _index("district").find(lat, lon)
    if state is None and district is None:
        return AdminResolution(resolved=False)
    return AdminResolution(
        state=(state or district or {}).get("state"), district=(district or {}).get("district"), resolved=True,
    )


def feature_collection(level: str = "state", state: str | None = None) -> dict:
    if level not in ("state", "district"):
        raise ValueError("level must be 'state' or 'district'")
    feats = [f for f in _raw()["features"] if f["properties"].get("kind") == level
             and (not state or f["properties"].get("state", "").lower() == state.lower())]
    return {
        "type": "FeatureCollection", "features": feats,
        "provenance": {"dataset": "india_admin.geojson", "origin": ORIGIN, "level": level, "data_mode": "GEOGRAPHIC_REFERENCE",
                       "note": SOURCE_NOTE, "feature_count": len(feats)},
    }


def summary() -> dict:
    feats = _raw()["features"]
    states = sorted({f["properties"]["state"] for f in feats if f["properties"]["kind"] == "state"})
    return {
        "states": len(states), "districts": sum(1 for f in feats if f["properties"]["kind"] == "district"),
        "state_names": states, "note": SOURCE_NOTE,
    }
