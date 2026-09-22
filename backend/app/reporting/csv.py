from __future__ import annotations

import csv
import io

from app.model.schemas import ThermalEvent


def events_to_csv(events: list[ThermalEvent]) -> str:
    buf = io.StringIO()
    fieldnames = [
        "event_id", "first_detected", "last_detected", "duration_hours", "observation_count",
        "peak_frp", "mean_frp", "peak_bt", "mean_bt", "centroid_lat", "centroid_lon",
        "facility_id", "facility_distance_km", "status", "classification", "ml_p_industrial",
        "ml_p_natural", "risk_score", "severity", "trajectory_direction", "is_demo",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for e in events:
        row = e.model_dump()
        writer.writerow({k: row.get(k) for k in fieldnames})
    return buf.getvalue()
