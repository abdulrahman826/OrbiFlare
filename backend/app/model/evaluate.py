"""Read-only accessor for the last-computed model evaluation metrics, used
by the /api endpoints and the frontend Model page. Trains (once) if no
metrics file exists yet.
"""
from __future__ import annotations

import json

from app.config import get_settings
from app.model.ml_schemas import EvaluationMetrics
from app.model.train import train_and_evaluate

settings = get_settings()


def get_latest_metrics() -> EvaluationMetrics:
    metrics_path = settings.data_dir / "rf_metrics.json"
    if metrics_path.exists():
        return EvaluationMetrics.model_validate(json.loads(metrics_path.read_text(encoding="utf-8")))
    _, metrics = train_and_evaluate(save=True)
    return metrics
