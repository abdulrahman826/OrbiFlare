"""On-demand NASA FIRMS refresh (India only) -- the primary, authoritative observation source.

  NASA FIRMS Area API (NOAA-21 [+ NOAA-20] VIIRS NRT) -> validate -> upsert observations (stable ids, all NASA fields kept)
  -> re-run the EXISTING event stages over the stored real observations -> return an honest summary.

Rules this module enforces:
  * The MAP_KEY comes from the server environment and never appears in results, logs or error messages.
  * Observation values are exactly what NASA returned (lat/lon, frp, bright_ti4/ti5, acquisition time, satellite, confidence,
    scan/track). Nothing is generated, interpolated or substituted.
  * A failed refresh leaves everything already stored exactly as it was, and never switches to synthetic data.
  * After the first successful live sync the synthetic DEMO dataset is removed from the primary database, so demo and live data
    can never be mixed. (It stays available to automated tests / an explicit dev rebuild on an empty database.)
  * Operator lifecycle state survives re-clustering (same event id: kept; grown/merged event: carried over + audited).
"""
from __future__ import annotations

import csv
import io
import logging
import threading
from datetime import datetime

import httpx
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ingestion import firms as firms_adapter
from app.intelligence import pipeline as pl
from app.model.schemas import AlertState, Sensor, ThermalObservation
from app.preprocessing.cleaning import deduplicate
from app.storage import models as m
from app.storage import repositories as repo

logger = logging.getLogger("orbiflare.firms")
_LOCK = threading.Lock()
REQUIRED_COLUMNS = {"latitude", "longitude", "acq_date", "acq_time"}
SATELLITE_NAMES = {"N": "Suomi NPP", "N20": "NOAA-20", "N21": "NOAA-21"}
LEGACY_PRODUCT = "VIIRS_NOAA21_NRT"     # every observation stored before satellites were recorded came from this product


class FirmsError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 502):
        super().__init__(message)
        self.code, self.message, self.http_status = code, message, http_status


# --------------------------------------------------------------------------- fetch

def _fetch_one(product: str) -> str:
    """One small request: India bounding box, one VIIRS NRT product, a couple of days. Errors are mapped to short, key-free
    messages (httpx exception text can contain the request URL, which contains the key)."""
    s = get_settings()
    url = f"{s.firms_api_base}/{s.firms_map_key}/{product}/{s.firms_bbox}/{s.firms_day_range}"
    try:
        resp = httpx.get(url, timeout=s.firms_timeout_s)
    except httpx.TimeoutException:
        raise FirmsError("TIMEOUT", "NASA FIRMS did not respond in time.", 504) from None
    except httpx.HTTPError:
        raise FirmsError("HTTP_ERROR", "Could not reach NASA FIRMS.", 502) from None
    if resp.status_code in (401, 403):
        raise FirmsError("INVALID_KEY", "NASA FIRMS rejected the MAP_KEY.", 502)
    if resp.status_code == 429:
        raise FirmsError("RATE_LIMITED", "NASA FIRMS rate limit reached; try again later.", 429)
    if resp.status_code != 200:
        raise FirmsError("HTTP_ERROR", f"NASA FIRMS returned HTTP {resp.status_code}.", 502)
    return resp.text


def fetch_firms_sources() -> list[tuple[str, str]]:
    """[(product, csv_text)] for every configured product. All-or-nothing: if any product fails, nothing is stored."""
    s = get_settings()
    if not s.firms_map_key:
        raise FirmsError("NOT_CONFIGURED", "FIRMS_MAP_KEY is not configured on the server.", 503)
    return [(p, _fetch_one(p)) for p in s.firms_source_list]


def _validate_body(text: str) -> None:
    body = (text or "").strip()
    if not body:
        raise FirmsError("MALFORMED", "NASA FIRMS returned an empty response.")
    header = body.splitlines()[0].lower()
    if "latitude" not in header:
        low = body[:200].lower()
        if "invalid" in low and "key" in low:
            raise FirmsError("INVALID_KEY", "NASA FIRMS rejected the MAP_KEY.")
        if "limit" in low or "exceed" in low:
            raise FirmsError("RATE_LIMITED", "NASA FIRMS rate limit reached; try again later.", 429)
        raise FirmsError("MALFORMED", "NASA FIRMS response was not a recognisable CSV.")
    missing = REQUIRED_COLUMNS - {c.strip() for c in header.split(",")}
    if missing:
        raise FirmsError("MALFORMED", f"NASA FIRMS response is missing columns: {', '.join(sorted(missing))}.")


# --------------------------------------------------------------------------- state

def _state(db: Session) -> m.FirmsSyncStateRecord:
    row = db.get(m.FirmsSyncStateRecord, 1)
    if row is None:
        row = m.FirmsSyncStateRecord(id=1, satellites=[])
        db.add(row)
        db.flush()
    return row


def _record_failure(db: Session, err: FirmsError) -> None:
    db.rollback()
    st = _state(db)
    st.last_attempt_at, st.last_status = datetime.utcnow(), "FAILED"
    st.last_error_code, st.last_error_message = err.code, err.message
    db.commit()


def sensor_label(satellites: list[str] | None, live: bool, demo: bool) -> str:
    """Sensor text derived from what is actually stored / returned -- never a hard-coded satellite."""
    parts: list[str] = []
    if live:
        names = [SATELLITE_NAMES.get(s, s) for s in (satellites or [])]
        parts.append("VIIRS 375m · " + (" + ".join(names) + " NRT" if names else "FIRMS"))
    if demo:
        parts.append("demo data" if not live else "+ demo data")
    return " ".join(parts) if parts else "no observations"


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() + "Z" if dt else None


def status_summary(db: Session) -> dict:
    st = db.get(m.FirmsSyncStateRecord, 1)
    s = get_settings()
    return {
        "configured": bool(s.firms_map_key),
        "manual_refresh_enabled": bool(s.firms_manual_refresh),
        "source_products": list(s.firms_source_list),
        "last_attempt_at": _iso(st.last_attempt_at) if st else None,
        "last_sync_at": _iso(st.last_sync_at) if st else None,
        "last_status": st.last_status if st else None,
        "last_error_code": st.last_error_code if st else None,
        "last_error_message": st.last_error_message if st else None,
        "last_acquisition": _iso(st.last_acquisition) if st else None,
        "satellites": list(st.satellites or []) if st else [],
        "last_received": st.received if st else 0,
        "last_new": st.new_observations if st else 0,
    }


# --------------------------------------------------------------------------- store

def _chunks(seq: list, n: int = 400):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _backfill_legacy_satellite(db: Session) -> None:
    """Rows stored before satellites were recorded all came from the NOAA-21 product (recorded in the sync state); tag them so
    the next upsert can complete their scan/track instead of duplicating them."""
    st = db.get(m.FirmsSyncStateRecord, 1)
    if st is None or st.source_product != LEGACY_PRODUCT:
        return
    db.execute(update(m.ObservationRecord)
               .where(m.ObservationRecord.source == "FIRMS", m.ObservationRecord.satellite.is_(None))
               .values(satellite="N21", instrument="VIIRS", source_product=LEGACY_PRODUCT))
    db.flush()


def _upsert_observations(db: Session, obs: list[ThermalObservation]) -> tuple[int, int]:
    """Insert new observations, update changed ones. Identity = the stable FIRMS-field hash used by the normaliser
    (source|sensor[|satellite]|lat|lon|acquisition time), so a repeat refresh cannot double-count."""
    existing: dict[str, m.ObservationRecord] = {}
    for ids in _chunks([o.observation_id for o in obs]):
        for r in db.scalars(select(m.ObservationRecord).where(m.ObservationRecord.observation_id.in_(ids))):
            existing[r.observation_id] = r
    new = [o for o in obs if o.observation_id not in existing]
    repo.bulk_insert_observations(db, new)
    updated = 0
    for o in obs:
        r = existing.get(o.observation_id)
        if r is None:
            continue
        flags = [q.value for q in o.quality_flags]
        mine = (r.frp, r.brightness_temperature, r.brightness_temperature_11, r.confidence, r.quality_flags,
                r.satellite, r.instrument, r.scan, r.track, r.source_product)
        theirs = (o.frp, o.brightness_temperature, o.brightness_temperature_11, o.confidence, flags,
                  o.satellite, o.instrument, o.scan, o.track, o.source_product)
        if mine != theirs:
            r.frp, r.brightness_temperature, r.brightness_temperature_11 = o.frp, o.brightness_temperature, o.brightness_temperature_11
            r.confidence, r.quality_flags = o.confidence, flags
            r.satellite, r.instrument, r.scan, r.track, r.source_product = o.satellite, o.instrument, o.scan, o.track, o.source_product
            updated += 1
    db.flush()
    return len(new), updated


# --------------------------------------------------------------------------- events

def assign_stable_event_ids(events, old_obs: dict[str, set[str]], old_first: dict[str, datetime]) -> dict:
    """Continuity matching. A new cluster that contains observations of an existing event keeps THAT event's id.

    Largest overlap wins; ties go to the older event. Each old id is claimed by at most one cluster. Everything that is not a
    plain 'same id' outcome is returned as a lineage note so it can be written to the audit trail:
      merged   : old events absorbed into a surviving event (old_id -> survivor)
      split    : an old event's observations now form several clusters (old_id kept by the biggest; others are new events)
    """
    obs_owner = {oid: eid for eid, obs in old_obs.items() for oid in obs}
    claims = []
    for idx, e in enumerate(events):
        counts: dict[str, int] = {}
        for oid in e.source_observation_ids:
            if oid in obs_owner:
                counts[obs_owner[oid]] = counts.get(obs_owner[oid], 0) + 1
        for old_id, c in counts.items():
            claims.append((c, old_first[old_id], idx, old_id))
    claims.sort(key=lambda t: (-t[0], t[1], t[2]))
    assigned: dict[int, str] = {}
    used: set[str] = set()
    for _c, _t, idx, old_id in claims:
        if idx not in assigned and old_id not in used:
            assigned[idx] = old_id
            used.add(old_id)
    for idx, old_id in assigned.items():
        events[idx].event_id = old_id

    final_of_cluster = {idx: events[idx].event_id for idx in range(len(events))}
    merged: dict[str, str] = {}
    split: dict[str, list[str]] = {}
    for _c, _t, idx, old_id in claims:
        if old_id in used and assigned.get(idx) != old_id:
            split.setdefault(old_id, []).append(final_of_cluster[idx])     # some of old_id's observations left for another cluster
        elif old_id not in used:
            merged.setdefault(old_id, final_of_cluster[idx])              # old_id lost its identity to the cluster that absorbed it
    return {"assigned": assigned, "merged": merged, "split": split}


def _reprocess_real_events(db: Session) -> dict:
    """Run the existing event stages over every stored REAL (FIRMS) observation, with REAL facility context.

    Event identity is stable: an evolving event keeps its id (and therefore its operator state, audit history, investigation
    history and trajectory) as compatible observations arrive."""
    from app.context import facilities as facility_ctx

    real_rows = list(db.scalars(select(m.ObservationRecord).where(m.ObservationRecord.source == "FIRMS")))
    observations = [repo.observation_to_schema(r) for r in real_rows]

    old_events = list(db.scalars(select(m.EventRecord).where(m.EventRecord.is_demo.is_(False))))
    old_obs: dict[str, set[str]] = {e.event_id: {o.observation_id for o in e.observations} for e in old_events}
    old_first = {e.event_id: e.first_detected for e in old_events}
    old_alert = {a.event_id: a for a in db.scalars(select(m.AlertRecord).where(m.AlertRecord.event_id.in_(list(old_obs) or [""])))}

    events = pl.form_events_stage(observations)
    lineage = assign_stable_event_ids(events, old_obs, old_first)

    # Real facility context (OSM + GPPD). Spatial association only; nothing is attributed to a facility.
    idx = facility_ctx.get_index()
    radius = get_settings().facility_context_radius_km
    used_ids: set[str] = set()
    for e in events:
        hit = idx.nearest(e.centroid_lat, e.centroid_lon, radius)
        e.facility_id, e.facility_distance_km = (hit["facility_id"], hit["distance_km"]) if hit else (None, None)
        e.facility_context_quality = hit["context_quality"] if hit else None
        if hit:
            used_ids.add(hit["facility_id"])
    facilities = [f for f in (idx.facility(i) for i in sorted(used_ids)) if f is not None]
    facilities_by_id = {f.facility_id: f for f in facilities}

    twins, _cur, obs_by_event = pl.build_thermal_twins_stage(events, observations)
    deviations = pl.calculate_deviations_stage(events, twins, obs_by_event)
    predictions = pl.classify_stage(events)
    stacks = pl.build_evidence_stage(events, deviations, predictions, facilities_by_id)
    risks = pl.calculate_risk_stage(events, deviations, predictions, obs_by_event)
    trajectories = pl.calculate_trajectory_stage(events, twins, obs_by_event)

    new_ids = {e.event_id for e in events}
    for e in events:                                            # same id => same operator state
        if e.event_id in old_alert:
            e.status = AlertState(old_alert[e.event_id].state)

    pl.persist(db, facilities, events, observations, twins, deviations, stacks, risks, trajectories)

    # ---- lineage: record WHY events were merged / split / dropped, and never lose human decisions ----
    for old_id, survivor in lineage["merged"].items():
        db.execute(update(m.AlertHistoryRecord).where(m.AlertHistoryRecord.event_id == old_id).values(event_id=survivor))
        old_state = old_alert[old_id].state if old_id in old_alert else AlertState.DETECTED.value
        cur = db.get(m.AlertRecord, survivor)
        if old_state != AlertState.DETECTED.value and cur is not None and cur.state == AlertState.DETECTED.value:
            repo.set_alert_state(db, survivor, old_state, "system", f"State carried over from {old_id}, which was merged into this event")
        repo.add_alert_note(db, survivor, f"Event {old_id} was merged into this event after a FIRMS refresh (spatio-temporal continuity of observations).")
    for old_id, new_ids_from_split in lineage["split"].items():
        repo.add_alert_note(db, old_id, f"After a FIRMS refresh some observations of this event now form separate event(s): {', '.join(sorted(set(new_ids_from_split)))}.")
    stale = [eid for eid in old_obs if eid not in new_ids]
    for eid in stale:                                           # superseded / vanished real events and their derived rows
        for model in (m.AlertHistoryRecord, m.AlertRecord, m.DeviationRecord, m.EvidenceRecord, m.RiskAssessmentRecord, m.RiskTrajectoryPointRecord):
            db.execute(delete(model).where(model.event_id == eid))
        db.execute(delete(m.EventRecord).where(m.EventRecord.event_id == eid))
    db.commit()

    unchanged = sum(1 for e in events if e.event_id in old_obs and set(e.source_observation_ids) == old_obs[e.event_id])
    updated = sum(1 for e in events if e.event_id in old_obs and set(e.source_observation_ids) != old_obs[e.event_id])
    created = sum(1 for e in events if e.event_id not in old_obs)
    with_ctx = sum(1 for e in events if e.facility_id)
    return {"total": len(events), "unchanged": unchanged, "updated": updated, "created": created,
            "merged": len(lineage["merged"]), "split": len(lineage["split"]), "with_facility_context": with_ctx,
            "facilities_referenced": len(facilities)}


# --------------------------------------------------------------------------- synthetic data removal

def purge_demo_data(db: Session) -> dict:
    """Remove the synthetic DEMO dataset (facilities, twins, observations, events and everything derived from them).

    Called only after live FIRMS observations have been stored, so synthetic and live data never coexist in the primary
    database. Historical reference incidents are file-based and unaffected."""
    demo_events = [r for r in db.scalars(select(m.EventRecord.event_id).where(m.EventRecord.is_demo.is_(True)))]
    demo_facilities = [r for r in db.scalars(select(m.FacilityRecord.facility_id).where(m.FacilityRecord.is_demo.is_(True)))]
    n_obs = db.query(m.ObservationRecord).filter(m.ObservationRecord.source == "DEMO").count()
    if not (demo_events or demo_facilities or n_obs):
        return {"events": 0, "facilities": 0, "observations": 0}
    db.execute(delete(m.ObservationRecord).where(m.ObservationRecord.source == "DEMO"))
    for ids in _chunks(demo_events):
        for model in (m.AlertHistoryRecord, m.AlertRecord, m.DeviationRecord, m.EvidenceRecord, m.RiskAssessmentRecord, m.RiskTrajectoryPointRecord):
            db.execute(delete(model).where(model.event_id.in_(ids)))
        db.execute(update(m.ObservationRecord).where(m.ObservationRecord.event_id.in_(ids)).values(event_id=None))
        db.execute(delete(m.EventRecord).where(m.EventRecord.event_id.in_(ids)))
    for ids in _chunks(demo_facilities):
        db.execute(delete(m.ThermalTwinRecord).where(m.ThermalTwinRecord.facility_id.in_(ids)))
        db.execute(delete(m.FacilityRecord).where(m.FacilityRecord.facility_id.in_(ids)))
    db.commit()
    logger.info("Removed synthetic demo data: %d events, %d facilities, %d observations", len(demo_events), len(demo_facilities), n_obs)
    return {"events": len(demo_events), "facilities": len(demo_facilities), "observations": n_obs}


def live_observation_count(db: Session) -> int:
    return db.query(m.ObservationRecord).filter(m.ObservationRecord.source == "FIRMS").count()


# --------------------------------------------------------------------------- public entry

def refresh_firms(db: Session) -> dict:
    if not _LOCK.acquire(blocking=False):
        raise FirmsError("BUSY", "A FIRMS refresh is already running.", 409)
    try:
        try:
            payloads = fetch_firms_sources()
            all_obs: list[ThermalObservation] = []
            per_source: list[dict] = []
            satellites: set[str] = set()
            dq_records = []
            for product, text in payloads:
                _validate_body(text)
                observations, dq = firms_adapter._run_pipeline(text, Sensor.VIIRS)
                if dq.rows_received > 0 and not observations:
                    raise FirmsError("MALFORMED", "NASA FIRMS rows could not be parsed.")
                for o in observations:
                    o.source_product = product
                sats = sorted({(r.get("satellite") or "").strip() for r in csv.DictReader(io.StringIO(text)) if r.get("satellite")})
                satellites.update(sats)
                all_obs.extend(observations)
                dq_records.append(dq)
                per_source.append({"product": product, "satellites": sats, "received": dq.rows_received,
                                   "rejected": dq.rows_rejected})
            all_obs, _dups = deduplicate(all_obs)
            received = sum(s["received"] for s in per_source)

            _backfill_legacy_satellite(db)
            new, updated = _upsert_observations(db, all_obs)
            for dq in dq_records:
                repo.record_data_quality(db, dq)
            events = _reprocess_real_events(db)
        except FirmsError as err:
            _record_failure(db, err)
            raise
        except Exception:                                       # never leak internals / key-bearing text
            logger.exception("FIRMS refresh failed unexpectedly")
            err = FirmsError("INTERNAL", "FIRMS data could not be processed.", 500)
            _record_failure(db, err)
            raise err from None

        live_total = live_observation_count(db)
        demo_removed = purge_demo_data(db) if live_total > 0 else {"events": 0, "facilities": 0, "observations": 0}

        now = datetime.utcnow()
        st = _state(db)
        stored_first = db.scalar(select(m.ObservationRecord.timestamp).where(m.ObservationRecord.source == "FIRMS").order_by(m.ObservationRecord.timestamp.asc()).limit(1))
        stored_last = db.scalar(select(m.ObservationRecord.timestamp).where(m.ObservationRecord.source == "FIRMS").order_by(m.ObservationRecord.timestamp.desc()).limit(1))
        st.last_attempt_at = st.last_sync_at = now
        st.last_status, st.last_error_code, st.last_error_message = "OK", None, None
        st.source_product = ",".join(get_settings().firms_source_list)
        st.satellites = sorted(satellites) or st.satellites
        st.last_acquisition, st.received, st.new_observations, st.updated_observations = stored_last, received, new, updated
        db.commit()

        return {
            "status": "OK", "synced_at": _iso(now), "sources": per_source, "satellites": sorted(satellites),
            "observations_received": received, "observations_stored": live_total,
            "new_observations": new, "updated_observations": updated,
            "rejected_rows": sum(s["rejected"] for s in per_source),
            "events_total": events["total"], "events_created": events["created"], "events_updated": events["updated"],
            "events_unchanged": events["unchanged"], "events_merged": events["merged"], "events_split": events["split"],
            "events_with_facility_context": events["with_facility_context"],
            "first_acquisition": _iso(stored_first), "last_acquisition": _iso(stored_last),
            "demo_data_removed": demo_removed,
            "note": "FIRMS detections are thermal observations, not confirmed fires." + (" No detections in the requested window." if received == 0 else ""),
        }
    finally:
        _LOCK.release()
