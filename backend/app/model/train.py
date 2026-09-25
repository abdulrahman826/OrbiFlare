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
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from app.config import get_settings
from app.model.ml_schemas import FACILITY_FEATURE, FEATURE_NAMES, NO_FACILITY_FEATURE_NAMES, ConfusionMatrix, EvaluationMetrics

try:
    import joblib
except ImportError:  # pragma: no cover
    joblib = None

settings = get_settings()

CLASS_A = "PERSISTENT_INDUSTRIAL_THERMAL_SOURCE"
CLASS_B = "NATURAL_AGRICULTURAL_FIRE_CANDIDATE"
MODEL_VERSION = "rf-proxy-v2"
# Signals used to CREATE the development labels (see generate_synthetic_training_corpus). Every one of them is also a model feature.
LABEL_RULE_INPUTS = ("dist_nearest_facility_km", "persistence_count")
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


def no_facility_artifact_path() -> Path:
    base = Path(settings.model_artifact_path)
    return base.with_name(base.stem + "_no_facility" + base.suffix)


def _fit(X, y):
    return RandomForestClassifier(n_estimators=200, max_depth=8, min_samples_leaf=5, class_weight="balanced", random_state=42).fit(X, y)


def _evaluate(clf, X_val, y_val, labels_sorted) -> dict:
    y_pred = clf.predict(X_val)
    y_proba = clf.predict_proba(X_val)
    a_idx = list(clf.classes_).index(CLASS_A)
    precision = precision_score(y_val, y_pred, labels=labels_sorted, average=None, zero_division=0)
    recall = recall_score(y_val, y_pred, labels=labels_sorted, average=None, zero_division=0)
    f1 = f1_score(y_val, y_pred, labels=labels_sorted, average=None, zero_division=0)
    try:
        roc_auc = float(roc_auc_score((y_val == CLASS_A).astype(int), y_proba[:, a_idx]))
    except ValueError:
        roc_auc = None
    return {
        "accuracy": float((y_pred == y_val).mean()), "balanced_accuracy": float(balanced_accuracy_score(y_val, y_pred)),
        "macro_f1": float(f1_score(y_val, y_pred, average="macro")), "weighted_f1": float(f1_score(y_val, y_pred, average="weighted")),
        "roc_auc": roc_auc, "precision": {labels_sorted[i]: float(precision[i]) for i in range(2)},
        "recall": {labels_sorted[i]: float(recall[i]) for i in range(2)}, "f1": {labels_sorted[i]: float(f1[i]) for i in range(2)},
        "confusion_matrix": confusion_matrix(y_val, y_pred, labels=labels_sorted).tolist(),
    }


def train_and_evaluate(save: bool = True) -> tuple[RandomForestClassifier, EvaluationMetrics]:
    """Trains the two models of the evidence layer from the same development corpus, split and hyper-parameters:

      * FULL model (all 7 features) -- used when an identified facility (HIGH/MEDIUM context quality) is nearby;
      * NO-FACILITY model (the facility-distance feature is absent) -- used when facility context is missing or LOW quality.

    Nothing is fabricated to represent "no facility": the second model simply does not have that input."""
    X, y, regions = generate_synthetic_training_corpus()

    # Random hold-out: rows whose region id is 8 or 9 (~20%). The region id is drawn independently of every feature and label,
    # so this is NOT a spatial hold-out and is not described as one.
    val_mask = np.isin(regions, [8, 9])
    X_train, y_train = X[~val_mask], y[~val_mask]
    X_val, y_val = X[val_mask], y[val_mask]
    labels_sorted = [CLASS_A, CLASS_B]
    nf_cols = [i for i, n in enumerate(FEATURE_NAMES) if n != FACILITY_FEATURE]

    clf = _fit(X_train, y_train)
    full = _evaluate(clf, X_val, y_val, labels_sorted)
    clf_nf = _fit(X_train[:, nf_cols], y_train)
    nf = _evaluate(clf_nf, X_val[:, nf_cols], y_val, labels_sorted)
    nf["features"] = NO_FACILITY_FEATURE_NAMES
    nf["feature_importance"] = {n: float(v) for n, v in zip(NO_FACILITY_FEATURE_NAMES, clf_nf.feature_importances_)}

    def ablate(drop: str) -> dict:
        cols = [i for i, n in enumerate(FEATURE_NAMES) if n != drop]
        m = _evaluate(_fit(X_train[:, cols], y_train), X_val[:, cols], y_val, labels_sorted)
        return {"macro_f1": m["macro_f1"], "accuracy": m["accuracy"], "balanced_accuracy": m["balanced_accuracy"]}

    metrics = EvaluationMetrics(
        model_version=MODEL_VERSION, trained_at=datetime.utcnow().isoformat(),
        n_train=len(X_train), n_val=len(X_val), split_strategy="random_holdout(20% of rows)",
        accuracy=full["accuracy"], precision=full["precision"], recall=full["recall"], f1=full["f1"], roc_auc=full["roc_auc"],
        balanced_accuracy=full["balanced_accuracy"], macro_f1=full["macro_f1"], weighted_f1=full["weighted_f1"],
        confusion_matrix=ConfusionMatrix(labels=labels_sorted, matrix=full["confusion_matrix"]),
        feature_importance={name: float(imp) for name, imp in zip(FEATURE_NAMES, clf.feature_importances_)},
        is_proxy_label_model=True,
        label_rule_inputs=list(LABEL_RULE_INPUTS),
        features_overlapping_label_rule=[n for n in FEATURE_NAMES if n in LABEL_RULE_INPUTS],
        no_facility_model=nf,
        ablations={"without_facility_distance": ablate(FACILITY_FEATURE), "without_persistence": ablate("persistence_count"),
                   "note": "Same corpus, split and settings; evaluation only. The production models are the two above."},
        caveats=[
            "Development labels come from a documented heuristic (facility proximity <= 5 km and persistence >= 2, plus injected label noise) on generated "
            "development data -- NOT verified real-world outcomes.",
            "The reported scores describe how well the model recovers that labelling heuristic on a random hold-out. They are not real-world fire-detection "
            "accuracy and must not be read as one.",
            "The labelling heuristic uses facility distance and persistence, which are also model features: the score is partly circular, and the model is "
            "evidence, not independent confirmation.",
            "This is a 2-class model only: persistent industrial thermal source vs. natural/agricultural fire candidate. It does not output a "
            "confirmed-industrial-fire class.",
        ],
    )

    if save and joblib is not None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(clf, settings.model_artifact_path)
        joblib.dump(clf_nf, no_facility_artifact_path())
        with open(settings.data_dir / "rf_metrics.json", "w", encoding="utf-8") as f:
            json.dump(metrics.model_dump(), f, indent=2)

    return clf, metrics


if __name__ == "__main__":
    _, m = train_and_evaluate()
    print(json.dumps(m.model_dump(), indent=2))
