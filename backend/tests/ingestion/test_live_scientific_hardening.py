"""Live-pipeline hardening: facility quality persisted and applied, split/merge lineage, data purity, ML batching. No network."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.context import facilities as facility_ctx
from app.ingestion import firms_refresh
from app.storage import models as m
from app.storage.database import Base, SessionLocal, engine

HEADER = "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight"


def row(lat, lon, hhmm, frp=5.0, sat="N21", conf="n", date="2026-09-24"):
    return f"{lat:.5f},{lon:.5f},335.0,0.40,0.40,{date},{hhmm},{sat},VIIRS,{conf},2.0NRT,290.0,{frp},D"


def csv_of(*rows):
    return "\n".join([HEADER, *rows]) + "\n"


def index_of(rows):
    return facility_ctx.FacilityContextIndex(pd.DataFrame(rows, columns=["facility_id", "lat", "lon", "facility_type", "source", "name", "country"]))


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    from app.main import app
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def feed(monkeypatch):
    state = {"csv": csv_of(), "index": facility_ctx.FacilityContextIndex()}
    monkeypatch.setattr(firms_refresh, "fetch_firms_sources", lambda: [("VIIRS_NOAA21_NRT", state["csv"])])
    monkeypatch.setattr(facility_ctx, "get_index", lambda: state["index"])
    return state


def events(client):
    return {e["event_id"]: e for e in client.get("/api/events").json()}


# ------------------------------------------------------------------ lineage (pure)

class _E:
    def __init__(self, eid, obs):
        self.event_id, self.source_observation_ids = eid, obs


def test_assign_stable_ids_growth_split_and_merge_unit():
    assign = firms_refresh.assign_stable_event_ids
    t = datetime(2026, 9, 1)
    grown = [_E("NEW", ["a", "b", "c", "d"])]
    assert assign(grown, {"OLD": {"a", "b"}}, {"OLD": t})["assigned"] == {0: "OLD"} and grown[0].event_id == "OLD"      # growth keeps identity

    split = [_E("N1", ["a", "b", "c"]), _E("N2", ["d"])]
    res = assign(split, {"OLD": {"a", "b", "c", "d"}}, {"OLD": t})
    assert split[0].event_id == "OLD" and split[1].event_id == "N2" and res["split"] == {"OLD": ["N2"]}                   # biggest keeps id

    merge = [_E("N", ["a", "b", "c"])]
    res = assign(merge, {"A": {"a", "b"}, "B": {"c"}}, {"A": t, "B": datetime(2026, 9, 2)})
    assert merge[0].event_id == "A" and res["merged"] == {"B": "A"}                                                       # older identity survives

    tie = [_E("N", ["a", "b"])]
    assign(tie, {"Y": {"a"}, "X": {"b"}}, {"Y": datetime(2026, 9, 3), "X": datetime(2026, 9, 2)})
    assert tie[0].event_id == "X"                                                                                          # tie -> older event

    fresh = [_E("N", ["z"])]
    assert assign(fresh, {"OLD": {"a"}}, {"OLD": t})["assigned"] == {} and fresh[0].event_id == "N"                       # unrelated -> new id


# ------------------------------------------------------------------ split end-to-end (audited, state preserved)

CHAIN = [row(21.1000, 72.6000, "0600"), row(21.1100, 72.6000, "0630"), row(21.1200, 72.6000, "0700")]     # ~1.1 km links -> one event


def test_split_is_audited_and_keeps_the_original_identity_and_operator_state(client, feed):
    feed["csv"] = csv_of(*CHAIN)
    client.post("/api/firms/refresh")
    ev = events(client)
    assert len(ev) == 1
    old_id = next(iter(ev))
    assert ev[old_id]["observation_count"] == 3
    assert client.post(f"/api/events/{old_id}/transition", json={"to_state": "VALIDATING", "actor": "analyst1", "note": "look"}).status_code == 200

    # the bridging observation disappears (NASA revises/removes it): the remaining two are ~2.2 km apart -> no longer one event
    db = SessionLocal()
    try:
        bridge = db.query(m.ObservationRecord).filter(m.ObservationRecord.latitude.between(21.1099, 21.1101)).one()
        db.delete(bridge)
        db.commit()
    finally:
        db.close()
    feed["csv"] = csv_of(CHAIN[0], CHAIN[2])
    s = client.post("/api/firms/refresh").json()
    assert s["events_split"] == 1 and s["events_total"] == 2
    ev2 = events(client)
    assert old_id in ev2 and len(ev2) == 2                                    # one part keeps the id, the other is a new event
    new_id = next(k for k in ev2 if k != old_id)
    assert client.get(f"/api/events/{old_id}").json()["status"] == "VALIDATING"                                # operator state survives
    hist = client.get(f"/api/alerts/{old_id}/history").json()
    assert any(h["actor"] == "analyst1" and h["note"] == "look" for h in hist)                                 # human history survives
    assert any(new_id in (h["note"] or "") and "separate event" in (h["note"] or "") and h["actor"] == "system" for h in hist)   # the split is audited
    assert client.get(f"/api/events/{new_id}").json()["status"] == "DETECTED"
    assert len(client.get(f"/api/events/{old_id}/trajectory").json()["points"]) == ev2[old_id]["observation_count"]   # trajectory follows the data


# ------------------------------------------------------------------ facility quality stored and applied on live events

def test_generic_land_use_context_is_low_quality_weakly_counted_and_explained(client, feed):
    feed["index"] = index_of([
        ("OSM-G", 19.3010, 85.3010, "industrial", "OSM", "", "IND"),                    # generic land-use, unnamed
        ("OSM-R", 12.0010, 76.0010, "refinery", "OSM", "Test Refinery", "IND"),          # identified installation
    ])
    feed["csv"] = csv_of(row(19.3000, 85.3000, "1000", frp=5.0), row(12.0000, 76.0000, "1000", frp=5.0))
    client.post("/api/firms/refresh")
    ev = events(client)
    gen = next(e for e in ev.values() if abs(e["centroid_lat"] - 19.3) < 0.01)
    ref = next(e for e in ev.values() if abs(e["centroid_lat"] - 12.0) < 0.01)
    assert (gen["facility_id"], gen["facility_context_quality"]) == ("OSM-G", "LOW")
    assert (ref["facility_id"], ref["facility_context_quality"]) == ("OSM-R", "HIGH")

    ctx = client.get(f"/api/context/events/{gen['event_id']}").json()
    assert ctx["nearest"]["context_quality"] == "LOW" and "Generic industrial land-use record" in ctx["statement"]
    assert "not an identified installation" in ctx["statement"] and "Nearby does not mean caused by" in ctx["note"]
    ctx2 = client.get(f"/api/context/events/{ref['event_id']}").json()
    assert ctx2["nearest"]["context_quality"] == "HIGH" and "Refinery facility within" in ctx2["statement"] and "spatial association" in ctx2["statement"]

    r_gen = client.get(f"/api/events/{gen['event_id']}/investigation").json()["risk"]
    r_ref = client.get(f"/api/events/{ref['event_id']}/investigation").json()["risk"]
    assert r_gen["facility_context_quality"] == "LOW" and any("weak facility context" in x for x in r_gen["limiting"])
    assert not any(f["name"] == "facility_context" for f in r_gen["risk_factors"])
    assert r_ref["facility_context_quality"] == "HIGH" and r_ref["baseline_status"] == "INSUFFICIENT"
    assert r_gen["baseline_status"] == "INSUFFICIENT" and r_gen["deviation_contribution"] == 0.0 and r_gen["deviation_contribution_cap"] == 0.0
    assert gen["risk_score"] <= ref["risk_score"]                                        # a generic polygon is never stronger evidence than a refinery

    q = client.get("/api/context/live-summary").json()["events"]["by_facility_context_quality"]
    assert q["LOW"] >= 1 and q["HIGH"] >= 1


def test_trajectory_and_replay_agree_with_the_stored_risk_for_a_low_quality_event(client):
    ev = next(e for e in events(client).values() if e["facility_context_quality"] == "LOW")
    traj = client.get(f"/api/events/{ev['event_id']}/trajectory").json()
    replay = client.get(f"/api/events/{ev['event_id']}/replay").json()
    assert traj["points"][-1]["risk_score"] == ev["risk_score"] == replay["frames"][-1]["risk_score"]


# ------------------------------------------------------------------ data purity with synthetic data present

def test_synthetic_data_never_enters_live_events_baselines_twins_or_statistics(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    from app.main import app
    monkeypatch.setattr(firms_refresh, "purge_demo_data", lambda db: {"events": 0, "facilities": 0, "observations": 0})     # keep demo data to prove isolation
    idx = index_of([("OSM-P", 22.3300, 69.8600, "refinery", "OSM", "Purity Refinery", "IND")])
    monkeypatch.setattr(facility_ctx, "get_index", lambda: idx)
    monkeypatch.setattr(firms_refresh, "fetch_firms_sources",
                        lambda: [("VIIRS_NOAA21_NRT", csv_of(row(22.3301, 69.8601, "0600"), row(22.3302, 69.8602, "0700"), row(22.3300, 69.8600, "0800", date="2026-09-20")))])
    with TestClient(app) as c:
        n_demo_obs = len(c.get("/api/observations").json())
        assert n_demo_obs > 0 and any(e["is_demo"] for e in c.get("/api/events").json())            # demo present alongside live
        assert c.post("/api/firms/refresh").status_code == 200
        allev = c.get("/api/events").json()
        live = [e for e in allev if e["is_live_firms"]]
        demo_obs_ids = {o["observation_id"] for o in c.get("/api/observations").json() if not o["is_live_firms"]}
        assert live and all(not e["is_demo"] for e in live)
        assert all(not (set(e["source_observation_ids"]) & demo_obs_ids) for e in live)              # no synthetic observation inside any live event
        s = c.get("/api/context/live-summary").json()
        assert s["firms_observations"]["total"] == 3 and s["events"]["live_total"] == len(live)      # live counts exclude synthetic
        assert s["purity"]["demo_observations"] == n_demo_obs                                    # ...and synthetic is reported separately
        assert s["firms_observations"]["by_satellite"] == {"N21": 3}
        db = SessionLocal()
        try:
            twin = db.get(m.ThermalTwinRecord, "OSM-P")
            assert twin is not None and twin.payload["is_demo"] is False
            assert twin.payload["historical_observation_count"] <= 3                                  # built from the 3 real observations only
            assert not db.get(m.FacilityRecord, "OSM-P").is_demo
        finally:
            db.close()
    Base.metadata.drop_all(bind=engine)


# ------------------------------------------------------------------ ML batching stays active

def test_pipeline_classifies_and_prefetches_in_batches(monkeypatch):
    from app.intelligence import classification, pipeline as pl
    from app.intelligence.events import build_event_from_group
    from app.model import predict as predict_mod
    from app.model.schemas import DataSource, Sensor, ThermalObservation
    calls = []
    real = predict_mod.predict_many
    monkeypatch.setattr(classification, "predict_many", lambda items: (calls.append(len(items)), real(items))[1])
    classification._MEMO.clear()
    groups = [[ThermalObservation(observation_id=f"Q{i}-{k}", timestamp=datetime(2026, 9, 24, 6, k * 10), latitude=20 + i * 0.5, longitude=75.0, sensor=Sensor.VIIRS,
                                  frp=3.0 + k, brightness_temperature=320.0, source=DataSource.FIRMS) for k in range(3)] for i in range(25)]
    evs = [build_event_from_group(g) for g in groups]
    pl.classify_stage(evs)
    assert calls == [25]                                                   # 25 events -> ONE model call
    calls.clear()
    obs_by_event = {e.event_id: g for e, g in zip(evs, groups)}
    pl.calculate_trajectory_stage(evs, {}, obs_by_event)
    assert len(calls) <= 1 and sum(calls) <= 75                            # every prefix of every event -> at most one more call
