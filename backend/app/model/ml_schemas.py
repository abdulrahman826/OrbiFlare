"""Typed schemas for the ML layer: feature vectors, training examples, and
evaluation metrics. Kept separate from model/schemas.py (the domain model)
to avoid confusing "ML model" with "domain model".
"""
from __future__ import annotations

from pydantic import BaseModel, model_validator

FEATURE_NAMES = [
    "bt_kelvin", "frp_mw", "persistence_count", "dist_nearest_facility_km",
    "agri_season_flag", "day_night_bin", "acq_month",
]
FACILITY_FEATURE = "dist_nearest_facility_km"
# Features of the model used when there is NO usable facility context: the facility feature is simply absent (not set to a
# made-up distance), so "no facility information" is never read as "a facility is N km away".
NO_FACILITY_FEATURE_NAMES = [n for n in FEATURE_NAMES if n != FACILITY_FEATURE]
FEATURE_SCHEMA_VERSION = "2"

# Facility context state presented to the ML layer.
FACILITY_USABLE = "USABLE"            # identified (HIGH/MEDIUM quality) facility within the search radius -> distance is a real feature
FACILITY_LOW_QUALITY = "LOW_QUALITY"  # only a generic land-use record nearby -> not usable as evidence, distance withheld
FACILITY_NONE = "NONE"                # nothing within the search radius


class FeatureVector(BaseModel):
    bt_kelvin: float
    frp_mw: float
    persistence_count: float
    dist_nearest_facility_km: float | None = None    # None whenever facility context is not usable
    facility_context_state: str | None = None        # USABLE | LOW_QUALITY | NONE (derived from the distance when not given)
    agri_season_flag: float  # 1.0 if acq_month in typical Indian agri-burn months (Oct-Nov, Apr-May), else 0.0
    day_night_bin: float     # 1.0 = night, 0.0 = day
    acq_month: float

    @model_validator(mode="after")
    def _state(self):
        if self.facility_context_state is None:
            self.facility_context_state = FACILITY_USABLE if self.dist_nearest_facility_km is not None else FACILITY_NONE
        if self.facility_context_state == FACILITY_USABLE and self.dist_nearest_facility_km is None:
            raise ValueError("USABLE facility context requires a distance")
        if self.facility_context_state != FACILITY_USABLE and self.dist_nearest_facility_km is not None:
            raise ValueError("a distance must not be supplied when facility context is not usable")
        return self

    @property
    def facility_usable(self) -> bool:
        return self.facility_context_state == FACILITY_USABLE

    def as_list(self) -> list[float]:
        """Full feature row (requires usable facility context)."""
        return [getattr(self, name) for name in FEATURE_NAMES]

    def as_list_without_facility(self) -> list[float]:
        return [getattr(self, name) for name in NO_FACILITY_FEATURE_NAMES]

    def model_features(self) -> dict[str, float]:
        """Exactly the features the routed model sees (the facility distance is absent, not defaulted, when unusable)."""
        names = FEATURE_NAMES if self.facility_usable else NO_FACILITY_FEATURE_NAMES
        return {n: float(getattr(self, n)) for n in names}


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
    balanced_accuracy: float | None = None
    macro_f1: float | None = None
    weighted_f1: float | None = None
    evaluation_kind: str = "Development-set evaluation (random hold-out)"
    feature_schema_version: str = FEATURE_SCHEMA_VERSION
    label_rule_inputs: list[str] = []          # signals used to CREATE the development labels
    features_overlapping_label_rule: list[str] = []
    no_facility_model: dict | None = None      # same evaluation for the model used when facility context is not usable
    ablations: dict | None = None
