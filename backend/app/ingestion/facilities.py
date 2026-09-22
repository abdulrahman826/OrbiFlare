"""Facility / industrial-site ingestion.

Normalizes facility datasets from OSM extracts, WRI Global Power Plant
Database exports, or any similarly-shaped point dataset into the internal
Facility schema. Real datasets are optional; app.ingestion.demo_fixtures
supplies a clearly labelled synthetic set so the app runs with zero external
data.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from app.model.schemas import Facility

_OSM_INDUSTRIAL_TAGS = {
    "man_made=works": "industrial_works",
    "landuse=industrial": "industrial_area",
    "industrial=refinery": "oil_refinery",
    "industrial=oil": "oil_refinery",
    "power=plant": "power_plant",
    "building=industrial": "industrial_building",
}


def load_facilities_from_geojson(path: str | Path) -> list[Facility]:
    """Load a GeoJSON FeatureCollection of Point features (OSM-extract shaped:
    properties may include name, industrial/man_made/power tags)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    facilities: list[Facility] = []
    for feature in data.get("features", []):
        geom = feature.get("geometry", {})
        if geom.get("type") != "Point":
            continue
        lon, lat = geom["coordinates"][0], geom["coordinates"][1]
        props = feature.get("properties", {})
        facility_type = _infer_facility_type(props)
        facilities.append(Facility(
            facility_id=str(props.get("id") or uuid.uuid4().hex[:12]),
            name=str(props.get("name") or f"Unnamed {facility_type}"),
            facility_type=facility_type,
            industry=props.get("industry"),
            latitude=float(lat), longitude=float(lon),
            source="OSM", country=props.get("country"), state=props.get("state"),
            region=props.get("region"), is_demo=False,
        ))
    return facilities


def load_facilities_from_wri_csv(rows: list[dict]) -> list[Facility]:
    """Normalize WRI Global Power Plant Database-shaped rows."""
    facilities = []
    for row in rows:
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
        except (KeyError, ValueError, TypeError):
            continue
        facilities.append(Facility(
            facility_id=str(row.get("gppd_idnr") or uuid.uuid4().hex[:12]),
            name=str(row.get("name") or "Unnamed Power Plant"),
            facility_type="power_plant",
            industry=row.get("primary_fuel"),
            latitude=lat, longitude=lon, source="WRI_GPPD",
            country=row.get("country"), is_demo=False,
        ))
    return facilities


def _infer_facility_type(props: dict) -> str:
    for key in ("industrial", "man_made", "power", "landuse", "building"):
        if key in props:
            tag = f"{key}={props[key]}"
            if tag in _OSM_INDUSTRIAL_TAGS:
                return _OSM_INDUSTRIAL_TAGS[tag]
    return "industrial_unclassified"
