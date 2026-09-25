"""API-level tests: provenance labelling, 404s, honest FIRMS-match behaviour, read-only agent tools, verified data mode."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.storage.database import Base, engine


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    from app.main import app
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


def test_incident_list_summary_and_detail(client):
    items = client.get("/api/reference/incidents").json()
    assert len(items) == 30
    assert all(i["provenance"]["status"] == "HISTORICAL" and not i["provenance"]["is_live_firms"] for i in items)
    assert len(client.get("/api/reference/incidents?state=Odisha").json()) == 4
    assert all(i["record_kind"] == "AGRICULTURAL_BURNING_REFERENCE" for i in client.get("/api/reference/incidents?kind=AGRICULTURAL_BURNING_REFERENCE").json())
    assert client.get("/api/reference/incidents/summary").json()["total"] == 30
    assert client.get("/api/reference/incidents/IND-004").json()["state"] == "Telangana"
    assert client.get("/api/reference/incidents/IND-999").status_code == 404
    assert client.get("/api/reference/incidents/IND-999/context").status_code == 404


def test_incident_context_never_fabricates_a_firms_match(client):
    ctx = client.get("/api/reference/incidents/IND-015/context").json()
    assert ctx["firms_match"]["status"] == "NO_FIRMS_MATCH"
    assert ctx["firms_match"]["matching_firms_observations"] == 0   # DB only holds DEMO observations
    assert ctx["admin"]["resolved"] and ctx["admin"]["state"] == "Gujarat"
    assert ctx["unknown"] and ctx["known"]
    # nearby demo objects stay labelled as demo
    assert all(e["is_demo"] for e in ctx["nearby_current_events"])
    assert all(f["is_demo"] for f in ctx["nearby_facilities"])


def test_near_endpoint_validates_and_sorts(client):
    hits = client.get("/api/reference/incidents/near?lat=22.39&lon=70.05&radius_km=100").json()
    assert hits and hits == sorted(hits, key=lambda h: h["distance_km"])
    assert client.get("/api/reference/incidents/near?lat=999&lon=70").status_code == 422


def test_admin_region_endpoints(client):
    fc = client.get("/api/reference/admin-regions?level=state").json()
    assert len(fc["features"]) == 36 and fc["provenance"]["data_mode"] == "GEOGRAPHIC_REFERENCE"
    assert client.get("/api/reference/admin-regions?level=bogus").status_code == 422
    assert client.get("/api/reference/admin-regions/summary").json()["districts"] == 760
    assert client.get("/api/reference/admin-regions/resolve?lat=22.39&lon=70.05").json()["state"] == "Gujarat"
    assert client.get("/api/reference/admin-regions/resolve?lat=0&lon=0").json()["resolved"] is False


def test_reports_keep_historical_and_current_separate(client):
    rep = client.post("/api/reports/historical-incident/IND-003").json()
    assert rep["report_type"] == "HISTORICAL_REFERENCE_INCIDENT"
    assert "NOT A LIVE FIRMS DETECTION" in rep["data_label"]
    assert rep["firms_match_check"]["status"] == "NO_FIRMS_MATCH"
    assert client.post("/api/reports/historical-incident/NOPE").status_code == 404
    ev = client.get("/api/events").json()[0]["event_id"]
    er = client.post(f"/api/reports/event/{ev}").json()
    assert er["historical_reference_context"]["label"].startswith("HISTORICAL REFERENCE CONTEXT")
    assert er["data_label"] == "DEMO"


def test_health_data_mode_is_verified_not_assumed(client):
    h = client.get("/api/health").json()
    assert h["data_mode"] == "DEMO" and h["live_firms_observations"] == 0 and h["demo_observations"] > 0


def test_analytics_admin_state_never_forces_unknown_geography(client):
    a = client.get("/api/analytics/events").json()
    assert sum(a["by_admin_state"].values()) == len(client.get("/api/events").json())


# ---- deterministic agent: read-only, honest ----

def test_agent_historical_tools_are_read_only_and_labelled(client):
    before = client.get("/api/events").json()
    r = client.post("/api/agent/query", json={"message": "list historical incidents in Gujarat"}).json()
    assert "not FIRMS detections" in r["text"] and r["result_cards"] and all(c["type"] == "incident" for c in r["result_cards"])
    r2 = client.post("/api/agent/query", json={"message": "show incident IND-004"}).json()
    assert r2["ui_action"]["action"] == "open_incident" and "HISTORICAL" in r2["text"]
    ev = before[0]["event_id"]
    r3 = client.post("/api/agent/query", json={"message": f"incidents near {ev}"}).json()
    assert "not causation" in r3["text"] or "No historical" in r3["text"]
    r4 = client.post("/api/agent/query", json={"message": "extinguish " + ev}).json()
    assert client.get("/api/events").json() == before                     # nothing mutated
    assert client.get(f"/api/events/{ev}").json()["status"] == before[0]["status"]
    assert r4["tool_calls"] and all(t["tool"] != "transition" for t in r4["tool_calls"])


def test_lifecycle_and_unknown_id_status_codes(client):
    ev = client.get("/api/events").json()[0]["event_id"]
    assert client.post(f"/api/events/{ev}/transition", json={"to_state": "ESCALATED", "actor": "op"}).status_code == 409
    assert client.post("/api/events/NOPE/transition", json={"to_state": "VALIDATING", "actor": "op"}).status_code == 404
    assert client.get("/api/events/NOPE").status_code == 404
    assert client.get("/api/facilities/NOPE").status_code == 404


PROHIBITED = ("siddiquezain", "zero1", "6059958", "udit-001", "confirmed_incidents_india", "india_admin", "reference_repository", "Imported from")


def test_exported_report_and_agent_responses_carry_no_repository_provenance(client):
    import json
    rep = client.post("/api/reports/historical-incident/IND-003").json()
    assert rep["incident"]["provenance"]["status_label"].startswith("Historical reference")
    assert rep["incident"]["provenance"]["source_label"]                      # legitimate per-record source label is kept
    blob = json.dumps(rep)
    for q in ("list historical incidents in Gujarat", "show incident IND-004", "historical incidents near FAC-REF-ALPHA"):
        blob += json.dumps(client.post("/api/agent/query", json={"message": q}).json())
    ev = client.get("/api/events").json()[0]["event_id"]
    blob += json.dumps(client.post(f"/api/reports/event/{ev}").json())
    for bad in PROHIBITED:
        assert bad not in blob, bad


def test_ui_facing_boundary_note_is_neutral_but_origin_stays_internal(client):
    fc = client.get("/api/reference/admin-regions?level=state").json()["provenance"]
    assert "zero1" not in fc["note"] and "siddiquezain" not in fc["note"] and "udit-001" not in fc["note"]
    assert "zero1" in fc["origin"]                                            # traceability metadata is preserved
    raw = client.get("/api/reference/incidents/IND-003").json()
    assert raw["provenance"]["reference_repository"]                           # stored provenance untouched
