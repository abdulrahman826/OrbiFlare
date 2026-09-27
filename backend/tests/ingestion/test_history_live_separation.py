"""End-to-end: a real historical baseline changes ONLY the Thermal Twin; live events, alerts, counts and ids stay exactly as without it."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.context import facilities as facility_ctx
from app.ingestion import firms_refresh
from app.intelligence import history_baseline as hb
from app.storage import models as m
from app.storage.database import Base, SessionLocal, engine

HEADER = "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight"
LIVE_DAY = "2026-09-24"


def _row(lat, lon, hhmm, d=LIVE_DAY, frp=5.0):
    return f"{lat:.5f},{lon:.5f},335.0,0.40,0.40,{d},{hhmm},N21,VIIRS,n,2.0NRT,290.0,{frp},D"


LIVE = "\n".join([HEADER, _row(21.1000, 72.6000, "0600"), _row(21.1010, 72.6010, "0600"), _row(21.1005, 72.6005, "0745"), _row(26.2000, 80.1000, "0610")]) + "\n"
FAC = pd.DataFrame([{"facility_id": "F-REF", "lat": 21.1005, "lon": 72.6005, "facility_type": "refinery", "source": "OSM", "name": "Test Refinery", "country": "IND"}])


def _hist_raw(n_events):
    rows = []
    for k in range(n_events):
        d = (date(2026, 4, 1) + timedelta(days=5 * k)).isoformat()
        for j, hhmm in enumerate((630, 815, 1930)):
            rows.append({"latitude": 21.1000 + 0.0005 * j, "longitude": 72.6000, "bright_ti4": 330.0, "scan": 0.4, "track": 0.4, "acq_date": d, "acq_time": hhmm, "satellite": "N20",
                         "instrument": "VIIRS", "confidence": "n", "bright_ti5": 290.0, "frp": 6.0 + k, "daynight": "N", "source_product": "VIIRS_NOAA20_SP", "type": 2})
    return pd.DataFrame(rows)


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    from app.main import app
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


def _run(client, monkeypatch, tmp_path, n_hist):
    s = get_settings()
    monkeypatch.setattr(s, "firms_history_dir", str(tmp_path / f"h{n_hist}"))
    hb._reset()
    if n_hist:
        hb.build_history_baseline(raw=_hist_raw(n_hist), index=facility_ctx.FacilityContextIndex(FAC))
    monkeypatch.setattr(firms_refresh, "fetch_firms_sources", lambda: [("VIIRS_NOAA21_NRT", LIVE)])
    monkeypatch.setattr(facility_ctx, "get_index", lambda: facility_ctx.FacilityContextIndex(FAC))
    summary = client.post("/api/firms/refresh").json()
    events = {e["event_id"]: e for e in client.get("/api/events").json()}
    with SessionLocal() as db:
        state = {"alerts": db.query(m.AlertRecord).count(), "history": db.query(m.AlertHistoryRecord).count(), "obs": db.query(m.ObservationRecord).count(),
                 "obs_ids": sorted(o.observation_id for o in db.query(m.ObservationRecord)), "twin": [t.baseline_confidence for t in db.query(m.ThermalTwinRecord)]}
    live_summary = client.get("/api/context/live-summary").json()
    return summary, events, state, live_summary


def _fresh(client):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_history_never_changes_live_events_alerts_or_counts_only_the_twin(client, monkeypatch, tmp_path):
    base_summary, base_events, base_state, base_live = _run(client, monkeypatch, tmp_path, 0)
    assert base_state["twin"] == ["INSUFFICIENT"]                                              # no history: the current event has nothing to compare with
    _fresh(client)
    hist_summary, hist_events, hist_state, hist_live = _run(client, monkeypatch, tmp_path, 6)

    # identical live picture
    assert set(hist_events) == set(base_events)                                                # same current event ids
    assert hist_summary["events_total"] == base_summary["events_total"] == 2 and hist_summary["new_observations"] == base_summary["new_observations"] == 4
    assert hist_live["events"]["live_total"] == base_live["events"]["live_total"] == 2         # active/current event count untouched
    assert hist_live["firms_observations"]["total"] == base_live["firms_observations"]["total"] == 4
    assert (hist_state["alerts"], hist_state["history"]) == (base_state["alerts"], base_state["history"])   # no alerts created by history
    assert hist_state["obs_ids"] == base_state["obs_ids"] and hist_state["obs"] == 4                          # no historical row stored as an observation
    assert not any(k.startswith("HIST") for k in hist_events) and not any(o.startswith("HIST") for o in hist_state["obs_ids"])
    assert all(e["status"] == "DETECTED" for e in hist_events.values())                                     # no operator/alert state change

    # the ONLY difference: the facility's Thermal Twin now has real history
    assert hist_state["twin"] == ["ESTABLISHED"] and hist_live["facilities_with_context"]["twins_by_baseline"]["ESTABLISHED"] == 1
    ev = next(e for e in hist_events.values() if e["facility_id"] == "F-REF")
    assert ev["baseline_confidence"] == "ESTABLISHED" and ev["overall_deviation_score"] is not None
    base_ev = next(e for e in base_events.values() if e["facility_id"] == "F-REF")
    assert base_ev["baseline_confidence"] == "INSUFFICIENT" and base_ev["overall_deviation_score"] in (0, 0.0)  # insufficient => deviation 0


def test_the_live_event_is_not_its_own_history_even_when_history_overlaps_the_live_window(client, monkeypatch, tmp_path):
    """History rows dated INSIDE the live window (same day/time as the live detections) must not become baseline for the live event."""
    s = get_settings()
    monkeypatch.setattr(s, "firms_history_dir", str(tmp_path / "overlap"))
    hb._reset()
    overlap = _hist_raw(1).assign(acq_date=LIVE_DAY)                              # 3 detections on the live day at the live facility
    hb.build_history_baseline(raw=pd.concat([overlap, _hist_raw(1)], ignore_index=True), index=facility_ctx.FacilityContextIndex(FAC))
    monkeypatch.setattr(firms_refresh, "fetch_firms_sources", lambda: [("VIIRS_NOAA21_NRT", LIVE)])
    monkeypatch.setattr(facility_ctx, "get_index", lambda: facility_ctx.FacilityContextIndex(FAC))
    client.post("/api/firms/refresh")
    with SessionLocal() as db:
        twin = db.query(m.ThermalTwinRecord).one()
    assert twin.payload["historical_event_count"] == 1                             # only the genuinely earlier event counts; the same-day one is excluded
    assert twin.baseline_confidence == "INSUFFICIENT"
