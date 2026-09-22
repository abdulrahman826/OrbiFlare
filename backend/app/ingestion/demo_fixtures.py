"""DEMO / SYNTHETIC data generator.

This module produces the ONLY fabricated data anywhere in OrbiFlare: raw
facilities and raw thermal observations for a clearly labelled demonstration
scenario ("ORBIFLARE DEMO -- ESCALATING REFINERY THERMAL EVENT" plus three
supporting scenarios). Every downstream artifact -- events, thermal twins,
deviation, evidence, risk, trajectory -- is COMPUTED by the real pipeline
from these raw points. Nothing downstream of this module is hand-authored;
we only fabricate the satellite-observation-shaped inputs, never the
analysis.

All records produced here carry is_demo=True / source=DEMO so the UI can
render an unmistakable "DEMO / SYNTHETIC" badge and the API can exclude them
from a "real data only" view.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

import numpy as np

from app.model.schemas import DataSource, DayNight, Facility, Sensor, ThermalObservation

KM_PER_DEG_LAT = 111.0


def _km_to_deg(lat: float, dlat_km: float, dlon_km: float) -> tuple[float, float]:
    dlat = dlat_km / KM_PER_DEG_LAT
    dlon = dlon_km / (KM_PER_DEG_LAT * math.cos(math.radians(lat)))
    return dlat, dlon


def _obs_id(prefix: str, i: int) -> str:
    return f"DEMO-{prefix}-{i:04d}"


def _make_obs(prefix: str, i: int, ts: datetime, lat: float, lon: float, frp: float,
              bt: float, sensor: Sensor = Sensor.SYNTHETIC, day_night: DayNight = DayNight.NIGHT) -> ThermalObservation:
    return ThermalObservation(
        observation_id=_obs_id(prefix, i), timestamp=ts, latitude=lat, longitude=lon,
        sensor=sensor, brightness_temperature=bt, brightness_temperature_11=bt - 8,
        frp=frp, confidence="n" if sensor != Sensor.SYNTHETIC else "demo",
        day_night=day_night, source=DataSource.DEMO, source_id=_obs_id(prefix, i),
    )


def generate_demo_dataset(seed: int = 42, now: datetime | None = None) -> tuple[list[Facility], list[ThermalObservation]]:
    rng = np.random.default_rng(seed)
    now = now or datetime.utcnow()

    facilities: list[Facility] = []
    observations: list[ThermalObservation] = []

    # ------------------------------------------------------------------
    # Facility 1: Synthetic Refinery Alpha -- flagship ESCALATING scenario
    # ------------------------------------------------------------------
    fac_alpha = Facility(
        facility_id="FAC-REF-ALPHA", name="Synthetic Refinery Alpha", facility_type="oil_refinery",
        industry="Petroleum Refining", latitude=22.3200, longitude=69.8500, source="DEMO",
        country="IN", state="Gujarat", region="Saurashtra Industrial Belt", is_demo=True,
    )
    facilities.append(fac_alpha)

    # Historical baseline: ~24 routine flaring events over the past ~11 months
    # in a tight "Zone A" footprint, FRP 20-40 MW, duration 1-2h, 2-4 obs each,
    # concentrated 21:00-02:00 IST (~15:30-20:30 UTC).
    n_hist_events = 24
    for e in range(n_hist_events):
        days_ago = 330 - e * 13 - int(rng.integers(0, 4))
        base_ts = now - timedelta(days=days_ago, hours=float(rng.uniform(-1, 1)))
        base_ts = base_ts.replace(hour=int(rng.integers(15, 19)), minute=int(rng.integers(0, 59)))
        n_obs = int(rng.integers(2, 5))
        for i in range(n_obs):
            dlat_km, dlon_km = rng.normal(0, 0.12, 2)
            dlat, dlon = _km_to_deg(fac_alpha.latitude, dlat_km, dlon_km)
            frp = float(np.clip(rng.normal(28, 5), 18, 42))
            bt = float(np.clip(rng.normal(332, 6), 315, 350))
            ts = base_ts + timedelta(minutes=int(i * rng.integers(20, 55)))
            observations.append(_make_obs(f"ALPHA-H{e}", i, ts, fac_alpha.latitude + dlat, fac_alpha.longitude + dlon, frp, bt))

    # Current event: displaced ~1.9km into "Zone C", 11 observations over 6h,
    # FRP escalating 45 -> 118 MW, BT elevated, spanning into daytime hours
    # (temporal deviation vs. the 21:00-02:00 historical pattern).
    zone_c_dlat, zone_c_dlon = _km_to_deg(fac_alpha.latitude, 1.35, 1.05)
    current_start = now - timedelta(hours=6)
    frp_curve = [45, 52, 61, 74, 83, 91, 98, 104, 110, 115, 118]
    for i, frp_val in enumerate(frp_curve):
        ts = current_start + timedelta(minutes=i * 33)
        dlat_km, dlon_km = rng.normal(0, 0.15, 2)
        lat = fac_alpha.latitude + zone_c_dlat + (dlat_km / KM_PER_DEG_LAT)
        lon = fac_alpha.longitude + zone_c_dlon + (dlon_km / (KM_PER_DEG_LAT * math.cos(math.radians(fac_alpha.latitude))))
        bt = float(np.clip(340 + frp_val * 0.19 + rng.normal(0, 3), 330, 400))
        dn = DayNight.NIGHT if (ts.hour >= 15 or ts.hour < 1) else DayNight.DAY
        observations.append(_make_obs("ALPHA-CUR", i, ts, lat, lon, float(frp_val), bt, day_night=dn))

    # ------------------------------------------------------------------
    # Facility 2: Synthetic Steel Plant Beta -- STABLE / matches baseline
    # ------------------------------------------------------------------
    fac_beta = Facility(
        facility_id="FAC-STEEL-BETA", name="Synthetic Steel Plant Beta", facility_type="steel_plant",
        industry="Steel & Metallurgy", latitude=22.8046, longitude=86.2029, source="DEMO",
        country="IN", state="Jharkhand", region="Chhotanagpur Industrial Belt", is_demo=True,
    )
    facilities.append(fac_beta)

    n_hist_beta = 20
    for e in range(n_hist_beta):
        days_ago = 300 - e * 14 - int(rng.integers(0, 4))
        base_ts = now - timedelta(days=days_ago)
        base_ts = base_ts.replace(hour=int(rng.integers(14, 20)), minute=int(rng.integers(0, 59)))
        n_obs = int(rng.integers(2, 4))
        for i in range(n_obs):
            dlat_km, dlon_km = rng.normal(0, 0.10, 2)
            dlat, dlon = _km_to_deg(fac_beta.latitude, dlat_km, dlon_km)
            frp = float(np.clip(rng.normal(22, 4), 14, 30))
            bt = float(np.clip(rng.normal(326, 5), 312, 340))
            ts = base_ts + timedelta(minutes=int(i * rng.integers(15, 40)))
            observations.append(_make_obs(f"BETA-H{e}", i, ts, fac_beta.latitude + dlat, fac_beta.longitude + dlon, frp, bt))

    # Current event: consistent with baseline -> should resolve LOW / STABLE.
    current_start_b = now - timedelta(hours=2)
    for i, frp_val in enumerate([19, 23, 25]):
        ts = current_start_b + timedelta(minutes=i * 35)
        dlat_km, dlon_km = rng.normal(0, 0.10, 2)
        dlat, dlon = _km_to_deg(fac_beta.latitude, dlat_km, dlon_km)
        bt = float(np.clip(rng.normal(327, 4), 315, 340))
        observations.append(_make_obs("BETA-CUR", i, ts, fac_beta.latitude + dlat, fac_beta.longitude + dlon, float(frp_val), bt))

    # ------------------------------------------------------------------
    # Facility 3: Synthetic Chemical Plant Gamma -- INSUFFICIENT baseline
    # ------------------------------------------------------------------
    fac_gamma = Facility(
        facility_id="FAC-CHEM-GAMMA", name="Synthetic Chemical Plant Gamma", facility_type="chemical_plant",
        industry="Petrochemicals", latitude=22.3072, longitude=73.1812, source="DEMO",
        country="IN", state="Gujarat", region="Vadodara Industrial Belt", is_demo=True,
    )
    facilities.append(fac_gamma)

    # Only one historical event with 2 observations -- not enough for even a
    # LIMITED baseline. The twin/deviation layers must surface INSUFFICIENT.
    base_ts_g = now - timedelta(days=200, hours=3)
    for i in range(2):
        dlat_km, dlon_km = rng.normal(0, 0.1, 2)
        dlat, dlon = _km_to_deg(fac_gamma.latitude, dlat_km, dlon_km)
        observations.append(_make_obs("GAMMA-H0", i, base_ts_g + timedelta(minutes=i * 30),
                                       fac_gamma.latitude + dlat, fac_gamma.longitude + dlon, 26.0, 330.0))

    current_start_g = now - timedelta(hours=3)
    frp_curve_g = [38, 47, 55, 60, 58, 60]
    for i, frp_val in enumerate(frp_curve_g):
        ts = current_start_g + timedelta(minutes=i * 30)
        dlat_km, dlon_km = rng.normal(0, 0.12, 2)
        dlat, dlon = _km_to_deg(fac_gamma.latitude, dlat_km, dlon_km)
        bt = float(np.clip(335 + frp_val * 0.15 + rng.normal(0, 2), 325, 370))
        observations.append(_make_obs("GAMMA-CUR", i, ts, fac_gamma.latitude + dlat, fac_gamma.longitude + dlon, float(frp_val), bt))

    # ------------------------------------------------------------------
    # Unassociated event: rural area, no facility nearby -> natural/agri
    # burn candidate. Short, daytime, low FRP, single-ish detection cluster.
    # ------------------------------------------------------------------
    agri_lat, agri_lon = 20.9200, 78.3100  # Vidarbha agricultural belt, no facility fixture nearby
    agri_start = now - timedelta(hours=1, minutes=10)
    for i, frp_val in enumerate([9.0, 11.5, 8.0]):
        ts = agri_start + timedelta(minutes=i * 18)
        dlat_km, dlon_km = rng.normal(0, 0.3, 2)
        dlat, dlon = _km_to_deg(agri_lat, dlat_km, dlon_km)
        bt = float(np.clip(rng.normal(315, 4), 305, 325))
        observations.append(_make_obs("AGRI", i, ts, agri_lat + dlat, agri_lon + dlon, frp_val, bt, day_night=DayNight.DAY))

    return facilities, observations


DEMO_SCENARIO_LABEL = "DEMO SCENARIO -- SYNTHETIC DATA (not a NASA FIRMS observation)"
