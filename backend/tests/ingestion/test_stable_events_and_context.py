"""Stable event identity, real facility context, and baseline honesty for LIVE FIRMS data. No network."""
from __future__ import annotations

import math
from datetime import datetime, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.context import facilities as facility_ctx
from app.ingestion import firms_refresh
from app.intelligence.thermal_twin import build_thermal_twin
from app.model.schemas import BaselineConfidence, DataSource, Sensor, ThermalEvent, ThermalObservation
from app.storage.database import Base, engine

HEADER = "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight"


def row(lat, lon, hhmm, frp=5.0, sat="N21", conf="n", date="2026-09-24"):
    return f"{lat:.5f},{lon:.5f},335.0,0.40,0.40,{date},{hhmm},{sat},VIIRS,{conf},2.0NRT,290.0,{frp},D"


def csv_of(*rows):
    return "\n".join([HEADER, *rows]) + "\n"


def hav(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def small_index(rows):
    return facility_ctx.FacilityContextIndex(pd.DataFrame(rows, columns=["facility_id", "lat", "lon", "facility_type", "source", "name", "country"]))


# --------------------------------------------------------------------------- facility index (pure)

def test_index_returns_real_distances_sorted_with_provenance_and_excludes_non_thermal_types():
    idx = small_index([
        ("OSM-1", 22.3300, 69.8600, "refinery", "OSM", "Refinery A", "IND"),
        ("OSM-2", 22.3400, 69.8600, "industrial", "OSM", "Zone B", "IND"),
        ("GPPD-3", 22.3305, 69.8601, "Solar", "GPPD", "Solar farm", "IND"),      # excluded: no combustion heat
        ("OSM-4", 25.0000, 75.0000, "brickyard", "OSM", "Far", "IND"),
        ("OSM-5", 60.0, 10.0, "industrial", "OSM", "Outside India bbox", "NOR"),
    ])
    assert len(idx) == 3 and idx.facility("GPPD-3") is None and idx.facility("OSM-5") is None
    hits = idx.near(22.3302, 69.8602, 3.0)
    assert [h["facility_id"] for h in hits] == ["OSM-1", "OSM-2"]
    assert hits[0]["distance_km"] == pytest.approx(hav(22.3302, 69.8602, 22.3300, 69.8600), abs=0.002)
    assert hits[1]["distance_km"] == pytest.approx(hav(22.3302, 69.8602, 22.3400, 69.8600), abs=0.002)
    assert all(h["source"] == "OSM" and h["facility_type"] and h["latitude"] and h["longitude"] for h in hits)
    assert idx.nearest(22.3302, 69.8602, 0.001) is None                       # outside the radius -> no context, nothing invented
    assert idx.near(0.0, 0.0, 3.0) == []


def test_empty_index_gives_no_context():
    assert facility_ctx.FacilityContextIndex().nearest(20, 80, 3) is None


def test_bundled_dataset_is_real_and_loadable():
    idx = facility_ctx.get_index()
    assert len(idx) > 30000 and idx.facility("OSM-91585872").name == "Reliance Refinery"
    ref = idx.nearest(22.3368, 69.8666, 0.5)
    assert ref["facility_id"] == "OSM-91585872" and ref["source"] == "OSM"


# --------------------------------------------------------------------------- baseline honesty (pure)

def _hist(i, day, n_obs=3, src=DataSource.FIRMS):
    ts = datetime(2026, 9, 1, 8) + timedelta(days=day)
    obs = [ThermalObservation(observation_id=f"E{i}-{k}", timestamp=ts + timedelta(minutes=k), latitude=22.3, longitude=69.8, sensor=Sensor.VIIRS,
                              frp=5.0 + i, brightness_temperature=330.0, source=src, day_night="D") for k in range(n_obs)]
    ev = ThermalEvent(event_id=f"H{i}", first_detected=ts, last_detected=ts + timedelta(minutes=n_obs), duration_hours=0.05, observation_count=n_obs,
                      peak_frp=5.0 + i, mean_frp=5.0 + i, peak_bt=330.0, mean_bt=330.0, centroid_lat=22.3, centroid_lon=69.8,
                      source_observation_ids=[o.observation_id for o in obs], is_demo=False)
    return ev, obs


def _twin(n_events, n_obs=3):
    pairs = [_hist(i, i * 2, n_obs) for i in range(n_events)]
    return build_thermal_twin("F", [e for e, _ in pairs], {e.event_id: o for e, o in pairs})


def test_baseline_needs_more_than_one_historical_event_and_is_established_only_with_enough_real_history():
    assert _twin(0).baseline_confidence == BaselineConfidence.INSUFFICIENT
    assert _twin(1, n_obs=6).baseline_confidence == BaselineConfidence.INSUFFICIENT      # one event = no notion of "normal variability"
    assert _twin(2).baseline_confidence == BaselineConfidence.LIMITED
    assert _twin(3, n_obs=2).baseline_confidence == BaselineConfidence.LIMITED
    assert _twin(4, n_obs=1).baseline_confidence == BaselineConfidence.LIMITED           # 4 events but only 4 obs (<8): not established
    assert _twin(4, n_obs=2).baseline_confidence == BaselineConfidence.ESTABLISHED
    t = _twin(5)
    assert t.baseline_confidence == BaselineConfidence.ESTABLISHED and t.is_demo is False and t.normal_frp.n == 5


# --------------------------------------------------------------------------- live pipeline

@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    from app.main import app
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def feed(monkeypatch):
    """Controls what 'NASA' returns and which facilities exist. Default: no facilities."""
    state = {"csv": csv_of(), "index": facility_ctx.FacilityContextIndex()}
    monkeypatch.setattr(firms_refresh, "fetch_firms_sources", lambda: [("VIIRS_NOAA21_NRT", state["csv"])])
    monkeypatch.setattr(facility_ctx, "get_index", lambda: state["index"])
    return state


def events(client):
    return {e["event_id"]: e for e in client.get("/api/events").json()}


A = [row(21.1000, 72.6000, "0600"), row(21.1010, 72.6010, "0600"), row(21.1005, 72.6005, "0745")]     # one event (A)
B = [row(26.2000, 80.1000, "0610")]                                                                     # an unrelated single detection


def test_round1_creates_events(client, feed):
    feed["csv"] = csv_of(*A, *B)
    s = client.post("/api/firms/refresh").json()
    assert s["status"] == "OK" and s["events_total"] == 2 and s["events_created"] == 2
    ev = events(client)
    a = next(e for e in ev.values() if e["observation_count"] == 3)
    test_round1_creates_events.a_id = a["event_id"]
    test_round1_creates_events.b_id = next(k for k in ev if k != a["event_id"])
    test_round1_creates_events.a_risk = a["risk_score"]
    assert all(e["is_live_firms"] and not e["is_demo"] for e in ev.values())


def test_operator_actions_before_the_event_evolves(client):
    a = test_round1_creates_events.a_id
    assert client.post(f"/api/events/{a}/transition", json={"to_state": "VALIDATING", "actor": "analyst1", "note": "checking imagery"}).status_code == 200
    hist = client.get(f"/api/alerts/{a}/history").json()
    assert hist and hist[-1]["to_state"] == "VALIDATING" and hist[-1]["actor"] == "analyst1"


def test_new_compatible_observation_extends_the_event_and_keeps_its_identity(client, feed):
    a, b = test_round1_creates_events.a_id, test_round1_creates_events.b_id
    extra = row(21.1002, 72.6008, "1930", frp=12.0)                    # same place, 11h45m after the 07:45 observation -> within the 12 h continuity gap
    feed["csv"] = csv_of(*A, *B, extra)
    s = client.post("/api/firms/refresh").json()
    assert s["events_created"] == 0 and s["events_updated"] == 1 and s["events_unchanged"] == 1 and s["events_total"] == 2
    ev = events(client)
    assert set(ev) == {a, b}                                           # SAME ids: nothing new, nothing lost
    assert ev[a]["observation_count"] == 4 and ev[a]["peak_frp"] == 12.0
    assert ev[a]["duration_hours"] > 12                                # metrics recalculated from the real observations
    # risk was recalculated (persistence + duration are inputs) and the trajectory was extended
    assert ev[a]["risk_score"] > test_round1_creates_events.a_risk
    traj = client.get(f"/api/events/{a}/trajectory").json()
    assert len(traj["points"]) == 4


def test_operator_state_and_audit_history_survive_the_update(client):
    a = test_round1_creates_events.a_id
    assert client.get(f"/api/events/{a}").json()["status"] == "VALIDATING"
    hist = client.get(f"/api/alerts/{a}/history").json()
    assert any(h["actor"] == "analyst1" and h["to_state"] == "VALIDATING" and h["note"] == "checking imagery" for h in hist)


def test_unrelated_observation_creates_a_new_event_and_disturbs_nothing(client, feed):
    a, b = test_round1_creates_events.a_id, test_round1_creates_events.b_id
    far = row(15.0000, 78.0000, "0700")
    feed["csv"] = csv_of(*A, *B, row(21.1002, 72.6008, "1930", frp=12.0), far)
    s = client.post("/api/firms/refresh").json()
    assert s["events_created"] == 1 and s["events_updated"] == 0 and s["events_unchanged"] == 2
    ev = events(client)
    assert a in ev and b in ev and len(ev) == 3
    new = next(e for k, e in ev.items() if k not in (a, b))
    assert new["observation_count"] == 1 and abs(new["centroid_lat"] - 15.0) < 0.01
    assert client.get(f"/api/events/{a}").json()["status"] == "VALIDATING"


def test_second_identical_refresh_changes_nothing(client, feed):
    feed["csv"] = csv_of(*A, *B, row(21.1002, 72.6008, "1930", frp=12.0), row(15.0, 78.0, "0700"))
    before = events(client)
    s = client.post("/api/firms/refresh").json()
    assert s["new_observations"] == 0 and s["events_created"] == 0 and s["events_updated"] == 0 and s["events_unchanged"] == 3
    assert events(client).keys() == before.keys()


def test_merging_events_keeps_the_older_identity_records_the_reason_and_keeps_human_decisions(client, feed):
    ev = events(client)
    a, b = test_round1_creates_events.a_id, test_round1_creates_events.b_id
    # two events near each other: A (already VALIDATING) and a new one C ~4 km away; a bridging chain of detections then joins them
    c_rows = [row(21.1400, 72.6000, "0630")]
    feed["csv"] = csv_of(*A, *B, row(21.1002, 72.6008, "1930", frp=12.0), row(15.0, 78.0, "0700"), *c_rows)
    client.post("/api/firms/refresh")
    c = next(k for k, e in events(client).items() if abs(e["centroid_lat"] - 21.14) < 0.01)
    assert client.post(f"/api/events/{c}/transition", json={"to_state": "VALIDATING", "actor": "analyst2"}).status_code == 200
    bridge = [row(21.1100, 72.6000, "0700"), row(21.1200, 72.6000, "0700"), row(21.1300, 72.6000, "0700")]      # ~1.1 km steps: chains A..C
    feed["csv"] = csv_of(*A, *B, row(21.1002, 72.6008, "1930", frp=12.0), row(15.0, 78.0, "0700"), *c_rows, *bridge)
    s = client.post("/api/firms/refresh").json()
    assert s["events_merged"] >= 1
    after = events(client)
    survivor = a if a in after else c
    gone = c if survivor == a else a
    assert gone not in after and survivor in after                       # exactly one identity survives
    assert after[survivor]["observation_count"] >= 8
    hist = client.get(f"/api/alerts/{survivor}/history").json()
    assert any("merged into this event" in (h["note"] or "") for h in hist)               # the reason is recorded
    assert client.get(f"/api/events/{survivor}").json()["status"] == "VALIDATING"          # human decisions survive the merge
    assert any(h["actor"] in ("analyst1", "analyst2") for h in hist)                      # audit history of the absorbed event is preserved
    assert client.get(f"/api/events/{gone}").status_code == 404


# --------------------------------------------------------------------------- facility context on live events

def test_live_event_gets_real_facility_context_persisted_only_for_referenced_facilities(client, feed):
    target = row(19.3000, 85.3000, "1000")
    idx = small_index([
        ("OSM-77", 19.3010, 85.3010, "refinery", "OSM", "Test Refinery", "IND"),
        ("OSM-78", 19.3200, 85.3000, "industrial", "OSM", "Zone Z", "IND"),
        ("OSM-99", 10.0, 70.0, "factory", "OSM", "Unrelated", "IND"),
    ])
    feed["index"] = idx
    feed["csv"] = csv_of(target)
    client.post("/api/firms/refresh")
    ev = next(e for e in events(client).values() if abs(e["centroid_lat"] - 19.3) < 0.01)
    assert ev["facility_id"] == "OSM-77"
    assert ev["facility_distance_km"] == pytest.approx(hav(19.3000, 85.3000, 19.3010, 85.3010), abs=0.01)
    fac_ids = {f["facility_id"] for f in client.get("/api/facilities").json()}
    assert "OSM-77" in fac_ids and "OSM-99" not in fac_ids                # only referenced facilities are stored, not the whole dataset

    ctx = client.get(f"/api/context/events/{ev['event_id']}").json()
    assert ctx["nearest"]["name"] == "Test Refinery" and ctx["nearest"]["source"] == "OSM" and ctx["nearest"]["facility_type"] == "refinery"
    assert ctx["nearby_count"] == 2 and [n["facility_id"] for n in ctx["nearby"]] == ["OSM-77", "OSM-78"]
    assert "spatial association" in ctx["statement"] and "Nearby does not mean caused by" in ctx["note"]
    for banned in ("caused", "fire at", "belongs to"):
        assert banned not in ctx["statement"].lower()


def test_no_facility_context_is_stated_without_implying_a_natural_fire(client, feed):
    ev = next(e for e in events(client).values() if e["facility_id"] is None)
    ctx = client.get(f"/api/context/events/{ev['event_id']}").json()
    assert ctx["nearest"] is None and ctx["nearby_count"] == 0
    assert "No relevant facility context" in ctx["statement"] and "does not indicate a natural fire" in ctx["statement"]
    assert client.get("/api/context/events/NOPE").status_code == 404


def test_facility_context_does_not_force_severity_or_use_nasa_confidence(client, feed):
    ev = next(e for e in events(client).values() if e["facility_id"] == "OSM-77")
    assert ev["severity"] in ("LOW", "MEDIUM")                            # one 5 MW pixel next to a refinery is still not an alert
    inv = client.get(f"/api/events/{ev['event_id']}/investigation").json()
    assert inv["deviation"]["baseline_confidence"] == "INSUFFICIENT" and inv["deviation"]["overall_deviation_score"] == 0.0
    assert inv["thermal_twin"]["baseline_confidence"] == "INSUFFICIENT"   # no history => explicitly insufficient, never fabricated


def test_nasa_confidence_never_changes_orbiflare_risk(client, feed):
    def risk_for(conf):
        feed["csv"] = csv_of(row(12.0, 76.0, "1100", conf=conf))
        client.post("/api/firms/refresh")
        e = next(e for e in events(client).values() if abs(e["centroid_lat"] - 12.0) < 0.01)
        return e["risk_score"]
    r_low = risk_for("l")
    r_high = risk_for("h")     # same geometry/FRP/time; different NASA confidence flag (same observation id -> updated in place)
    assert r_low == r_high


def test_live_summary_keeps_nasa_confidence_and_orbiflare_severity_separate_and_pure(client, feed):
    s = client.get("/api/context/live-summary").json()
    assert s["purity"] == {"demo_observations": 0, "demo_events": 0}
    assert set(s["firms_observations"]["by_nasa_confidence"]) <= {"low", "nominal", "high", "n/a"}
    assert set(s["events"]["by_orbiflare_severity"]) <= {"LOW", "MEDIUM", "HIGH", "CRITICAL", "UNSCORED"}
    b = s["events"]["by_baseline"]
    assert sum(b.values()) == s["events"]["live_total"] and s["events"]["with_facility_context"] + s["events"]["without_facility_context"] == s["events"]["live_total"]
    assert b["ESTABLISHED"] == 0                                          # a few test observations can never establish a baseline
