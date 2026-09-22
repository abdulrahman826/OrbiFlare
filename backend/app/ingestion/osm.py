"""OpenStreetMap context adapter (industrial land-use, admin boundaries).

Live Overpass queries are supported but opt-in (`fetch_live=True`) since
outbound network access is not guaranteed in every deployment/demo
environment. Without it, callers get an explicit UNAVAILABLE result rather
than a silent empty success -- the frontend must render this as
"GIS CONTEXT UNAVAILABLE", never as "no industrial context exists".
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


@dataclass
class OSMContextResult:
    available: bool
    features: list[dict]
    reason: str | None = None


def fetch_industrial_landuse(bbox: tuple[float, float, float, float], fetch_live: bool = False) -> OSMContextResult:
    """bbox = (south, west, north, east). Returns industrial landuse polygons
    near the bbox, or an explicit UNAVAILABLE result."""
    if not fetch_live:
        return OSMContextResult(available=False, features=[], reason="Live OSM fetch disabled (fetch_live=False)")
    south, west, north, east = bbox
    query = f"""
    [out:json][timeout:15];
    (
      way["landuse"="industrial"]({south},{west},{north},{east});
      way["man_made"="works"]({south},{west},{north},{east});
    );
    out geom;
    """
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(OVERPASS_URL, data={"data": query})
            resp.raise_for_status()
        elements = resp.json().get("elements", [])
        return OSMContextResult(available=True, features=elements)
    except Exception as exc:  # network/API failure -> explicit unavailable, not a crash
        return OSMContextResult(available=False, features=[], reason=f"OSM fetch failed: {exc}")
