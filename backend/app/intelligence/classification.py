"""Bridges a ThermalEvent into the ML feature space and calls the Random
Forest adapter. The model is ONE evidence signal among several (deviation,
facility context, ...) -- see app/intelligence/evidence.py and risk.py for
how it's combined. This module never treats p(industrial) as a final
verdict.
"""
from __future__ import annotations

from app.model.ml_schemas import FACILITY_LOW_QUALITY, FACILITY_NONE, FACILITY_USABLE, FeatureVector
from app.model.predict import predict, predict_many
from app.model.train import AGRI_MONTHS
from app.model.schemas import MLPrediction, ThermalEvent


def facility_state(event: ThermalEvent) -> str:
    """Which facility information may the ML layer see? An identified facility (quality HIGH/MEDIUM, or an unclassified legacy record)
    is usable; a generic land-use record (LOW) is context only and is withheld; no facility is simply absent."""
    if event.facility_distance_km is None:
        return FACILITY_NONE
    if event.facility_context_quality == "LOW":
        return FACILITY_LOW_QUALITY
    return FACILITY_USABLE


def build_feature_vector(event: ThermalEvent) -> FeatureVector:
    month = event.first_detected.month
    hour = event.first_detected.hour
    is_night = 1.0 if (hour >= 18 or hour < 6) else 0.0
    state = facility_state(event)
    return FeatureVector(
        bt_kelvin=event.peak_bt or event.mean_bt or 300.0,
        frp_mw=event.peak_frp or event.mean_frp or 5.0,
        persistence_count=float(event.observation_count),
        # No made-up distance for "no usable facility": the distance is None and the model routed to has no such input.
        dist_nearest_facility_km=event.facility_distance_km if state == FACILITY_USABLE else None,
        facility_context_state=state,
        agri_season_flag=1.0 if month in AGRI_MONTHS else 0.0,
        day_night_bin=is_night,
        acq_month=float(month),
    )


def classify_event(event: ThermalEvent) -> MLPrediction:
    features = build_feature_vector(event)
    return predict(event.event_id, features)


_MEMO: dict[tuple, MLPrediction] = {}
_MEMO_MAX = 200_000


def classify_events(events: list[ThermalEvent]) -> list[MLPrediction]:
    """Batch form of classify_event (identical per-event results, one model call for everything not seen before).

    Memoised on (event id, feature vector): an event id is a hash of its observation ids, so the same key always means the same
    inputs and therefore the same prediction. This lets the pipeline classify every trajectory prefix of every event in ONE call."""
    vectors = [build_feature_vector(e) for e in events]
    keys = [(e.event_id, tuple(v.model_features().items())) for e, v in zip(events, vectors)]
    missing = {k: (e.event_id, v) for k, e, v in zip(keys, events, vectors) if k not in _MEMO}
    if missing:
        if len(_MEMO) + len(missing) > _MEMO_MAX:
            _MEMO.clear()
        for k, pred in zip(missing, predict_many(list(missing.values()))):
            _MEMO[k] = pred
    return [_MEMO[k] for k in keys]
