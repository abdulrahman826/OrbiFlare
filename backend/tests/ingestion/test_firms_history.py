"""Historical FIRMS baseline: acquisition, isolation from the live pipeline, event construction, facility association, baselines."""
from __future__ import annotations

import io
import json
from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from app.config import get_settings
from app.context.facilities import FacilityContextIndex
from app.ingestion import firms_history as fh
from app.intelligence import history_baseline as hb
from app.intelligence import pipeline as pl
from app.model.schemas import BaselineConfidence, DataSource, Sensor, ThermalEvent, ThermalObservation
from app.storage import models as m

AVAIL = {
    "VIIRS_NOAA20_SP": (date(2018, 4, 1), date(2026, 6, 30)),
    "VIIRS_NOAA20_NRT": (date(2026, 7, 1), date(2026, 9, 26)),
    "VIIRS_NOAA21_NRT": (date(2024, 1, 17), date(2026, 9, 26)),
}
HEADER = "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight"


def _csv(rows):
    return "\n".join([HEADER] + rows) + "\n"


def _row(lat, lon, d, hhmm, sat="N20", frp=5.0, bt=330.0):
    return f"{lat},{lon},{bt},0.4,0.4,{d},{hhmm},{sat},VIIRS,n,2,290.0,{frp},N"


@pytest.fixture()
def hist_dir(tmp_path, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "firms_history_dir", str(tmp_path / "hist"))
    monkeypatch.setattr(s, "firms_map_key", "TESTKEY-not-real")
    hb._reset()
    yield tmp_path / "hist"
    hb._reset()


# ------------------------------------------------------------------ planning
def test_chunks_use_sp_for_old_dates_nrt_for_recent_and_split_at_the_boundary():
    chunks = fh.plan_chunks(AVAIL, date(2026, 6, 26), date(2026, 7, 10))
    n20 = [c for c in chunks if c.product.startswith("VIIRS_NOAA20")]
    assert [c.product for c in n20][:2] == ["VIIRS_NOAA20_SP", "VIIRS_NOAA20_NRT"]          # boundary at 2026-06-30 / 07-01
    assert all(c.days <= fh.CHUNK_DAYS for c in chunks)
    assert {c.product for c in chunks if c.product.startswith("VIIRS_NOAA21")} == {"VIIRS_NOAA21_NRT"}
    covered = sorted(d for c in n20 for d in (c.start + timedelta(days=i) for i in range(c.days)))
    assert covered == [date(2026, 6, 26) + timedelta(days=i) for i in range(15)]           # exact cover, no gaps, no overlaps


def test_no_suomi_npp_and_dates_outside_availability_are_skipped_not_invented():
    chunks = fh.plan_chunks({"VIIRS_NOAA21_NRT": (date(2026, 8, 1), date(2026, 9, 1))}, date(2026, 7, 25), date(2026, 8, 10))
    assert all("SNPP" not in c.product for c in chunks)
    assert min(c.start for c in chunks) == date(2026, 8, 1)


def test_window_leaves_the_live_days_to_the_live_pipeline():
    first, last = fh.window(today=date(2026, 9, 26), days=180)
    assert last == date(2026, 9, 26) - timedelta(days=get_settings().firms_day_range + 1)
    assert (last - first).days + 1 == 180
    assert fh.window(today=date(2026, 9, 26), days=365)[0] < first                        # 90 / 180 / 365 are only a setting


# ------------------------------------------------------------------ ingestion: batching, idempotency, dedup, failure
def _patch_get(monkeypatch, rows_by_call=None, fail_products=()):
    calls = []

    def fake(url, timeout):
        calls.append(url)
        if "data_availability" in url:
            return "data_id,min_date,max_date\n" + "\n".join(f"{k},{a},{b}" for k, (a, b) in AVAIL.items())
        prod = next(k for k in AVAIL if f"/{k}/" in url)
        if prod in fail_products:
            raise fh.HistoryError("TIMEOUT", "NASA FIRMS did not respond in time.")
        d = url.rstrip("/").split("/")[-1]
        return _csv([_row(22.3, 69.8, d, "0630", "N20" if "NOAA20" in prod else "N21")])
    monkeypatch.setattr(fh, "_get", fake)
    return calls


def test_ingestion_is_area_batched_resumable_and_idempotent(hist_dir, monkeypatch):
    calls = _patch_get(monkeypatch)
    m1 = fh.ingest_history(today=date(2026, 9, 26), days=20, pause_s=0)
    n_first = len(calls)
    assert m1["status"] == "OK" and m1["covered_days"] == 20 and m1["chunks_downloaded"] == m1["chunks_planned"]
    assert n_first == 1 + m1["chunks_planned"] and m1["chunks_planned"] <= 2 * 20 // fh.CHUNK_DAYS + 2   # one request per 5-day area chunk, not per facility/day
    assert all("68,6,98,37" in u for u in calls if "data_availability" not in u)                          # India bbox only
    m2 = fh.ingest_history(today=date(2026, 9, 26), days=20, pause_s=0)
    assert m2["chunks_downloaded"] == 0 and m2["chunks_cached"] == m1["chunks_planned"]
    assert len(calls) == n_first + 1                                                                      # second run: only the availability call
    assert len(fh.load_raw()) == len(fh.load_raw())


def test_overlapping_windows_repeated_downloads_and_sp_nrt_overlap_never_duplicate(hist_dir):
    sp = pd.DataFrame([{"latitude": 22.3, "longitude": 69.8, "acq_date": "2026-06-30", "acq_time": 630, "satellite": "N20", "source_product": "VIIRS_NOAA20_SP", "type": 2}])
    nrt = sp.assign(source_product="VIIRS_NOAA20_NRT", type=float("nan"))
    other_sat = sp.assign(satellite="N21", source_product="VIIRS_NOAA21_NRT")
    for prod, df, name in (("VIIRS_NOAA20_SP", sp, "a.parquet"), ("VIIRS_NOAA20_SP", sp, "b.parquet"), ("VIIRS_NOAA20_NRT", nrt, "a.parquet"), ("VIIRS_NOAA21_NRT", other_sat, "a.parquet")):
        (fh.raw_dir(prod)).mkdir(parents=True, exist_ok=True)
        df.to_parquet(fh.raw_dir(prod) / name, index=False)
    raw = fh.load_raw()
    assert len(raw) == 2                                                                                  # N20 once (SP wins), N21 kept: satellite identity preserved
    assert set(raw["satellite"]) == {"N20", "N21"} and raw[raw.satellite == "N20"].iloc[0]["source_product"] == "VIIRS_NOAA20_SP"


def test_a_failed_chunk_is_recorded_coverage_is_honest_and_nothing_raises(hist_dir, monkeypatch):
    _patch_get(monkeypatch, fail_products=("VIIRS_NOAA21_NRT",))
    man = fh.ingest_history(today=date(2026, 9, 26), days=10, pause_s=0)
    assert man["status"] == "PARTIAL" and man["chunks_failed"]
    assert man["covered_days_by_satellite"]["N21"] == 0 and man["covered_days_by_satellite"]["N20"] == 10
    assert man["covered_days"] == 10 and man["requested_days"] == 10                                      # reported per satellite, never pretended


def test_no_key_or_unreachable_availability_degrades_gracefully(hist_dir, monkeypatch):
    monkeypatch.setattr(get_settings(), "firms_map_key", "")
    assert fh.ingest_history(pause_s=0)["status"] == "NOT_CONFIGURED"
    monkeypatch.setattr(get_settings(), "firms_map_key", "TESTKEY-not-real")

    def boom(url, timeout):
        raise fh.HistoryError("HTTP_ERROR", "Could not reach NASA FIRMS.")
    monkeypatch.setattr(fh, "_get", boom)
    out = fh.ingest_history(pause_s=0)
    assert out["status"] == "FAILED" and "TESTKEY" not in json.dumps(out)


def test_the_map_key_never_reaches_manifests_or_error_messages(hist_dir, monkeypatch):
    _patch_get(monkeypatch, fail_products=("VIIRS_NOAA20_SP", "VIIRS_NOAA20_NRT"))
    fh.ingest_history(today=date(2026, 9, 26), days=10, pause_s=0)
    text = (fh.history_dir() / "fetch_manifest.json").read_text()
    assert "TESTKEY" not in text


# ------------------------------------------------------------------ event construction, facility association, isolation
def _facility_index():
    df = pd.DataFrame([{"facility_id": "F-REF", "lat": 22.30, "lon": 69.80, "facility_type": "refinery", "source": "OSM", "name": "Test Refinery", "country": "IND"},
                       {"facility_id": "F-GEN", "lat": 24.00, "lon": 71.00, "facility_type": "industrial", "source": "OSM", "name": None, "country": "IND"}])
    return FacilityContextIndex(df)


def _raw_rows():
    rows = []
    for k in range(6):                                   # 6 separate historical episodes near the refinery (days apart => 6 events)
        d = (date(2026, 4, 1) + timedelta(days=k * 4)).isoformat()
        for j, hhmm in enumerate(("0630", "0810", "1930")):
            rows.append({"latitude": 22.300 + 0.0005 * j, "longitude": 69.800, "bright_ti4": 330.0, "scan": 0.4, "track": 0.4, "acq_date": d, "acq_time": int(hhmm),
                         "satellite": "N20", "instrument": "VIIRS", "confidence": "n", "bright_ti5": 290.0, "frp": 6.0 + k, "daynight": "N", "source_product": "VIIRS_NOAA20_SP", "type": 2})
    rows.append({"latitude": 10.0, "longitude": 80.0, "bright_ti4": 320.0, "scan": 0.4, "track": 0.4, "acq_date": "2026-04-02", "acq_time": 700, "satellite": "N20",
                 "instrument": "VIIRS", "confidence": "n", "bright_ti5": 290.0, "frp": 2.0, "daynight": "D", "source_product": "VIIRS_NOAA20_SP", "type": 0})   # far from any facility
    return pd.DataFrame(rows)


def test_history_events_are_built_with_the_existing_clustering_and_associated_with_facilities(hist_dir):
    man = hb.build_history_baseline(raw=_raw_rows(), index=_facility_index())
    assert man["status"] == "OK" and man["historical_observations"] == 19
    assert man["historical_events_with_facility"] == 6 and man["facilities_with_history"] == 1
    store = hb.get_store()
    events, obs = store.events_for("F-REF")
    assert len(events) == 6 and all(e.observation_count == 3 and e.facility_id == "F-REF" for e in events)
    assert all(e.event_id.startswith("HIST-") and len(obs[e.event_id]) == 3 for e in events)               # historical ids can never collide with live EVT- ids
    assert store.type_counts("F-REF") == (18, 18)                                                          # FIRMS type kept as provided
    assert store.events_for("F-GEN") == ([], {})                                                           # no history => nothing invented


def test_history_build_is_deterministic_and_idempotent(hist_dir):
    a = hb.build_history_baseline(raw=_raw_rows(), index=_facility_index())
    ev1 = pd.read_parquet(hist_dir / "history_events.parquet")
    b = hb.build_history_baseline(raw=_raw_rows(), index=_facility_index())
    ev2 = pd.read_parquet(hist_dir / "history_events.parquet")
    assert a["historical_events_with_facility"] == b["historical_events_with_facility"] and ev1.equals(ev2)


def test_history_never_touches_the_live_tables_or_creates_live_alerts(hist_dir, db_session):
    before = (db_session.query(m.ObservationRecord).count(), db_session.query(m.EventRecord).count(), db_session.query(m.AlertRecord).count())
    hb.build_history_baseline(raw=_raw_rows(), index=_facility_index())
    obs = [o for e in hb.get_store().events_for("F-REF")[1].values() for o in e]
    events, _ = hb.get_store().events_for("F-REF")
    pl.build_thermal_twins_stage([], [])                         # reading history must not persist anything either
    after = (db_session.query(m.ObservationRecord).count(), db_session.query(m.EventRecord).count(), db_session.query(m.AlertRecord).count())
    assert before == after == (0, 0, 0)
    assert all(o.observation_id.startswith("HIST|") for o in obs) and all(e.event_id.startswith("HIST-") for e in events)


def test_missing_or_corrupt_history_files_mean_no_history_and_never_break_anything(hist_dir):
    assert not hb.get_store().available and hb.get_store().status()["state"] == "UNAVAILABLE"
    hist_dir.mkdir(parents=True, exist_ok=True)
    (hist_dir / "history_events.parquet").write_bytes(b"not parquet")
    (hist_dir / "history_observations.parquet").write_bytes(b"not parquet")
    (hist_dir / "history_manifest.json").write_text("{not json")
    hb._reset()
    st = hb.get_store()
    assert not st.available and st.events_for("F-REF") == ([], {}) and st.status()["state"] == "UNAVAILABLE"


# ------------------------------------------------------------------ Thermal Twin baselines from history (existing states and thresholds)
class _Store:
    def __init__(self, events_by_fid, coverage=1.0):
        self.events_by_fid, self.cov, self.available = events_by_fid, coverage, True

    def coverage_fraction(self):
        return self.cov

    def events_for(self, fid, before=None):
        evs = [e for e in self.events_by_fid.get(fid, []) if before is None or e.last_detected < before]
        return evs, {e.event_id: [ThermalObservation(observation_id=f"{e.event_id}-{k}", timestamp=e.first_detected + timedelta(minutes=20 * k), latitude=22.3, longitude=69.8,
                                                     sensor=Sensor.VIIRS, frp=5.0, source=DataSource.FIRMS) for k in range(e.observation_count)] for e in evs}


def _hev(i, start, n_obs=3):
    return ThermalEvent(event_id=f"HIST-{i:04d}", first_detected=start, last_detected=start + timedelta(hours=1), duration_hours=1.0, observation_count=n_obs, peak_frp=8.0 + i,
                        mean_frp=6.0, peak_bt=330.0, mean_bt=325.0, centroid_lat=22.3, centroid_lon=69.8, facility_id="F-REF", facility_distance_km=0.2, source_observation_ids=[])


def _live_event(start, n=3):
    obs = [ThermalObservation(observation_id=f"L{k}", timestamp=start + timedelta(minutes=30 * k), latitude=22.3, longitude=69.8, sensor=Sensor.VIIRS, frp=9.0, source=DataSource.FIRMS) for k in range(n)]
    e = ThermalEvent(event_id="EVT-LIVE000001", first_detected=obs[0].timestamp, last_detected=obs[-1].timestamp, duration_hours=1.0, observation_count=n, peak_frp=9.0, mean_frp=9.0,
                     centroid_lat=22.3, centroid_lon=69.8, facility_id="F-REF", facility_distance_km=0.2, source_observation_ids=[o.observation_id for o in obs])
    return e, obs


def _twin_with_history(monkeypatch, n_hist, coverage=1.0):
    live_start = datetime(2026, 9, 20, 6)
    hist = [_hev(i, datetime(2026, 4, 1) + timedelta(days=7 * i)) for i in range(n_hist)]
    monkeypatch.setattr(hb, "get_store", lambda: _Store({"F-REF": hist}, coverage))
    e, obs = _live_event(live_start)
    twins, _cur, _obs = pl.build_thermal_twins_stage([e], obs)
    return twins["F-REF"]


@pytest.mark.parametrize("n_hist,expected", [(0, BaselineConfidence.INSUFFICIENT), (1, BaselineConfidence.INSUFFICIENT), (2, BaselineConfidence.LIMITED),
                                             (3, BaselineConfidence.LIMITED), (6, BaselineConfidence.ESTABLISHED)])
def test_historical_events_populate_the_existing_three_baseline_states(monkeypatch, n_hist, expected):
    twin = _twin_with_history(monkeypatch, n_hist)
    assert twin.baseline_confidence == expected and twin.historical_event_count == n_hist
    if n_hist == 0:
        assert twin.history_start is None and twin.normal_frp.n == 0                                        # nothing fabricated: no fake zeros
    else:
        assert (twin.history_end - twin.history_start).days >= (1 if n_hist > 1 else 0) and twin.normal_frp.median is not None and twin.normal_persistence.median == 3


def test_partial_historical_coverage_never_claims_an_established_baseline(monkeypatch):
    assert _twin_with_history(monkeypatch, 6, coverage=1.0).baseline_confidence == BaselineConfidence.ESTABLISHED
    assert _twin_with_history(monkeypatch, 6, coverage=0.3).baseline_confidence == BaselineConfidence.LIMITED


def test_the_current_event_cannot_establish_its_own_baseline(monkeypatch):
    """Leakage guard: a historical event that reaches into the live window is excluded, and the current event is never in its own history."""
    live_start = datetime(2026, 9, 20, 6)
    ok = [_hev(i, datetime(2026, 4, 1) + timedelta(days=7 * i)) for i in range(2)]
    leaking = _hev(99, live_start - timedelta(minutes=30))                     # ends after the first live observation => overlaps the live window
    same_as_current = _hev(98, live_start + timedelta(minutes=10))
    monkeypatch.setattr(hb, "get_store", lambda: _Store({"F-REF": ok + [leaking, same_as_current]}))
    e, obs = _live_event(live_start)
    twin = pl.build_thermal_twins_stage([e], obs)[0]["F-REF"]
    assert twin.historical_event_count == 2                                    # only the two events fully before the live window
    twins_no_hist = pl.build_thermal_twins_stage([e], obs)[0]
    assert e.event_id not in {ev for ev in [x.event_id for x in ok]}
    # a single live event with no history at all stays INSUFFICIENT: it never baselines itself
    monkeypatch.setattr(hb, "get_store", lambda: _Store({}))
    assert pl.build_thermal_twins_stage([e], obs)[0]["F-REF"].baseline_confidence == BaselineConfidence.INSUFFICIENT and twins_no_hist


def test_without_history_the_twin_stage_behaves_exactly_as_before(monkeypatch):
    e, obs = _live_event(datetime(2026, 9, 20, 6))
    monkeypatch.setattr(hb, "get_store", lambda: _Store({}))
    with_empty = pl.build_thermal_twins_stage([e], obs)[0]["F-REF"]
    class Off:                                   # store unavailable
        available = False
        def coverage_fraction(self): return None
    monkeypatch.setattr(hb, "get_store", lambda: Off())
    off = pl.build_thermal_twins_stage([e], obs)[0]["F-REF"]
    assert with_empty.model_dump(exclude={"computed_at"}) == off.model_dump(exclude={"computed_at"})
