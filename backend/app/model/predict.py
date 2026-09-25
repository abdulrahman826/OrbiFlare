"""Prediction adapter: loads the trained Random Forest (training it once on
first use if no artifact exists yet, so the app never requires a manual
training step to start) and exposes a typed predict() over FeatureVector.
"""
from __future__ import annotations

from pathlib import Path
from threading import Lock

from app.config import get_settings
from app.model.ml_schemas import FACILITY_NONE, FEATURE_NAMES, NO_FACILITY_FEATURE_NAMES, FeatureVector
from app.model.schemas import MLClass, MLPrediction
from app.model.train import CLASS_A, MODEL_VERSION, no_facility_artifact_path, train_and_evaluate

try:
    import joblib
except ImportError:  # pragma: no cover
    joblib = None

settings = get_settings()
_lock = Lock()
_models: dict[str, object] = {}
FULL, NO_FACILITY = "full", "no_facility"


def _get_model(variant: str = FULL):
    """variant FULL: all features (identified facility nearby). NO_FACILITY: the facility-distance feature is absent."""
    if variant in _models:
        return _models[variant]
    with _lock:
        if variant in _models:
            return _models[variant]
        artifacts = {FULL: Path(settings.model_artifact_path), NO_FACILITY: no_facility_artifact_path()}
        if joblib is not None and all(p.exists() for p in artifacts.values()):
            _models.update({k: joblib.load(p) for k, p in artifacts.items()})
        else:
            train_and_evaluate(save=True)
            if joblib is not None and all(p.exists() for p in artifacts.values()):
                _models.update({k: joblib.load(p) for k, p in artifacts.items()})
            else:  # pragma: no cover - joblib unavailable: train in memory
                raise RuntimeError("Model artifacts could not be created")
    return _models[variant]


_importance_cache: dict[int, dict[str, float]] = {}


def _feature_importance(model, names) -> dict[str, float]:
    """RandomForest.feature_importances_ re-averages every tree on each access (tens of ms); it never changes for a fitted model."""
    key = id(model)
    if key not in _importance_cache:
        imp = getattr(model, "feature_importances_", None)
        _importance_cache[key] = {n: float(v) for n, v in zip(names, imp)} if imp is not None else {}
    return _importance_cache[key]


def predict_many(items: list[tuple[str, FeatureVector]]) -> list[MLPrediction]:
    """Same per-row result as predict(), but one predict_proba call per model variant (rows are independent).

    Routing is by facility context state: a usable facility -> the FULL model with the real distance; anything else (LOW quality
    generic record, or nothing nearby) -> the NO-FACILITY model, which has no distance input at all."""
    if not items:
        return []
    out: list[MLPrediction | None] = [None] * len(items)
    for variant, names in ((FULL, FEATURE_NAMES), (NO_FACILITY, NO_FACILITY_FEATURE_NAMES)):
        idx = [i for i, (_, f) in enumerate(items) if f.facility_usable == (variant == FULL)]
        if not idx:
            continue
        model = _get_model(variant)
        rows = [items[i][1].as_list() if variant == FULL else items[i][1].as_list_without_facility() for i in idx]
        proba = model.predict_proba(rows)
        classes = list(model.classes_)
        importance = _feature_importance(model, names)
        for i, row in zip(idx, proba):
            event_id, features = items[i]
            p_a = float(row[classes.index(CLASS_A)]) if CLASS_A in classes else 0.0
            p_b = 1.0 - p_a
            predicted = MLClass.PERSISTENT_INDUSTRIAL if p_a >= p_b else MLClass.NATURAL_CANDIDATE
            out[i] = MLPrediction(
                event_id=event_id, p_persistent_industrial=round(p_a, 4), p_natural_candidate=round(p_b, 4),
                predicted_class=predicted, low_confidence=max(p_a, p_b) < settings.ml_confidence_threshold,
                feature_values=features.model_features(), feature_importance=dict(importance),
                model_version=MODEL_VERSION, is_proxy_label_model=True,
                facility_context_state=features.facility_context_state or FACILITY_NONE, model_variant=variant,
            )
    return out  # type: ignore[return-value]


def predict(event_id: str, features: FeatureVector) -> MLPrediction:
    return predict_many([(event_id, features)])[0]
