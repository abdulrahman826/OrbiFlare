"""Ingestion + normalisation of the historical incident reference CSV.

Strict validation: every row must have a parseable date and in-range coordinates or the whole load fails loudly
(reference data is small and curated; silently dropping rows would hide problems).
"""
from __future__ import annotations

import csv
from datetime import date
from functools import lru_cache
from pathlib import Path

from app.config import REPO_ROOT
from app.reference.schemas import (
    RECORD_KIND_LABEL, HistoricalIncident, IncidentProvenance,
)

INCIDENTS_CSV = REPO_ROOT / "data" / "reference" / "incidents" / "confirmed_incidents_india.csv"
REQUIRED = ("incident_id", "name", "date", "lat", "lon", "state", "facility_type", "description", "source")

# India bounding box used for sanity validation only (not a boundary).
_LAT = (6.0, 37.5)
_LON = (68.0, 98.5)

_PERSISTENT_WORDS = ("persistent", "routine", "chronic", "thermal signature", "thermal anomaly", "thermal source")
_INCIDENT_WORDS = ("fire", "explosion", "leak", "blast", "tragedy")


def classify_record(name: str, facility_type: str, description: str) -> str:
    """Deterministic, keyword-based record kind. Conservative: a row is only called a
    REPORTED_INDUSTRIAL_INCIDENT if its own text describes a fire/explosion/leak."""
    n, f, d = name.lower(), facility_type.lower(), description.lower()
    if "commemoration" in n or "anniversary" in d:
        return "MEMORIAL_SITE_REFERENCE"
    if f == "agricultural" or "stubble" in n:
        return "AGRICULTURAL_BURNING_REFERENCE"
    if any(w in d or w in n for w in _PERSISTENT_WORDS):
        return "PERSISTENT_THERMAL_SOURCE_REFERENCE"
    if any(w in d for w in _INCIDENT_WORDS):
        return "REPORTED_INDUSTRIAL_INCIDENT"
    if "flare" in d or "flare" in n:
        return "PERSISTENT_THERMAL_SOURCE_REFERENCE"
    return "REPORTED_INDUSTRIAL_INCIDENT"


_KIND_CAVEAT = {
    "REPORTED_INDUSTRIAL_INCIDENT": "Reported by the listed source; OrbiFlare has not independently verified this record or its exact location.",
    "PERSISTENT_THERMAL_SOURCE_REFERENCE": "A reference to a routine/persistent thermal source (e.g. flare, kiln, smelter, chronic coal fire) -- NOT a discrete fire incident.",
    "AGRICULTURAL_BURNING_REFERENCE": "A seasonal agricultural-burning reference point -- NOT an industrial incident.",
    "MEMORIAL_SITE_REFERENCE": "A memorial/anniversary reference to a historical site -- the date is not an incident date.",
}


def _parse_row(row: dict, dup_coords: dict[tuple[float, float], list[str]]) -> HistoricalIncident:
    missing = [k for k in REQUIRED if not (row.get(k) or "").strip()]
    if missing:
        raise ValueError(f"{row.get('incident_id', '?')}: missing fields {missing}")
    lat, lon = float(row["lat"]), float(row["lon"])
    if not (_LAT[0] <= lat <= _LAT[1] and _LON[0] <= lon <= _LON[1]):
        raise ValueError(f"{row['incident_id']}: coordinates ({lat}, {lon}) outside India sanity bounds")
    date.fromisoformat(row["date"])  # raises on bad dates
    kind = classify_record(row["name"], row["facility_type"], row["description"])
    notes = ["Coordinates are approximate (site/city level), not surveyed."]
    twins = [i for i in dup_coords[(lat, lon)] if i != row["incident_id"]]
    if twins:
        notes.append(f"Shares identical coordinates with {', '.join(twins)}.")
    return HistoricalIncident(
        incident_id=row["incident_id"].strip(), name=row["name"].strip(), date=row["date"].strip(),
        latitude=lat, longitude=lon, state=row["state"].strip(), facility_type=row["facility_type"].strip(),
        description=row["description"].strip(), record_kind=kind, record_kind_label=RECORD_KIND_LABEL[kind],
        coordinate_notes=notes,
        provenance=IncidentProvenance(source_label=row["source"].strip()),
        caveats=[
            _KIND_CAVEAT[kind],
            "Historical reference record -- NOT a FIRMS detection, NOT a live alert, and not used to train the ML model.",
        ],
    )


def load_incidents(path: Path = INCIDENTS_CSV) -> list[HistoricalIncident]:
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    dup: dict[tuple[float, float], list[str]] = {}
    for r in rows:
        dup.setdefault((float(r["lat"]), float(r["lon"])), []).append(r["incident_id"])
    seen: set[str] = set()
    out: list[HistoricalIncident] = []
    for r in rows:
        inc = _parse_row(r, dup)
        if inc.incident_id in seen:
            raise ValueError(f"duplicate incident_id {inc.incident_id}")
        seen.add(inc.incident_id)
        out.append(inc)
    return out


@lru_cache
def incidents() -> tuple[HistoricalIncident, ...]:
    return tuple(load_incidents())


def get_incident(incident_id: str) -> HistoricalIncident | None:
    return next((i for i in incidents() if i.incident_id.upper() == incident_id.upper()), None)


def list_incidents(state: str | None = None, kind: str | None = None) -> list[HistoricalIncident]:
    return [i for i in incidents()
            if (not state or i.state.lower() == state.lower()) and (not kind or i.record_kind == kind)]


def summary() -> dict:
    items = incidents()
    by_kind: dict[str, int] = {}
    by_state: dict[str, int] = {}
    for i in items:
        by_kind[i.record_kind] = by_kind.get(i.record_kind, 0) + 1
        by_state[i.state] = by_state.get(i.state, 0) + 1
    dates = sorted(i.date for i in items)
    return {
        "total": len(items), "by_record_kind": by_kind, "by_state": dict(sorted(by_state.items(), key=lambda kv: -kv[1])),
        "date_range": [dates[0], dates[-1]] if dates else None,
        "provenance": {
            "source_dataset": "confirmed_incidents_india.csv", "data_mode": "HISTORICAL_REFERENCE", "status": "HISTORICAL",
            "is_live_firms": False, "used_for_ml_training": False,
            "firms_match_note": "The originating prototype's own matching run (1 km / 1 day) matched 0 of 30 incidents to FIRMS detections; OrbiFlare does not assert any FIRMS match.",
        },
    }
