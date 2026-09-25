"""Real facility CONTEXT for thermal events -- a spatial index over the bundled OSM + GPPD facility table.

Facility proximity is contextual evidence (spatial association), never causation. This module only answers
"which known facilities are near this point, and how far", with the source of each record.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from app.config import get_settings
from app.model.schemas import Facility

logger = logging.getLogger("orbiflare.context")
EARTH_RADIUS_KM = 6371.0088
INDIA_BBOX = (68.0, 6.0, 98.0, 37.0)                     # west, south, east, north
EXCLUDED_TYPES = frozenset({"Solar", "Wind", "Hydro"})   # no combustion heat source a VIIRS pixel could see
# --- Facility context QUALITY: derived only from the record's own type/name. HIGH = specific, heat-relevant, identified;
# MEDIUM = identifiable site but less specific metadata; LOW = generic land-use or ambiguous. Not a probability.
GENERIC_TYPES = frozenset({
    "industrial", "industrial area", "industrial_park", "yes", "temporary", "works", "transport", "depot", "bus_depot", "vehicle_depot", "warehouse",
    "storage", "cold_storage", "godown", "distributor", "logistics", "communication", "telecommunication", "railway", "port", "school", "hospital",
    "it", "digital_marketing_agency", "house_of_service", "construction", "construction_company", "grid_station", "substation", "utility", "water",
    "container_yard", "container_terminal", "intermodal_freight_terminal", "data_centre", "water_works", "water_treatment", "water_purification",
})
THERMAL_KEYWORDS = ("refiner", "oil", "gas", "coal", "power", "nuclear", "biomass", "geothermal", "cement", "steel", "smelt", "chemical", "petro",
                    "mine", "mining", "quarry", "kiln", "brick", "lime", "foundry", "casting", "aluminium", "metal", "fertili", "polymer", "asphalt",
                    "ash", "factory", "manufactur", "ceramic", "tile", "glass", "paper", "sugar")


def context_quality(facility_type: str | None, name: str | None, source: str | None = None) -> tuple[str, str]:
    """(HIGH|MEDIUM|LOW, reason). Uses ONLY information already in the facility record."""
    t = (facility_type or "").strip().lower().replace("_", " ")
    generic = t in {g.replace("_", " ") for g in GENERIC_TYPES}
    named = bool(name and str(name).strip() and not str(name).strip().lower().startswith("unnamed"))
    thermal = any(k in t for k in THERMAL_KEYWORDS)
    if generic or not t:
        return "LOW", "generic land-use / non-specific facility record"
    if thermal and named:
        return "HIGH", "specific heat-relevant facility type with an identified name"
    if thermal:
        return "MEDIUM", "specific heat-relevant type, but the record has no name"
    return "MEDIUM", "identifiable site type, but not clearly a heat-producing installation"


DISTANCE_NOTE = "OSM industrial areas are stored as a single point; distance is to that point, not to the area boundary."


class FacilityContextIndex:
    def __init__(self, df: pd.DataFrame | None = None):
        cols = ["facility_id", "lat", "lon", "facility_type", "source", "name", "country"]
        df = pd.DataFrame(columns=cols) if df is None else df
        w, s, e, n = INDIA_BBOX
        df = df[df["lat"].between(s, n) & df["lon"].between(w, e) & ~df["facility_type"].isin(EXCLUDED_TYPES)].reset_index(drop=True)
        self.df = df
        self._pos = {fid: i for i, fid in enumerate(df["facility_id"])}
        self.tree = BallTree(np.radians(df[["lat", "lon"]].to_numpy(dtype=float)), metric="haversine") if len(df) else None

    def __len__(self) -> int:
        return len(self.df)

    def _row(self, i: int, dist_km: float | None = None) -> dict:
        r = self.df.iloc[i]
        d = {"facility_id": str(r["facility_id"]), "name": str(r["name"]) if pd.notna(r["name"]) and str(r["name"]).strip() else f"Unnamed {r['facility_type']}",
             "facility_type": str(r["facility_type"]), "latitude": float(r["lat"]), "longitude": float(r["lon"]),
             "source": str(r["source"]), "country": str(r["country"]) if pd.notna(r["country"]) else None}
        q, why = context_quality(d["facility_type"], str(r["name"]) if pd.notna(r["name"]) else None, d["source"])
        d["context_quality"], d["context_quality_reason"] = q, why
        if dist_km is not None:
            d["distance_km"] = round(dist_km, 3)
        return d

    def near(self, lat: float, lon: float, radius_km: float, limit: int | None = None) -> list[dict]:
        """Facilities within radius_km, nearest first. Distances are great-circle (haversine)."""
        if self.tree is None:
            return []
        idx, dist = self.tree.query_radius(np.radians([[lat, lon]]), r=radius_km / EARTH_RADIUS_KM, return_distance=True, sort_results=True)
        rows = [self._row(int(i), float(d) * EARTH_RADIUS_KM) for i, d in zip(idx[0], dist[0])]
        return rows[:limit] if limit else rows

    def nearest(self, lat: float, lon: float, radius_km: float) -> dict | None:
        hits = self.near(lat, lon, radius_km, limit=1)
        return hits[0] if hits else None

    def facility(self, facility_id: str) -> Facility | None:
        i = self._pos.get(facility_id)
        if i is None:
            return None
        r = self._row(i)
        return Facility(facility_id=r["facility_id"], name=r["name"], facility_type=r["facility_type"], latitude=r["latitude"],
                        longitude=r["longitude"], source=r["source"], country=r["country"], is_demo=False)


@lru_cache
def get_index() -> FacilityContextIndex:
    path = Path(get_settings().facility_dataset_path)
    if not path.exists():
        logger.warning("Facility context dataset not found at %s -- events will have no facility context.", path)
        return FacilityContextIndex()
    idx = FacilityContextIndex(pd.read_parquet(path))
    logger.info("Facility context index ready: %d facilities (India bbox, thermal-relevant types)", len(idx))
    return idx
