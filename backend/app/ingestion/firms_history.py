"""Historical NASA FIRMS acquisition (India bbox) -- an explicit ADMIN operation, never run by the dashboard or the live refresh.

  python scripts/ingest_firms_history.py            # fetch (resumable) + build the baseline

Design rules:
  * Isolated: raw historical rows live only in parquet files under `data/firms/historical/raw/` (data_origin = FIRMS_HISTORICAL).
    They are never written to the live observations table, so they cannot create live events, alerts or counts.
  * India-area requests only, 5-day chunks (the API maximum): ~ (days / 5) requests per product -- never one request per facility.
  * Resumable / idempotent: a chunk already cached is not downloaded again; re-running fetches only what is missing.
  * Product per date comes from NASA's own data-availability table (NOAA-20 Standard Processing for older dates, NRT for recent ones,
    NOAA-21 NRT where it exists). Suomi-NPP is not used.
  * The MAP_KEY is read from the server environment; errors are mapped to short key-free messages (httpx text contains the URL).
  * Failure of any chunk is recorded in the manifest (coverage is reported honestly) and never raises into the live application.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pandas as pd

from app.config import get_settings

logger = logging.getLogger("orbiflare.history")

DATA_ORIGIN = "FIRMS_HISTORICAL"
CHUNK_DAYS = 5                                   # FIRMS Area API: 1-5 days per request
AVAILABILITY_URL = "https://firms.modaps.eosdis.nasa.gov/api/data_availability/csv"
PRODUCT_SATELLITE = {"VIIRS_NOAA20_SP": "N20", "VIIRS_NOAA20_NRT": "N20", "VIIRS_NOAA21_NRT": "N21"}
# Preference order per satellite: Standard Processing (final, includes the FIRMS `type` field) before NRT.
SATELLITE_PRODUCTS = {"N20": ["VIIRS_NOAA20_SP", "VIIRS_NOAA20_NRT"], "N21": ["VIIRS_NOAA21_SP", "VIIRS_NOAA21_NRT"]}


class HistoryError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


@dataclass(frozen=True)
class Chunk:
    product: str
    start: date
    days: int

    @property
    def end(self) -> date:
        return self.start + timedelta(days=self.days - 1)

    @property
    def filename(self) -> str:
        return f"{self.start.isoformat()}_{self.days}d.parquet"


def history_dir() -> Path:
    return Path(get_settings().firms_history_dir)


def raw_dir(product: str) -> Path:
    return history_dir() / "raw" / product


def window(today: date | None = None, days: int | None = None) -> tuple[date, date]:
    """(first_date, last_date) of the configured history window. The last `firms_day_range + 1` days are left to the LIVE pipeline so
    the two never overlap (and a live event can never be its own baseline)."""
    s = get_settings()
    today = today or datetime.now(timezone.utc).date()
    days = days or s.firms_history_days
    last = today - timedelta(days=s.firms_day_range + 1)
    return last - timedelta(days=days - 1), last


def plan_chunks(availability: dict[str, tuple[date, date]], first: date, last: date) -> list[Chunk]:
    """Cover [first, last] for each satellite with the best available product per date. Pure function (unit-tested)."""
    chunks: list[Chunk] = []
    for _sat, products in SATELLITE_PRODUCTS.items():
        d = first
        while d <= last:
            prod = next((p for p in products if p in availability and availability[p][0] <= d <= availability[p][1]), None)
            if prod is None:                      # nothing published for this satellite on this date: skip it (coverage records the gap)
                d += timedelta(days=1)
                continue
            lo, hi = availability[prod]
            end = min(last, hi, d + timedelta(days=CHUNK_DAYS - 1))
            chunks.append(Chunk(prod, d, (end - d).days + 1))
            d = end + timedelta(days=1)
    return chunks


def _get(url: str, timeout: float) -> str:
    try:
        resp = httpx.get(url, timeout=timeout)
    except httpx.TimeoutException:
        raise HistoryError("TIMEOUT", "NASA FIRMS did not respond in time.") from None
    except httpx.HTTPError:
        raise HistoryError("HTTP_ERROR", "Could not reach NASA FIRMS.") from None
    if resp.status_code in (401, 403):
        raise HistoryError("INVALID_KEY", "NASA FIRMS rejected the MAP_KEY.")
    if resp.status_code == 429:
        raise HistoryError("RATE_LIMITED", "NASA FIRMS rate limit reached.")
    if resp.status_code != 200:
        raise HistoryError("HTTP_ERROR", f"NASA FIRMS returned HTTP {resp.status_code}.")
    return resp.text


def fetch_availability() -> dict[str, tuple[date, date]]:
    s = get_settings()
    text = _get(f"{AVAILABILITY_URL}/{s.firms_map_key}/ALL", s.firms_timeout_s)
    out: dict[str, tuple[date, date]] = {}
    for row in csv.DictReader(io.StringIO(text)):
        try:
            out[row["data_id"]] = (date.fromisoformat(row["min_date"]), date.fromisoformat(row["max_date"]))
        except (KeyError, ValueError):
            continue
    if not out:
        raise HistoryError("MALFORMED", "NASA FIRMS data-availability response was not recognisable.")
    return out


def fetch_chunk(chunk: Chunk) -> pd.DataFrame:
    s = get_settings()
    url = f"{s.firms_api_base}/{s.firms_map_key}/{chunk.product}/{s.firms_bbox}/{chunk.days}/{chunk.start.isoformat()}"
    text = _get(url, s.firms_timeout_s)
    header = (text.strip().splitlines() or [""])[0].lower()
    if "latitude" not in header:
        raise HistoryError("MALFORMED", "NASA FIRMS response was not a recognisable CSV.")
    df = pd.read_csv(io.StringIO(text))
    df["source_product"] = chunk.product
    df["data_origin"] = DATA_ORIGIN
    return df


def _manifest_path() -> Path:
    return history_dir() / "fetch_manifest.json"


def load_fetch_manifest() -> dict:
    p = _manifest_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _covered_dates(chunks_ok: list[Chunk]) -> set[date]:
    out: set[date] = set()
    for c in chunks_ok:
        out.update(c.start + timedelta(days=i) for i in range(c.days))
    return out


def ingest_history(today: date | None = None, days: int | None = None, pause_s: float = 0.4, progress=None) -> dict:
    """Fetch every missing chunk of the window. Returns (and writes) the fetch manifest; never raises for chunk-level failures."""
    s = get_settings()
    if not s.firms_map_key:
        return {"status": "NOT_CONFIGURED", "message": "FIRMS_MAP_KEY is not configured; historical baseline unavailable."}
    first, last = window(today, days)
    try:
        availability = fetch_availability()
    except HistoryError as err:
        return {"status": "FAILED", "code": err.code, "message": err.message}
    chunks = plan_chunks(availability, first, last)
    ok: list[Chunk] = []
    failed: list[dict] = []
    downloaded = cached = 0
    for i, ch in enumerate(chunks):
        path = raw_dir(ch.product) / ch.filename
        if path.exists():
            cached += 1
            ok.append(ch)
            continue
        try:
            df = fetch_chunk(ch)
        except HistoryError as err:
            failed.append({"product": ch.product, "start": ch.start.isoformat(), "days": ch.days, "code": err.code})
            if err.code in ("INVALID_KEY", "RATE_LIMITED"):
                break                                     # will not get better by hammering
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        downloaded += 1
        ok.append(ch)
        if progress:
            progress(i + 1, len(chunks), ch, len(df))
        time.sleep(pause_s)
    want_days = (last - first).days + 1
    sats = {}
    for sat, products in SATELLITE_PRODUCTS.items():
        sats[sat] = len(_covered_dates([c for c in ok if PRODUCT_SATELLITE.get(c.product) == sat]))
    manifest = {
        "status": "OK" if not failed else "PARTIAL", "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window_first": first.isoformat(), "window_last": last.isoformat(), "requested_days": want_days,
        "covered_days_by_satellite": sats, "covered_days": max(sats.values()) if sats else 0,
        "chunks_planned": len(chunks), "chunks_downloaded": downloaded, "chunks_cached": cached, "chunks_failed": failed,
        "products": sorted({c.product for c in chunks}), "availability": {k: [v[0].isoformat(), v[1].isoformat()] for k, v in availability.items() if k in PRODUCT_SATELLITE},
    }
    history_dir().mkdir(parents=True, exist_ok=True)
    _manifest_path().write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def load_raw() -> pd.DataFrame:
    """All cached historical rows, de-duplicated on stable source attributes (satellite, lat, lon, date, time): overlapping windows,
    repeated downloads and an SP/NRT overlap can never create duplicates. Standard Processing wins over NRT."""
    frames = []
    for prod in PRODUCT_SATELLITE:
        for p in sorted(raw_dir(prod).glob("*.parquet")) if raw_dir(prod).exists() else []:
            frames.append(pd.read_parquet(p))
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df["_sp"] = df["source_product"].str.endswith("_SP")
    df = df.sort_values("_sp", ascending=False).drop_duplicates(subset=["satellite", "latitude", "longitude", "acq_date", "acq_time"], keep="first")
    return df.drop(columns="_sp").reset_index(drop=True)
