"""Ingestion, schema, provenance and geometry tests for the imported REFERENCE data."""
from __future__ import annotations

import csv
import tempfile
from pathlib import Path

import pytest

from app.reference import admin, incidents


def test_loads_all_thirty_incidents_with_unique_ids():
    items = incidents.incidents()
    assert len(items) == 30
    assert len({i.incident_id for i in items}) == 30


def test_every_incident_is_marked_historical_never_live_demo_or_training():
    for i in incidents.incidents():
        p = i.provenance
        assert p.data_mode == "HISTORICAL_REFERENCE" and p.status == "HISTORICAL"
        assert p.is_live_firms is False and p.is_demo is False and p.used_for_ml_training is False
        assert p.per_record_verification == "NOT_VERIFIED_BY_ORBIFLARE"
        assert i.coordinate_precision == "APPROXIMATE"
        assert any("NOT a FIRMS detection" in c for c in i.caveats)
        assert p.source_label  # per-record source preserved verbatim


def test_record_kinds_do_not_call_everything_a_fire():
    by_id = {i.incident_id: i for i in incidents.incidents()}
    assert by_id["IND-002"].record_kind == "MEMORIAL_SITE_REFERENCE"          # commemoration site, date is an anniversary
    assert by_id["IND-009"].record_kind == "AGRICULTURAL_BURNING_REFERENCE"   # stubble burning, not industrial
    assert by_id["IND-012"].record_kind == "PERSISTENT_THERMAL_SOURCE_REFERENCE"  # chronic coal fire
    assert by_id["IND-015"].record_kind == "PERSISTENT_THERMAL_SOURCE_REFERENCE"  # routine flare
    assert by_id["IND-003"].record_kind == "REPORTED_INDUSTRIAL_INCIDENT"     # refinery fire
    kinds = {i.record_kind for i in by_id.values()}
    assert len(kinds) == 4


def test_duplicate_coordinates_are_flagged():
    by_id = {i.incident_id: i for i in incidents.incidents()}
    assert any("IND-017" in n for n in by_id["IND-001"].coordinate_notes)
    assert any("IND-001" in n for n in by_id["IND-017"].coordinate_notes)


def test_filters_and_lookup():
    assert {i.state for i in incidents.list_incidents(state="gujarat")} == {"Gujarat"}
    assert incidents.get_incident("ind-004").name.startswith("Sigachi")
    assert incidents.get_incident("IND-999") is None
    s = incidents.summary()
    assert s["total"] == 30 and s["provenance"]["is_live_firms"] is False and "0 of 30" in s["provenance"]["firms_match_note"]


def _write(rows, header=("incident_id", "name", "date", "lat", "lon", "state", "facility_type", "description", "source")):
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8", newline="")
    w = csv.writer(f)
    w.writerow(header)
    w.writerows(rows)
    f.close()
    return Path(f.name)


def test_loader_rejects_bad_rows_loudly():
    good = ["IND-1", "n", "2021-01-01", "20.0", "80.0", "S", "Refinery", "Fire at X", "News"]
    assert len(incidents.load_incidents(_write([good]))) == 1
    with pytest.raises(ValueError):
        incidents.load_incidents(_write([["IND-1", "n", "2021-13-40", "20.0", "80.0", "S", "R", "Fire", "N"]]))  # bad date
    with pytest.raises(ValueError):
        incidents.load_incidents(_write([["IND-1", "n", "2021-01-01", "51.0", "80.0", "S", "R", "Fire", "N"]]))  # outside India bounds
    with pytest.raises(ValueError):
        incidents.load_incidents(_write([["IND-1", "n", "2021-01-01", "20.0", "80.0", "S", "R", "", "N"]]))  # missing description
    with pytest.raises(ValueError):
        incidents.load_incidents(_write([good, good]))  # duplicate id


# ---- admin geometry ----

def test_admin_geometry_is_the_real_36_states_and_760_districts():
    s = admin.summary()
    assert s["states"] == 36 and s["districts"] == 760
    fc = admin.feature_collection("state")
    assert len(fc["features"]) == 36
    assert fc["provenance"]["data_mode"] == "GEOGRAPHIC_REFERENCE"
    assert all(f["geometry"]["type"] in ("Polygon", "MultiPolygon") for f in fc["features"])
    assert len(admin.feature_collection("district")["features"]) == 760
    assert {f["properties"]["state"] for f in admin.feature_collection("district", state="Gujarat")["features"]} == {"Gujarat"}
    with pytest.raises(ValueError):
        admin.feature_collection("village")


def test_point_in_polygon_resolution():
    assert admin.resolve(22.39, 70.05).state == "Gujarat"          # Jamnagar
    assert admin.resolve(22.39, 70.05).district == "Jamnagar"
    assert admin.resolve(23.7957, 86.4304).state == "Jharkhand"    # Dhanbad
    out = admin.resolve(51.5, -0.12)                               # London -- must NOT be forced into a region
    assert out.resolved is False and out.state is None
