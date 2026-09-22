"""Centralized, environment-driven configuration for the whole backend.

Every threshold that the intelligence layer uses (clustering radius, baseline
minimums, risk cutoffs, ...) lives here so behaviour can be tuned without
touching pipeline code, per the "single source of configuration" requirement.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ---
    database_url: str = f"sqlite:///{(BACKEND_ROOT / 'data' / 'orbiflare.db').as_posix()}"

    # --- App mode ---
    orbiflare_mode: str = "demo"  # "demo" | "real"

    # --- FIRMS ingestion ---
    firms_map_key: str = ""
    firms_api_base: str = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

    # --- Event clustering (Thermal Event Engine) ---
    event_spatial_radius_km: float = 1.5
    event_temporal_gap_hours: float = 12.0

    # --- Thermal twin baseline confidence thresholds ---
    baseline_min_observations_limited: int = 3
    baseline_min_observations_established: int = 8
    baseline_min_events_established: int = 4

    # --- Deviation thresholds (in "robust z-score" units, i.e. multiples of MAD) ---
    deviation_notable_threshold: float = 1.5
    deviation_significant_threshold: float = 3.0

    # --- Risk thresholds (0-100 composite score -> severity) ---
    risk_threshold_medium: float = 35.0
    risk_threshold_high: float = 60.0
    risk_threshold_critical: float = 80.0

    # --- ML ---
    ml_confidence_threshold: float = 0.55
    model_artifact_path: str = str(BACKEND_ROOT / "data" / "rf_model.joblib")

    # --- Networking ---
    api_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def data_dir(self) -> Path:
        return BACKEND_ROOT / "data"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
