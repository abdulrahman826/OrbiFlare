"""Typed schemas for the ML layer: feature vectors, training examples, and
evaluation metrics. Kept separate from model/schemas.py (the domain model)
to avoid confusing "ML model" with "domain model".
"""
from __future__ import annotations

from pydantic import BaseModel

FEATURE_NAMES = [
    "bt_kelvin", "frp_mw", "persistence_count", "dist_nearest_facility_km",
    "agri_season_flag", "day_night_bin", "acq_month",
]


class FeatureVector(BaseModel):
    bt_kelvin: float
    frp_mw: float
    persistence_count: float
    dist_nearest_facility_km: float
    agri_season_flag: float  # 1.0 if acq_month in typical Indian agri-burn months (Oct-Nov, Apr-May), else 0.0
    day_night_bin: float     # 1.0 = night, 0.0 = day
    acq_month: float

    def as_list(self) -> list[float]:
        return [getattr(self, name) for name in FEATURE_NAMES]


class TrainingExample(BaseModel):
    features: FeatureVector
    label: str  # MLClass value
    is_proxy_label: bool = True


class ConfusionMatrix(BaseModel):
    labels: list[str]
    matrix: list[list[int]]


class EvaluationMetrics(BaseModel):
    model_version: str
    trained_at: str
    n_train: int
    n_val: int
    split_strategy: str
    accuracy: float
    precision: dict[str, float]
    recall: dict[str, float]
    f1: dict[str, float]
    roc_auc: float | None
    confusion_matrix: ConfusionMatrix
    feature_importance: dict[str, float]
    is_proxy_label_model: bool = True
    caveats: list[str] = []
