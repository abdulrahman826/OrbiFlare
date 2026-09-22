"""Random Forest training for the two-class thermal-source classifier.

CLASS A = PERSISTENT_INDUSTRIAL_THERMAL_SOURCE
CLASS B = NATURAL_AGRICULTURAL_FIRE_CANDIDATE  ("_candidate" -- this is not a
confirmed wildfire/burn label)

============================ IMPORTANT CAVEAT =============================
There is no ground-truth industrial-fire dataset available in this build.
Training examples are generated from a documented PROXY-LABEL heuristic
(facility proximity + persistence + thermal intensity + seasonality), not
verified real-world outcomes. Label noise is injected deliberately so the
reported metrics do not overstate real-world accuracy. This is surfaced
everywhere the model's output is shown (is_proxy_label_model=True,
EvaluationMetrics.caveats, the frontend Model page, and docs/ml.md).
=============================================================================
"""
from __future__ import annotations

import json
from datetime import datetime

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from app.config import get_settings
from app.model.ml_schemas import FEATURE_NAMES, ConfusionMatrix, EvaluationMetrics

try:
    import joblib
except ImportError:  # pragma: no cover
    joblib = None

settings = get_settings()

CLASS_A = "PERSISTENT_INDUSTRIAL_THERMAL_SOURCE"
CLASS_B = "NATURAL_AGRICULTURAL_FIRE_CANDIDATE"
MODEL_VERSION = "rf-proxy-v1"
AGRI_MONTHS = {4, 5, 10, 11}


def generate_synthetic_training_corpus(n: int = 1400, seed: int = 7) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns (X, y, region_id) for a synthetic, proxy-labelled population
    used ONLY to fit the classifier -- unrelated to the 4-facility demo
    scenario used to walk through the UI.
    """
    rng = np.random.default_rng(seed)
    rows = []
    labels = []
    regions = []

    for _ in range(n):
        region_id = int(rng.integers(0, 10))
        is_industrial_world = rng.random() < 0.5

        if is_industrial_world:
            dist = float(np.clip(rng.exponential(2.5), 0.05, 40))
            persistence = float(rng.integers(1, 15))
            frp = float(np.clip(rng.normal(35, 20), 3, 250))
            bt = float(np.clip(rng.normal(335, 15), 290, 420))
            month = int(rng.integers(1, 13))
            day_night = float(rng.choice([0, 1], p=[0.35, 0.65]))
        else:
            dist = float(np.clip(rng.exponential(18), 2, 120))
            persistence = float(rng.integers(1, 4))
            frp = float(np.clip(rng.normal(14, 10), 1, 90))
            bt = float(np.clip(rng.normal(315, 12), 290, 400))
            month = int(rng.choice(list(AGRI_MONTHS) + [rng.integers(1, 13)]))
            day_night = float(rng.choice([0, 1], p=[0.7, 0.3]))

        agri_flag = 1.0 if month in AGRI_MONTHS else 0.0
        proxy_label = CLASS_A if (dist <= 5.0 and persistence >= 2) else CLASS_B

        # Deliberate label noise: proxy heuristic is not ground truth.
        if rng.random() < 0.16:
            proxy_label = CLASS_B if proxy_label == CLASS_A else CLASS_A
        # Feature noise so the boundary isn't a trivial threshold rule.
        dist *= float(rng.normal(1.0, 0.25))
        frp *= float(rng.normal(1.0, 0.2))

        rows.append([bt, frp, persistence, max(dist, 0.01), agri_flag, day_night, month])
        labels.append(proxy_label)
        regions.append(region_id)

    return np.array(rows, dtype=float), np.array(labels), np.array(regions)


def train_and_evaluate(save: bool = True) -> tuple[RandomForestClassifier, EvaluationMetrics]:
    X, y, regions = generate_synthetic_training_corpus()

    # Geographic holdout: regions 8-9 are held out entirely from training,
    # not just row-randomly split, to sanity-check spatial generalisation.
    val_mask = np.isin(regions, [8, 9])
    X_train, y_train = X[~val_mask], y[~val_mask]
    X_val, y_val = X[val_mask], y[val_mask]

    clf = RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_leaf=5,
        class_weight="balanced", random_state=42,
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_val)
    y_proba = clf.predict_proba(X_val)
    classes = list(clf.classes_)
    a_idx = classes.index(CLASS_A)

    labels_sorted = [CLASS_A, CLASS_B]
    cm = confusion_matrix(y_val, y_pred, labels=labels_sorted)
    precision = precision_score(y_val, y_pred, labels=labels_sorted, average=None, zero_division=0)
    recall = recall_score(y_val, y_pred, labels=labels_sorted, average=None, zero_division=0)
    f1 = f1_score(y_val, y_pred, labels=labels_sorted, average=None, zero_division=0)
    try:
        roc_auc = float(roc_auc_score((y_val == CLASS_A).astype(int), y_proba[:, a_idx]))
    except ValueError:
        roc_auc = None

    metrics = EvaluationMetrics(
        model_version=MODEL_VERSION, trained_at=datetime.utcnow().isoformat(),
        n_train=len(X_train), n_val=len(X_val), split_strategy="geographic_holdout(regions 8-9)",
        accuracy=float((y_pred == y_val).mean()),
        precision={labels_sorted[i]: float(precision[i]) for i in range(2)},
        recall={labels_sorted[i]: float(recall[i]) for i in range(2)},
        f1={labels_sorted[i]: float(f1[i]) for i in range(2)},
        roc_auc=roc_auc,
        confusion_matrix=ConfusionMatrix(labels=labels_sorted, matrix=cm.tolist()),
        feature_importance={name: float(imp) for name, imp in zip(FEATURE_NAMES, clf.feature_importances_)},
        is_proxy_label_model=True,
        caveats=[
            "Trained on synthetic, proxy-labelled data (facility proximity + persistence + intensity + "
            "seasonality heuristic with injected label noise) -- NOT verified real-world fire outcomes.",
            "Reported metrics describe how well the model recovers the proxy-labelling heuristic on a "
            "geographic holdout, not real-world industrial-fire detection accuracy.",
            "This is a 2-class model only: persistent industrial thermal source vs. natural/agricultural "
            "fire candidate. It does not output a 3rd 'confirmed industrial fire' class.",
        ],
    )

    if save and joblib is not None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(clf, settings.model_artifact_path)
        with open(settings.data_dir / "rf_metrics.json", "w", encoding="utf-8") as f:
            json.dump(metrics.model_dump(), f, indent=2)

    return clf, metrics


if __name__ == "__main__":
    _, m = train_and_evaluate()
    print(json.dumps(m.model_dump(), indent=2))
