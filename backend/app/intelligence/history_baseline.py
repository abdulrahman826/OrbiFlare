"""Historical thermal events for Thermal Twin baselines.

  cached historical FIRMS rows  ->  historical observations  ->  historical thermal events (existing clustering, read-only reuse)
  -> facility association (existing facility index, same radius)  ->  precomputed parquet + manifest  ->  Thermal Twin history.

Isolation guarantees:
  * Nothing here touches the live observations/events tables. Historical objects exist only in memory and in the precomputed parquet
    files (`history_events.parquet`, `history_observations.parquet`, `history_manifest.json`).
  * The live pipeline only READS them, through `HistoryStore.events_for(facility, before=<start of the live window>)`, and only to
    supply the facility's historical events to the EXISTING Thermal Twin builder. A historical event that reaches into the live
    window is excluded, so a current event can never establish its own baseline.
  * If the files are missing or unreadable the store returns nothing: baselines fall back to the existing behaviour, and the status
    is reported as UNAVAILABLE. No values are ever fabricated.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import get_settings
from app.context import facilities as facility_ctx
from app.ingestion import firms_history as fh
from app.intelligence.events import form_events
from app.model.schemas import DataSource, DayNight, Sensor, ThermalEvent, ThermalObservation

logger = logging.getLogger("orbiflare.history")
EARTH_RADIUS_KM = 6371.0088
SCHEMA_VERSION = 1


def _paths() -> tuple[Path, Path, Path]:
    d = fh.history_dir()
    return d / "history_events.parquet", d / "history_observations.parquet", d / "history_manifest.json"


def rows_to_observations(df: pd.DataFrame) -> list[ThermalObservation]:
    """FIRMS rows -> in-memory ThermalObservation objects (never persisted to the live tables)."""
    out: list[ThermalObservation] = []
    for r in df.itertuples(index=False):
        t = str(int(r.acq_time)).zfill(4)
        ts = datetime.strptime(f"{r.acq_date} {t}", "%Y-%m-%d %H%M")
        sat = str(r.satellite)
        out.append(ThermalObservation(
            observation_id=f"HIST|{sat}|{r.latitude:.5f}|{r.longitude:.5f}|{ts:%Y%m%dT%H%M}", timestamp=ts,
            latitude=float(r.latitude), longitude=float(r.longitude), sensor=Sensor.VIIRS,
            brightness_temperature=float(r.bright_ti4) if pd.notna(r.bright_ti4) else None,
            brightness_temperature_11=float(r.bright_ti5) if pd.notna(r.bright_ti5) else None,
            frp=float(r.frp) if pd.notna(r.frp) else None, confidence=str(r.confidence) if pd.notna(r.confidence) else None,
            day_night=DayNight(r.daynight) if getattr(r, "daynight", None) in ("D", "N") else None, source=DataSource.FIRMS,
            satellite=sat, instrument=str(r.instrument) if pd.notna(r.instrument) else None,
            scan=float(r.scan) if pd.notna(r.scan) else None, track=float(r.track) if pd.notna(r.track) else None, source_product=str(r.source_product),
        ))
    return out


def build_history_baseline(raw: pd.DataFrame | None = None, index=None, radius_km: float | None = None) -> dict:
    """Cluster the cached historical rows into events, keep the ones spatially associated with an eligible facility, and write the
    precomputed baseline files. Offline/admin operation; idempotent (same input -> same output)."""
    s = get_settings()
    index = index if index is not None else facility_ctx.get_index()
    radius = radius_km if radius_km is not None else s.facility_context_radius_km
    raw = fh.load_raw() if raw is None else raw
    ev_path, ob_path, mf_path = _paths()
    fetch_manifest = fh.load_fetch_manifest()
    manifest = {"schema_version": SCHEMA_VERSION, "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "data_origin": fh.DATA_ORIGIN,
                "configured_days": s.firms_history_days, "fetch": fetch_manifest, "radius_km": radius}
    if raw.empty or index.tree is None:
        manifest.update(status="UNAVAILABLE", historical_observations=0, historical_events_total=0, historical_events_with_facility=0)
        fh.history_dir().mkdir(parents=True, exist_ok=True)
        mf_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        _reset()
        return manifest

    # Only events near an eligible facility can shape a facility baseline: prefilter the (large) point set with the same spatial index.
    pts = np.radians(raw[["latitude", "longitude"]].to_numpy(dtype=float))
    near = index.tree.query_radius(pts, r=(radius + 2.0) / EARTH_RADIUS_KM, count_only=True) > 0
    raw_near = raw[near]
    obs = rows_to_observations(raw_near)
    events = form_events(obs)
    by_id = {o.observation_id: o for o in obs}
    type_by_id = dict(zip([o.observation_id for o in obs], raw_near["type"].tolist())) if "type" in raw_near.columns else {}

    ev_rows, ob_rows = [], []
    for e in events:
        hit = index.nearest(e.centroid_lat, e.centroid_lon, radius)
        if not hit:
            continue
        eid = "HIST-" + e.event_id[4:]
        ev_rows.append({"event_id": eid, "facility_id": hit["facility_id"], "facility_distance_km": hit["distance_km"], "facility_context_quality": hit["context_quality"],
                        "first_detected": e.first_detected, "last_detected": e.last_detected, "duration_hours": e.duration_hours, "observation_count": e.observation_count,
                        "peak_frp": e.peak_frp, "mean_frp": e.mean_frp, "peak_bt": e.peak_bt, "mean_bt": e.mean_bt, "centroid_lat": e.centroid_lat,
                        "centroid_lon": e.centroid_lon, "footprint_radius_km": e.footprint_radius_km})
        typed = [type_by_id[oid] for oid in e.source_observation_ids if oid in type_by_id and pd.notna(type_by_id[oid])]
        ev_rows[-1]["firms_type_typed"], ev_rows[-1]["firms_type_static"] = len(typed), int(sum(1 for t in typed if int(t) == 2))
        for oid in e.source_observation_ids:
            o = by_id[oid]
            ob_rows.append({"event_id": eid, "observation_id": oid, "timestamp": o.timestamp, "latitude": o.latitude, "longitude": o.longitude, "frp": o.frp,
                            "brightness_temperature": o.brightness_temperature, "day_night": o.day_night.value if o.day_night else None, "satellite": o.satellite})
    ev_df, ob_df = pd.DataFrame(ev_rows), pd.DataFrame(ob_rows)
    # FIRMS `type` (0 presumed vegetation fire, 1 active volcano, 2 other static land source, 3 offshore) exists only in Standard Processing rows.
    typed = raw[raw.get("type").notna()] if "type" in raw.columns else raw.iloc[0:0]
    fh.history_dir().mkdir(parents=True, exist_ok=True)
    ev_df.to_parquet(ev_path, index=False)
    ob_df.to_parquet(ob_path, index=False)
    manifest.update(
        status="OK", historical_observations=int(len(raw)), observations_near_facilities=int(near.sum()), historical_events_total=int(len(events)),
        historical_events_with_facility=int(len(ev_df)), facilities_with_history=int(ev_df["facility_id"].nunique()) if len(ev_df) else 0,
        first_observation=str(raw["acq_date"].min()), last_observation=str(raw["acq_date"].max()),
        firms_type_present_rows=int(len(typed)), firms_type_static_land_source_rows=int((typed["type"] == 2).sum()) if len(typed) else 0,
        firms_type_note="FIRMS `type` (0=presumed vegetation fire, 1=active volcano, 2=other static land source, 3=offshore) is provided only for Standard Processing rows; NRT rows carry no type field.",
    )
    mf_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    _reset()
    return manifest


class HistoryStore:
    """Read-only access to the precomputed historical baseline events."""

    def __init__(self) -> None:
        ev_path, ob_path, mf_path = _paths()
        self.manifest: dict = {}
        self.events = pd.DataFrame()
        self.obs = pd.DataFrame()
        try:
            if mf_path.exists():
                self.manifest = json.loads(mf_path.read_text(encoding="utf-8"))
            if ev_path.exists() and ob_path.exists():
                self.events = pd.read_parquet(ev_path)
                self.obs = pd.read_parquet(ob_path)
        except Exception:                                   # corrupt/partial files: behave as "no history", never break the live app
            logger.warning("Historical baseline files could not be read; baselines fall back to live history only.")
            self.events, self.obs, self.manifest = pd.DataFrame(), pd.DataFrame(), {}
        self._by_fid = {fid: g for fid, g in self.events.groupby("facility_id")} if len(self.events) else {}

    @property
    def available(self) -> bool:
        return bool(len(self.events)) and self.manifest.get("status") == "OK"

    def coverage_fraction(self) -> float | None:
        f = self.manifest.get("fetch") or {}
        if not f.get("requested_days"):
            return None
        return min(1.0, f.get("covered_days", 0) / f["requested_days"])

    def events_for(self, facility_id: str, before: datetime | None = None) -> tuple[list[ThermalEvent], dict[str, list[ThermalObservation]]]:
        """Historical events (and their observations) associated with a facility that ENDED before `before` (start of the live window)."""
        g = self._by_fid.get(facility_id)
        if g is None:
            return [], {}
        if before is not None:
            g = g[g["last_detected"] < before]
        if g.empty:
            return [], {}
        events, obs_by_event = [], {}
        obs = self.obs[self.obs["event_id"].isin(set(g["event_id"]))]
        grouped = {k: v for k, v in obs.groupby("event_id")}
        for r in g.itertuples(index=False):
            events.append(ThermalEvent(
                event_id=r.event_id, first_detected=r.first_detected.to_pydatetime(), last_detected=r.last_detected.to_pydatetime(), duration_hours=float(r.duration_hours),
                observation_count=int(r.observation_count), peak_frp=None if pd.isna(r.peak_frp) else float(r.peak_frp), mean_frp=None if pd.isna(r.mean_frp) else float(r.mean_frp),
                peak_bt=None if pd.isna(r.peak_bt) else float(r.peak_bt), mean_bt=None if pd.isna(r.mean_bt) else float(r.mean_bt), centroid_lat=float(r.centroid_lat),
                centroid_lon=float(r.centroid_lon), footprint_radius_km=float(r.footprint_radius_km), facility_id=facility_id,
                facility_distance_km=float(r.facility_distance_km), facility_context_quality=r.facility_context_quality, source_observation_ids=[],
            ))
            obs_by_event[r.event_id] = [
                ThermalObservation(observation_id=o.observation_id, timestamp=o.timestamp.to_pydatetime(), latitude=float(o.latitude), longitude=float(o.longitude), sensor=Sensor.VIIRS,
                                   frp=None if pd.isna(o.frp) else float(o.frp), brightness_temperature=None if pd.isna(o.brightness_temperature) else float(o.brightness_temperature),
                                   day_night=DayNight(o.day_night) if o.day_night in ("D", "N") else None, source=DataSource.FIRMS, satellite=o.satellite)
                for o in grouped.get(r.event_id, pd.DataFrame()).itertuples(index=False)]
        events.sort(key=lambda e: e.first_detected)
        return events, obs_by_event

    def type_counts(self, facility_id: str) -> tuple[int, int]:
        """(typed detections, of which 'other static land source') across the facility's historical events. FIRMS provides `type` only for
        Standard Processing rows, so this is (0, 0) when history is unavailable or untyped."""
        g = self._by_fid.get(facility_id)
        if g is None or "firms_type_typed" not in g.columns:
            return 0, 0
        return int(g["firms_type_typed"].sum()), int(g["firms_type_static"].sum())

    def status(self) -> dict:
        m = self.manifest
        f = m.get("fetch") or {}
        if not self.available:
            return {"state": "UNAVAILABLE", "message": "Historical baseline: UNAVAILABLE. Thermal Twins use only the live history window."}
        cov = self.coverage_fraction()
        return {"state": "PARTIAL" if (cov is not None and cov < 0.999) else "OK", "configured_days": m.get("configured_days"), "requested_days": f.get("requested_days"),
                "covered_days": f.get("covered_days"), "coverage": cov, "window_first": f.get("window_first"), "window_last": f.get("window_last"),
                "historical_observations": m.get("historical_observations"), "historical_events_with_facility": m.get("historical_events_with_facility"),
                "facilities_with_history": m.get("facilities_with_history"), "built_at": m.get("built_at"), "failed_chunks": len(f.get("chunks_failed") or []),
                "message": None}


@lru_cache(maxsize=1)
def get_store() -> HistoryStore:
    return HistoryStore()


def _reset() -> None:
    get_store.cache_clear()
