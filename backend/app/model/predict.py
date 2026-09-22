"""Prediction adapter: loads the trained Random Forest (training it once on
first use if no artifact exists yet, so the app never requires a manual
training step to start) and exposes a typed predict() over FeatureVector.
"""
from __future__ import annotations

from pathlib import Path
from threading import Lock

from app.config import get_settings
from app.model.ml_schemas import FEATURE_NAMES, FeatureVector
from app.model.schemas import MLClass, MLPrediction
from app.model.train import CLASS_A, MODEL_VERSION, train_and_evaluate

try:
    import joblib
except ImportError:  # pragma: no cover
    joblib = None

settings = get_settings()
_lock = Lock()
_model = None


def _get_model():
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:
            return _model
        artifact = Path(settings.model_artifact_path)
        if artifact.exists() and joblib is not None:
            _model = joblib.load(artifact)
        else:
            _model, _ = train_and_evaluate(save=True)
    return _model


def predict(event_id: str, features: FeatureVector) -> MLPrediction:
    model = _get_model()
    x = [features.as_list()]
    proba = model.predict_proba(x)[0]
    classes = list(model.classes_)
    p_a = float(proba[classes.index(CLASS_A)]) if CLASS_A in classes else 0.0
    p_b = 1.0 - p_a
    predicted = MLClass.PERSISTENT_INDUSTRIAL if p_a >= p_b else MLClass.NATURAL_CANDIDATE
    low_conf = max(p_a, p_b) < settings.ml_confidence_threshold
    importances = getattr(model, "feature_importances_", None)
    feature_importance = {n: float(i) for n, i in zip(FEATURE_NAMES, importances)} if importances is not None else {}

    return MLPrediction(
        event_id=event_id, p_persistent_industrial=round(p_a, 4), p_natural_candidate=round(p_b, 4),
        predicted_class=predicted, low_confidence=low_conf,
        feature_values=features.model_dump(), feature_importance=feature_importance,
        model_version=MODEL_VERSION, is_proxy_label_model=True,
    )
