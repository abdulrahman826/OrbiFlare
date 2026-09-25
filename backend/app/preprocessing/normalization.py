"""Normalize heterogeneous raw source rows (FIRMS CSV/JSON, demo fixtures)
into the internal ThermalObservation schema.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any

from app.model.schemas import DataSource, DayNight, QualityFlag, Sensor, ThermalObservation


def stable_observation_id(source: str, lat: float, lon: float, ts: datetime, sensor: str) -> str:
    key = f"{source}|{sensor}|{round(lat, 5)}|{round(lon, 5)}|{ts.isoformat()}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def parse_firms_timestamp(acq_date: str, acq_time: Any) -> datetime | None:
    """FIRMS gives acq_date=YYYY-MM-DD and acq_time=HHMM (int/str, zero-padded)."""
    try:
        date_part = datetime.strptime(acq_date.strip(), "%Y-%m-%d")
    except Exception:
        return None
    try:
        t = str(int(acq_time)).zfill(4)
        hour, minute = int(t[:2]), int(t[2:])
        if hour > 23 or minute > 59:
            return None
        return date_part + timedelta(hours=hour, minutes=minute)
    except Exception:
        # Timestamp couldn't be parsed precisely; caller flags as interpolated
        return date_part


def normalize_firms_row(row: dict, sensor: Sensor) -> tuple[ThermalObservation | None, list[str]]:
    """Normalize one raw FIRMS CSV row (as dict) into a ThermalObservation.

    Returns (observation_or_none, issue_codes). Only returns None when the
    row is unusable even as a flagged record (no coordinates or timestamp).
    """
    issues: list[str] = []
    try:
        lat = float(row.get("latitude"))
        lon = float(row.get("longitude"))
    except (TypeError, ValueError):
        return None, ["missing_coordinates"]

    ts = parse_firms_timestamp(str(row.get("acq_date", "")), row.get("acq_time", "0000"))
    if ts is None:
        return None, ["missing_timestamp"]
    if row.get("acq_time") is None:
        issues.append(QualityFlag.INTERPOLATED_TIMESTAMP.value)

    def _float(key: str) -> float | None:
        v = row.get(key)
        if v in (None, "", "NaN"):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    frp = _float("frp")
    bt = _float("bright_ti4") or _float("brightness")
    bt11 = _float("bright_ti5") or _float("bright_t31")
    if frp is None:
        issues.append(QualityFlag.MISSING_FRP.value)
    if bt is None:
        issues.append(QualityFlag.MISSING_BT.value)

    dn_raw = str(row.get("daynight", "")).upper()
    day_night = DayNight.DAY if dn_raw.startswith("D") else (DayNight.NIGHT if dn_raw.startswith("N") else None)

    confidence = row.get("confidence")
    confidence_str = str(confidence) if confidence not in (None, "") else None
    if confidence_str in ("l", "low", "0"):
        issues.append(QualityFlag.LOW_CONFIDENCE.value)

    satellite = (str(row.get("satellite") or "").strip() or None)
    # Identity = FIRMS fields (source, sensor, lat, lon, acquisition time). The satellite is added to the key only when it is
    # not NOAA-21, so observations stored before satellites were recorded (all from the NOAA-21 product) keep their ids.
    key_sensor = sensor.value if satellite in (None, "N21") else f"{sensor.value}|{satellite}"
    obs_id = stable_observation_id("FIRMS", lat, lon, ts, key_sensor)
    obs = ThermalObservation(
        observation_id=obs_id, timestamp=ts, latitude=lat, longitude=lon, sensor=sensor,
        brightness_temperature=bt, brightness_temperature_11=bt11, frp=frp,
        confidence=confidence_str, day_night=day_night, source=DataSource.FIRMS,
        source_id=str(row.get("source_id") or obs_id), quality_flags=[QualityFlag(i) for i in issues],
        satellite=satellite, instrument=(str(row.get("instrument") or "").strip() or None),
        scan=_float("scan"), track=_float("track"),
    )
    return obs, issues
