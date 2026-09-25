"""Live FIRMS refresh: parsing, errors, upsert/idempotence, NASA-field fidelity, data-mode transitions, demo-data removal, endpoint.
No network is used -- the HTTP fetch is replaced by fake CSV; the real fetch's error mapping is tested with a stubbed httpx."""
from __future__ import annotations

import csv
import io

import httpx
import pytest
from fastapi.testclient import TestClient

from app.ingestion import firms_refresh
from app.storage.database import Base, engine

HEADER = "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight"
N21_ROWS = [
    "21.10001,72.60001,335.1,0.41,0.39,2026-09-24,0644,N21,VIIRS,n,2.0NRT,290.1,4.2,D",
    "26.20002,80.10002,341.5,0.44,0.40,2026-09-24,0828,N21,VIIRS,h,2.0NRT,291.0,9.9,D",
    "19.30003,85.30003,330.2,0.38,0.37,2026-09-24,2054,N21,VIIRS,l,2.0NRT,289.0,1.1,N",
]
N20_ROWS = [
    "21.10001,72.60001,336.7,0.52,0.48,2026-09-24,0739,N20,VIIRS,n,2.0NRT,290.5,5.0,D",     # same place, different satellite/time
]
CSV21 = "\n".join([HEADER, *N21_ROWS]) + "\n"
CSV20 = "\n".join([HEADER, *N20_ROWS]) + "\n"


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    from app.main import app
    with TestClient(app) as c:  # auto-seeds the DEMO fallback scenario (empty database, no live data)
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def fake(monkeypatch):
    state = {"sources": [("VIIRS_NOAA21_NRT", CSV21), ("VIIRS_NOAA20_NRT", CSV20)]}
    monkeypatch.setattr(firms_refresh, "fetch_firms_sources", lambda: state["sources"])
    from app.context import facilities as facility_ctx
    monkeypatch.setattr(facility_ctx, "get_index", lambda: facility_ctx.FacilityContextIndex())   # hermetic: no facility context here
    return state


# ------------------------------------------------------------------ fetch / error mapping (no network)

def test_missing_map_key_is_reported_cleanly(monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "firms_map_key", "")
    with pytest.raises(firms_refresh.FirmsError) as e:
        firms_refresh.fetch_firms_sources()
    assert e.value.code == "NOT_CONFIGURED" and e.value.http_status == 503


@pytest.mark.parametrize("status,code", [(401, "INVALID_KEY"), (403, "INVALID_KEY"), (429, "RATE_LIMITED"), (500, "HTTP_ERROR")])
def test_http_errors_map_to_short_key_free_errors(monkeypatch, status, code):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "firms_map_key", "SECRETKEY123")
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(status, text="x"))
    with pytest.raises(firms_refresh.FirmsError) as e:
        firms_refresh.fetch_firms_sources()
    assert e.value.code == code and "SECRETKEY123" not in e.value.message


def test_timeout_and_network_errors_never_leak_the_key(monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "firms_map_key", "SECRETKEY123")
    for exc, code in ((httpx.ReadTimeout, "TIMEOUT"), (httpx.ConnectError, "HTTP_ERROR")):
        def boom(url, **k):
            raise exc("failed for " + url)
        monkeypatch.setattr(httpx, "get", boom)
        with pytest.raises(firms_refresh.FirmsError) as e:
            firms_refresh.fetch_firms_sources()
        assert e.value.code == code and "SECRETKEY123" not in e.value.message


def test_requests_target_india_and_the_configured_products(monkeypatch):
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "firms_map_key", "K")
    urls = []
    monkeypatch.setattr(httpx, "get", lambda url, **k: (urls.append(url), httpx.Response(200, text=CSV21))[1])
    out = firms_refresh.fetch_firms_sources()
    assert [p for p, _ in out] == ["VIIRS_NOAA21_NRT", "VIIRS_NOAA20_NRT"]
    assert all("/68,6,98,37/" in u for u in urls) and "VIIRS_NOAA21_NRT" in urls[0] and "VIIRS_NOAA20_NRT" in urls[1]


@pytest.mark.parametrize("body,code", [
    ("", "MALFORMED"), ("<html>oops</html>", "MALFORMED"), ("Invalid MAP_KEY.", "INVALID_KEY"),
    ("Exceeded rate limit", "RATE_LIMITED"), ("foo,bar\n1,2\n", "MALFORMED"), ("latitude,longitude\n1,2\n", "MALFORMED"),
])
def test_body_validation(body, code):
    with pytest.raises(firms_refresh.FirmsError) as e:
        firms_refresh._validate_body(body)
    assert e.value.code == code


def test_sensor_label_is_derived_never_hardcoded():
    assert firms_refresh.sensor_label(["N21"], live=True, demo=False) == "VIIRS 375m · NOAA-21 NRT"
    assert firms_refresh.sensor_label(["N20", "N21"], live=True, demo=False) == "VIIRS 375m · NOAA-20 + NOAA-21 NRT"
    assert firms_refresh.sensor_label([], live=False, demo=True) == "demo data"
    assert "demo data" in firms_refresh.sensor_label(["N21"], live=True, demo=True)
    assert firms_refresh.sensor_label([], live=False, demo=False) == "no observations"


# ------------------------------------------------------------------ data mode: never LIVE without a stored real response

def test_no_live_mode_before_a_successful_fetch(client):
    h = client.get("/api/health").json()
    assert h["data_mode"] == "DEMO" and h["live_firms_observations"] == 0
    assert h["firms"]["last_sync_at"] is None and "demo data" in h["sensor_label"]
    assert all(e["is_live_firms"] is False for e in client.get("/api/events").json())
    assert all(o["is_live_firms"] is False for o in client.get("/api/observations").json()[:20])


def test_failed_refresh_keeps_data_and_never_flips_mode(client, monkeypatch):
    def boom():
        raise firms_refresh.FirmsError("TIMEOUT", "NASA FIRMS did not respond in time.", 504)
    monkeypatch.setattr(firms_refresh, "fetch_firms_sources", boom)
    n_events = len(client.get("/api/events").json())
    r = client.post("/api/firms/refresh")
    assert r.status_code == 504
    body = r.json()
    assert body["status"] == "FAILED" and body["code"] == "TIMEOUT" and body["showing"] == "last available data"
    h = client.get("/api/health").json()
    assert h["data_mode"] == "DEMO" and h["firms"]["last_status"] == "FAILED" and h["firms"]["last_sync_at"] is None
    assert len(client.get("/api/events").json()) == n_events


def test_empty_result_does_not_go_live_or_remove_demo_data(client, fake):
    fake["sources"] = [("VIIRS_NOAA21_NRT", HEADER + "\n"), ("VIIRS_NOAA20_NRT", HEADER + "\n")]
    s = client.post("/api/firms/refresh").json()
    assert s["status"] == "OK" and s["observations_received"] == 0 and s["observations_stored"] == 0
    assert s["demo_data_removed"] == {"events": 0, "facilities": 0, "observations": 0}
    assert client.get("/api/health").json()["data_mode"] == "DEMO"


def test_all_rows_unparseable_is_malformed(client, fake):
    fake["sources"] = [("VIIRS_NOAA21_NRT", HEADER + "\nnot-a-number,x,y,bad-date,zz,N21,VIIRS,n,2.0NRT,1,1,D\n")]
    r = client.post("/api/firms/refresh")
    assert r.status_code == 502 and r.json()["code"] == "MALFORMED"


# ------------------------------------------------------------------ the live refresh itself

def test_successful_refresh_goes_live_stores_nasa_fields_and_removes_synthetic_data(client, fake):
    assert any(e["is_demo"] for e in client.get("/api/events").json())          # demo fallback present before the first live sync
    r = client.post("/api/firms/refresh")
    assert r.status_code == 200
    s = r.json()
    assert s["status"] == "OK" and s["observations_received"] == 4 and s["new_observations"] == 4 and s["observations_stored"] == 4
    assert s["satellites"] == ["N20", "N21"] and [x["product"] for x in s["sources"]] == ["VIIRS_NOAA21_NRT", "VIIRS_NOAA20_NRT"]
    assert s["first_acquisition"].startswith("2026-09-24T06:44") and s["last_acquisition"].startswith("2026-09-24T20:54")
    assert s["events_total"] >= 1 and s["events_created"] == s["events_total"] and s["events_updated"] == 0
    assert s["demo_data_removed"]["events"] > 0 and s["demo_data_removed"]["observations"] > 0

    h = client.get("/api/health").json()
    assert h["data_mode"] == "LIVE_FIRMS" and h["live_firms_observations"] == 4 and h["demo_observations"] == 0
    assert h["sensor_label"] == "VIIRS 375m · NOAA-20 + NOAA-21 NRT"
    events = client.get("/api/events").json()
    assert events and all(not e["is_demo"] and e["is_live_firms"] for e in events)   # no synthetic event survives
    assert client.get("/api/facilities").json() == []                               # synthetic facilities are gone too
    assert all(o["is_live_firms"] and o["source"] == "FIRMS" for o in client.get("/api/observations").json())


def test_stored_observations_match_the_nasa_response_exactly(client):
    stored = client.get("/api/observations?source=FIRMS").json()
    nasa = {}
    for rows, sat in ((N21_ROWS, "N21"), (N20_ROWS, "N20")):
        for r in csv.DictReader(io.StringIO(HEADER + "\n" + "\n".join(rows))):
            nasa[(round(float(r["latitude"]), 5), round(float(r["longitude"]), 5), r["acq_date"] + " " + r["acq_time"].zfill(4))] = r
    assert len(stored) == len(nasa) == 4
    for o in stored:
        key = (round(o["latitude"], 5), round(o["longitude"], 5), o["timestamp"][:10] + " " + o["timestamp"][11:13] + o["timestamp"][14:16])
        r = nasa[key]
        assert o["frp"] == float(r["frp"]) and o["brightness_temperature"] == float(r["bright_ti4"])
        assert o["brightness_temperature_11"] == float(r["bright_ti5"]) and o["confidence"] == r["confidence"]
        assert o["satellite"] == r["satellite"] and o["scan"] == float(r["scan"]) and o["track"] == float(r["track"])
        assert o["source_product"] == ("VIIRS_NOAA21_NRT" if r["satellite"] == "N21" else "VIIRS_NOAA20_NRT")


def test_events_are_traceable_to_their_nasa_observations_and_keep_confidence_separate_from_risk(client):
    ev = client.get("/api/events").json()[0]["event_id"]
    inv = client.get(f"/api/events/{ev}/investigation").json()
    assert inv["observations"] and all(o["source"] == "FIRMS" and o["satellite"] and o["scan"] for o in inv["observations"])
    assert {o["observation_id"] for o in inv["observations"]} == set(inv["event"]["source_observation_ids"])
    # NASA confidence 'h' (high) must not raise OrbiFlare severity: risk comes from the OrbiFlare engine only.
    events = client.get("/api/events").json()
    assert all(e["severity"] in ("LOW", "MEDIUM") for e in events)


def test_same_place_different_satellite_is_a_distinct_observation(client):
    ids = [o["observation_id"] for o in client.get("/api/observations?source=FIRMS").json()]
    assert len(ids) == len(set(ids)) == 4


def test_second_refresh_does_not_duplicate(client, fake):
    before = len(client.get("/api/observations?source=FIRMS").json())
    ev_before = sorted(e["event_id"] for e in client.get("/api/events").json())
    s = client.post("/api/firms/refresh").json()
    assert s["status"] == "OK" and s["observations_received"] == 4 and s["new_observations"] == 0 and s["updated_observations"] == 0
    assert s["events_created"] == 0 and s["events_updated"] == 0 and s["events_unchanged"] == s["events_total"]
    assert len(client.get("/api/observations?source=FIRMS").json()) == before
    assert sorted(e["event_id"] for e in client.get("/api/events").json()) == ev_before


def test_new_and_revised_rows_are_inserted_or_updated(client, fake):
    revised = N21_ROWS[0].replace(",4.2,D", ",5.5,D")
    fake["sources"] = [("VIIRS_NOAA21_NRT", "\n".join([HEADER, revised, "12.40004,77.40004,332.0,0.40,0.40,2026-09-24,0900,N21,VIIRS,n,2.0NRT,290.0,3.3,D"]) + "\n")]
    s = client.post("/api/firms/refresh").json()
    assert s["new_observations"] == 1 and s["updated_observations"] == 1 and s["observations_stored"] == 5
    assert s["events_created"] >= 1


def test_operator_state_survives_a_refresh(client, fake):
    real = client.get("/api/events").json()[0]["event_id"]
    assert client.post(f"/api/events/{real}/transition", json={"to_state": "VALIDATING", "actor": "op"}).status_code == 200
    client.post("/api/firms/refresh")
    assert client.get(f"/api/events/{real}").json()["status"] == "VALIDATING"


def test_demo_rebuild_is_refused_once_live_data_exists(client):
    r = client.post("/api/pipeline/rebuild", json={"mode": "demo"})
    assert r.status_code == 409 and "never mixed" in r.json()["detail"]
    assert all(e["is_live_firms"] for e in client.get("/api/events").json())


def test_status_endpoint_never_exposes_the_key(client):
    txt = client.get("/api/firms/status").text + client.get("/api/health").text
    from app.config import get_settings
    key = get_settings().firms_map_key
    assert not key or key not in txt


def test_http_client_logging_cannot_leak_the_map_key():
    import logging
    import app.main  # noqa: F401  (configures logging)
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
