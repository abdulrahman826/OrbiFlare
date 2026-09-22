"""Row-level validation for raw ingested thermal observation records.

Nothing here silently discards data: every row that fails a check is
returned alongside the specific reason so the caller (ingestion layer) can
decide to flag vs. reject, and so the decision is auditable via
DataQualityRecord.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RowValidationResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)


def validate_coordinates(lat: float | None, lon: float | None) -> RowValidationResult:
    if lat is None or lon is None:
        return RowValidationResult(False, ["missing_coordinates"])
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        return RowValidationResult(False, ["out_of_range_coordinates"])
    if lat == 0.0 and lon == 0.0:
        return RowValidationResult(False, ["null_island_coordinates"])
    return RowValidationResult(True)


def validate_timestamp(ts: datetime | None) -> RowValidationResult:
    if ts is None:
        return RowValidationResult(False, ["missing_timestamp"])
    if ts.year < 2000 or ts > datetime.utcnow().replace(year=datetime.utcnow().year + 1):
        return RowValidationResult(False, ["implausible_timestamp"])
    return RowValidationResult(True)


def validate_thermal_fields(frp: float | None, bt: float | None) -> RowValidationResult:
    reasons: list[str] = []
    if frp is None:
        reasons.append("missing_frp")
    elif frp < 0 or frp > 5000:
        reasons.append("frp_out_of_plausible_range")
    if bt is None:
        reasons.append("missing_bt")
    elif bt < 200 or bt > 500:
        reasons.append("bt_out_of_plausible_range")
    # Missing thermal fields are flagged, not fatal — a row can still anchor
    # an event on coordinates/time alone.
    return RowValidationResult(True, reasons)
