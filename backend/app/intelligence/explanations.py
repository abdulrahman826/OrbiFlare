"""Enforced phrasing helpers so the "no fabrication / scientific honesty"
rules (never "confirmed fire", never "facility caused it", never "will
become a fire") are applied consistently wherever free text is generated.
"""
from __future__ import annotations

SCIENTIFIC_HONESTY_BANNED_PHRASES = [
    "confirmed fire", "detected a fire", "facility caused", "caused by the facility",
    "will become a fire", "fire probability",
]


def describe_observation_source(sensor: str) -> str:
    return f"{sensor} detected thermal activity"  # never "detected a fire"


def describe_facility_context(facility_name: str, distance_km: float) -> str:
    return f"{facility_name} is located approximately {distance_km:.2f} km from the event"  # never "belongs to"


def describe_risk_trend(direction: str) -> str:
    if direction == "ESCALATING":
        return "Observed risk has increased consistently during the event"
    if direction == "INCREASING":
        return "Observed risk has trended upward during the event"
    if direction == "DECREASING":
        return "Observed risk has declined during the event"
    if direction == "STABLE":
        return "Observed risk has remained stable during the event"
    return "Not enough data exists yet to characterize a risk trend"
