"""NASA FIRMS ingestion adapter.

Supports VIIRS and MODIS, via:
  1. Live FIRMS area-CSV API, when FIRMS_MAP_KEY is configured (network call).
  2. A local CSV file (offline operation / analyst-supplied extract).
  3. Nothing configured -> caller falls back to demo fixtures; this module
     never requires a key to be importable or for the app to start.

Every row is normalized, validated and cleaned; nothing is silently
discarded -- see app.preprocessing for the shared logic, and
DataQualityRecord for the audit trail this function returns alongside data.
"""
from __future__ import annotations

import csv
import io
import uuid
from pathlib import Path

import httpx

from app.config import get_settings
from app.model.schemas import DataQualityRecord, DataSource, Sensor, ThermalObservation
from app.preprocessing.cleaning import clean_batch
from app.preprocessing.normalization import normalize_firms_row
from app.preprocessing.validation import validate_coordinates, validate_timestamp

settings = get_settings()


def _parse_csv_text(text: str, sensor: Sensor) -> tuple[list[ThermalObservation], int, list[str]]:
    reader = csv.DictReader(io.StringIO(text))
    observations: list[ThermalObservation] = []
    rejected = 0
    all_issues: list[str] = []
    for raw_row in reader:
        obs, issues = normalize_firms_row(raw_row, sensor)
        all_issues.extend(issues)
        if obs is None:
            rejected += 1
            continue
        coord_check = validate_coordinates(obs.latitude, obs.longitude)
        time_check = validate_timestamp(obs.timestamp)
        if not coord_check.ok or not time_check.ok:
            rejected += 1
            all_issues.extend(coord_check.reasons + time_check.reasons)
            continue
        observations.append(obs)
    return observations, rejected, all_issues


def ingest_from_local_file(path: str | Path, sensor: Sensor = Sensor.VIIRS) -> tuple[list[ThermalObservation], DataQualityRecord]:
    text = Path(path).read_text(encoding="utf-8")
    return _run_pipeline(text, sensor)


def ingest_from_live_api(
    bbox: tuple[float, float, float, float] = (68.0, 6.0, 98.0, 37.0),  # India bounding box (west, south, east, north)
    day_range: int = 1,
    sensor: Sensor = Sensor.VIIRS,
) -> tuple[list[ThermalObservation], DataQualityRecord]:
    if not settings.firms_map_key:
        raise RuntimeError("FIRMS_MAP_KEY not configured -- use ingest_from_local_file or demo fixtures instead.")
    dataset = "VIIRS_SNPP_NRT" if sensor == Sensor.VIIRS else "MODIS_NRT"
    area = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
    url = f"{settings.firms_api_base}/{settings.firms_map_key}/{dataset}/{area}/{day_range}"
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
    return _run_pipeline(resp.text, sensor)


def _run_pipeline(csv_text: str, sensor: Sensor) -> tuple[list[ThermalObservation], DataQualityRecord]:
    observations, rejected, issues = _parse_csv_text(csv_text, sensor)
    rows_received = observations.__len__() + rejected
    result = clean_batch(observations, rejected_rows=rejected)
    record = DataQualityRecord(
        batch_id=uuid.uuid4().hex[:12], source=DataSource.FIRMS, rows_received=rows_received,
        rows_accepted=len(result.accepted), rows_flagged=result.flagged_count,
        rows_rejected=result.rejected_count, issues=result.issue_counts,
    )
    return result.accepted, record
