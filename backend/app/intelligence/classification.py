"""Bridges a ThermalEvent into the ML feature space and calls the Random
Forest adapter. The model is ONE evidence signal among several (deviation,
facility context, ...) -- see app/intelligence/evidence.py and risk.py for
how it's combined. This module never treats p(industrial) as a final
verdict.
"""
from __future__ import annotations

from app.model.ml_schemas import FeatureVector
from app.model.predict import predict
from app.model.train import AGRI_MONTHS
from app.model.schemas import MLPrediction, ThermalEvent


def build_feature_vector(event: ThermalEvent) -> FeatureVector:
    month = event.first_detected.month
    hour = event.first_detected.hour
    is_night = 1.0 if (hour >= 18 or hour < 6) else 0.0
    return FeatureVector(
        bt_kelvin=event.peak_bt or event.mean_bt or 300.0,
        frp_mw=event.peak_frp or event.mean_frp or 5.0,
        persistence_count=float(event.observation_count),
        dist_nearest_facility_km=event.facility_distance_km if event.facility_distance_km is not None else 50.0,
        agri_season_flag=1.0 if month in AGRI_MONTHS else 0.0,
        day_night_bin=is_night,
        acq_month=float(month),
    )


def classify_event(event: ThermalEvent) -> MLPrediction:
    features = build_feature_vector(event)
    return predict(event.event_id, features)
