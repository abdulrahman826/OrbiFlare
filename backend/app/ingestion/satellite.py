"""Satellite imagery adapter interface.

OrbiFlare's evidence/replay layers reference imagery context (e.g. "no
direct visual confirmation" is a standing uncertainty item). No imagery
provider is wired up in this build -- this module defines the abstraction so
one (Sentinel Hub, Planet, etc.) can be plugged in later without touching
callers, and returns an honest UNAVAILABLE result today.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class SatelliteImageryResult:
    available: bool
    thumbnail_url: str | None = None
    acquired_at: datetime | None = None
    provider: str | None = None
    reason: str | None = "No satellite imagery provider is configured in this deployment."


def get_imagery_for_location(lat: float, lon: float, around: datetime) -> SatelliteImageryResult:
    return SatelliteImageryResult(available=False)
