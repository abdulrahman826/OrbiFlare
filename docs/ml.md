# Machine Learning

Code: `backend/app/model/` (train.py, predict.py, evaluate.py, ml_schemas.py) + `backend/app/intelligence/classification.py` (the adapter that turns an event into a feature vector and calls the model).

## Classes (exactly two)

- `PERSISTENT_INDUSTRIAL_THERMAL_SOURCE` ("Class A")
- `NATURAL_AGRICULTURAL_FIRE_CANDIDATE` ("Class B" -- a *candidate*, not a confirmed wildfire/burn label)

There is deliberately no third "confirmed industrial fire" class. If `max(P(A), P(B)) < ML_CONFIDENCE_THRESHOLD` (default 0.55), the prediction is flagged `low_confidence=True` and downstream consumers treat it as a weak anomaly-candidate signal, never a classification verdict.

## Features

`bt_kelvin`, `frp_mw`, `persistence_count`, `dist_nearest_facility_km`, `agri_season_flag` (Indian agri-burn months: Apr/May/Oct/Nov), `day_night_bin`, `acq_month` -- all derived from the event + its facility context (`classification.py::build_feature_vector`).

## Training data: PROXY LABELS, not ground truth

**There is no verified real-world industrial-fire dataset in this build.** `train.py::generate_synthetic_training_corpus()` generates a synthetic population and labels it with a documented heuristic:

```
label = PERSISTENT_INDUSTRIAL if (dist_nearest_facility_km <= 5.0 and persistence_count >= 2) else NATURAL_AGRICULTURAL_CANDIDATE
```

...then deliberately injects ~16% label noise and ~20-25% multiplicative feature noise, specifically so the resulting metrics don't overstate what a heuristic-derived proxy label can prove. This corpus is entirely separate from the 4-facility DEMO/SYNTHETIC scenario used to walk through the UI -- it exists only to fit the classifier's decision boundary.

`EvaluationMetrics.is_proxy_label_model = True` and `.caveats[]` travel with every prediction and are surfaced on the frontend Model page, the Analytics page, and every Investigation's ML Evidence panel.

## Training & validation (`train.py::train_and_evaluate`)

- `RandomForestClassifier(n_estimators=200, max_depth=8, min_samples_leaf=5, class_weight="balanced")`.
- **Geographic holdout**, not a random row split: samples are tagged with a synthetic `region_id` (0-9), and regions 8-9 are held out entirely from training -- a sanity check that the model isn't just memorizing spatial coincidences in the training population.
- Reports: accuracy, per-class precision/recall/F1, ROC-AUC, confusion matrix, feature importance -- all computed on the (unseen) holdout regions, saved to `data/rf_metrics.json` and served via `GET /api/analytics/risk` and the Model page.
- Class imbalance handled via `class_weight="balanced"` (the synthetic corpus is close to 50/50 by construction, but the noise injection can skew it slightly).

## Prediction (`predict.py`)

Loads the saved model (`data/rf_model.joblib`), training it once on first use if no artifact exists yet -- the app never requires a manual `python train.py` step to start. `predict()` returns a typed `MLPrediction` with both class probabilities, the predicted class, the `low_confidence` flag, the feature values used, and per-feature importances.

## Where ML sits in the bigger picture

The classifier is **one evidence signal among several** (see `evidence.py`), fused alongside behavioural deviation and facility context -- never the sole basis for risk or a "fire detected" claim. `risk.py` weights the ML signal at only 15% of the composite risk score. The Evidence Fusion layer also explicitly flags the correlation between the ML signal and the intensity-deviation signal (both driven substantially by FRP), so they are never read as two independent confirmations.

## Extensibility (not built, but designed for)

`app/model/ml_schemas.py::FEATURE_NAMES` and the `MLClass` enum are the two places a future verified-ground-truth model would extend: additional classes (ROUTINE_FLARE, CONFIRMED_INDUSTRIAL_FIRE, AGRICULTURAL_BURN, WILDFIRE, MINING, UNKNOWN) and additional features (FRP/BT trend, spatial movement, weather, higher-resolution imagery context) slot into the same `classify_event() -> MLPrediction` contract without changing any downstream consumer (evidence, risk, alternative explanations all just read `MLPrediction`).
