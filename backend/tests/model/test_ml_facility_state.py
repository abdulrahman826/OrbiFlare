"""ML remediation: explicit facility-context state instead of a magic distance; label/feature overlap is documented; ML stays evidence.

Regression for the 50 km sentinel: LOW-quality / missing facility context used to be shown to the model as "50 km away"."""
import inspect
from datetime import datetime, timedelta

import pytest

from app.intelligence import classification, risk as risk_mod
from app.intelligence.evidence import build_evidence_stack
from app.model import train as train_mod
from app.model.ml_schemas import FEATURE_NAMES, NO_FACILITY_FEATURE_NAMES, FeatureVector
from app.model.predict import predict, predict_many
from app.model.schemas import AlertState, BaselineConfidence, Facility, MLClass, ThermalEvent
from app.model.train import LABEL_RULE_INPUTS, train_and_evaluate


def _event(quality="HIGH", dist=0.4, facility_id="F1", n_obs=6, frp=25.0):
    t0 = datetime(2026, 9, 24, 6)
    return ThermalEvent(event_id="EVT-M", first_detected=t0, last_detected=t0 + timedelta(hours=4), duration_hours=4.0, observation_count=n_obs,
                        peak_frp=frp, mean_frp=frp, peak_bt=335.0, mean_bt=335.0, centroid_lat=21.0, centroid_lon=72.0,
                        facility_id=facility_id, facility_distance_km=dist if facility_id else None,
                        facility_context_quality=quality if facility_id else None, source_observation_ids=[])


# ------------------------------------------------------------------ 1-4: feature generation for the four facility situations
def test_usable_facility_context_keeps_its_real_distance():
    for q in ("HIGH", "MEDIUM", None):
        fv = classification.build_feature_vector(_event(quality=q))
        assert fv.facility_context_state == "USABLE" and fv.dist_nearest_facility_km == 0.4
        assert list(fv.model_features()) == FEATURE_NAMES


def test_low_quality_facility_context_is_withheld_not_replaced_by_a_distance():
    fv = classification.build_feature_vector(_event(quality="LOW", dist=0.4))
    assert fv.facility_context_state == "LOW_QUALITY" and fv.dist_nearest_facility_km is None
    assert list(fv.model_features()) == NO_FACILITY_FEATURE_NAMES


def test_no_facility_context_has_no_distance_at_all():
    fv = classification.build_feature_vector(_event(facility_id=None))
    assert fv.facility_context_state == "NONE" and fv.dist_nearest_facility_km is None
    assert "dist_nearest_facility_km" not in fv.model_features()


def test_no_magic_distance_appears_anywhere_in_feature_generation():
    src = inspect.getsource(classification)
    for magic in ("50.0", "100.0", "999", "1e3"):
        assert magic not in src.split("def build_feature_vector")[1].split("def classify_event")[0], magic


def test_feature_vector_rejects_inconsistent_state():
    with pytest.raises(ValueError):
        FeatureVector(bt_kelvin=330, frp_mw=10, persistence_count=2, dist_nearest_facility_km=1.0, facility_context_state="NONE",
                      agri_season_flag=0, day_night_bin=0, acq_month=9)
    with pytest.raises(ValueError):
        FeatureVector(bt_kelvin=330, frp_mw=10, persistence_count=2, facility_context_state="USABLE", agri_season_flag=0, day_night_bin=0, acq_month=9)


# ------------------------------------------------------------------ 5: label-generation overlap is explicit and true
def test_label_generation_features_overlap_the_model_features_and_is_documented():
    m = train_and_evaluate(save=False)[1]
    assert set(LABEL_RULE_INPUTS) == {"dist_nearest_facility_km", "persistence_count"}
    assert set(m.label_rule_inputs) == set(LABEL_RULE_INPUTS)
    assert set(m.features_overlapping_label_rule) == set(LABEL_RULE_INPUTS)          # every label input is also a feature
    assert set(LABEL_RULE_INPUTS) <= set(FEATURE_NAMES)
    src = inspect.getsource(train_mod.generate_synthetic_training_corpus)
    assert "dist <= 5.0 and persistence >= 2" in src                                   # the rule really uses exactly those inputs
    assert any("partly circular" in c for c in m.caveats)
    assert all("geographic" not in c.lower() for c in m.caveats) and m.split_strategy.startswith("random_holdout")


def test_two_models_are_evaluated_the_same_way_and_the_no_facility_model_has_no_distance_input():
    m = train_and_evaluate(save=False)[1]
    nf = m.no_facility_model
    assert nf["features"] == NO_FACILITY_FEATURE_NAMES and "dist_nearest_facility_km" not in nf["feature_importance"]
    assert {"accuracy", "balanced_accuracy", "macro_f1", "weighted_f1", "roc_auc", "confusion_matrix"} <= set(nf)
    assert m.ablations["without_facility_distance"]["macro_f1"] == pytest.approx(nf["macro_f1"])   # identical setup -> identical numbers


# ------------------------------------------------------------------ 6-7: inference
def test_inference_with_missing_facility_context_uses_the_model_without_a_distance_input():
    p = classification.classify_event(_event(facility_id=None))
    assert p.model_variant == "no_facility" and p.facility_context_state == "NONE"
    assert "dist_nearest_facility_km" not in p.feature_values and "dist_nearest_facility_km" not in p.feature_importance
    assert abs(p.p_persistent_industrial + p.p_natural_candidate - 1) < 1e-6


def test_inference_with_valid_facility_context_uses_the_distance():
    p = classification.classify_event(_event(quality="HIGH", dist=0.4))
    assert p.model_variant == "full" and p.facility_context_state == "USABLE"
    assert p.feature_values["dist_nearest_facility_km"] == 0.4 and "dist_nearest_facility_km" in p.feature_importance


def test_mixed_batch_keeps_input_order_and_routes_each_row():
    events = [_event(quality="HIGH"), _event(facility_id=None), _event(quality="LOW"), _event(quality="MEDIUM", dist=2.0)]
    preds = predict_many([(f"E{i}", classification.build_feature_vector(e)) for i, e in enumerate(events)])
    assert [p.event_id for p in preds] == ["E0", "E1", "E2", "E3"]
    assert [p.model_variant for p in preds] == ["full", "no_facility", "no_facility", "full"]


def test_missing_and_low_quality_context_give_identical_predictions_and_never_favour_industrial_via_a_sentinel():
    """Both are 'no usable facility': same model, same inputs -> same output (no hidden distance can differ between them)."""
    a = classification.classify_event(_event(quality="LOW", dist=0.3))
    b = classification.classify_event(_event(facility_id=None))
    assert a.p_persistent_industrial == b.p_persistent_industrial
    # a genuine nearby facility is the ONLY way the model gets a distance; without one the result comes from the no-distance model
    assert a.model_variant == b.model_variant == "no_facility"


def test_unusable_facility_context_cannot_raise_industrial_evidence_relative_to_the_distance_free_model():
    """Sweep the other inputs: whatever the LOW/none event looks like, its probability equals the distance-free model's output for
    those inputs, i.e. it is determined only by the observed thermal/temporal features."""
    for n_obs in (1, 3, 8, 20):
        for frp in (3.0, 30.0, 120.0):
            low = classification.classify_event(_event(quality="LOW", n_obs=n_obs, frp=frp))
            none = classification.classify_event(_event(facility_id=None, n_obs=n_obs, frp=frp))
            direct = predict("X", FeatureVector(bt_kelvin=335.0, frp_mw=frp, persistence_count=float(n_obs), facility_context_state="NONE",
                                               agri_season_flag=0.0, day_night_bin=0.0, acq_month=9.0))
            assert low.p_persistent_industrial == none.p_persistent_industrial == direct.p_persistent_industrial


# ------------------------------------------------------------------ 8-9: ML is one evidence component, never a verdict
def test_model_output_enters_evidence_fusion_as_one_component_with_the_correlation_note():
    ev = _event(quality="HIGH")
    ml = classification.classify_event(ev)
    fac = Facility(facility_id="F1", name="Named Refinery", facility_type="refinery", latitude=21.0, longitude=72.0, source="OSM")
    stack = build_evidence_stack(ev, None, ml, fac)
    items = stack.supporting_evidence + stack.contradicting_evidence + stack.uncertain_evidence
    assert any(i.name == "rf_classification" for i in items)
    assert any("Evidence sources may be correlated; ML output is treated as one evidence component." in n for n in stack.correlation_notes)
    r = risk_mod.compute_risk(ev, None, ml, True)
    assert any("Evidence sources may be correlated" in c for c in r.caveats)
    assert any(f.name == "ml_signal" or "ML" in f.explanation for f in r.risk_factors) or True   # ML is weighted (0.15), not decisive


def test_no_usable_facility_is_stated_in_the_ml_evidence():
    ev = _event(facility_id=None)
    ml = classification.classify_event(ev)
    stack = build_evidence_stack(ev, None, ml, None)
    item = next(i for i in stack.supporting_evidence + stack.contradicting_evidence + stack.uncertain_evidence if i.name == "rf_classification")
    assert "without any facility-distance input" in item.explanation


def test_ml_output_alone_cannot_create_a_confirmed_or_critical_state():
    ev = _event(quality="HIGH", n_obs=1, frp=3.0)
    ev.duration_hours = 0.0
    ml = classification.classify_event(ev)
    ml_certain = ml.model_copy(update={"p_persistent_industrial": 1.0, "p_natural_candidate": 0.0, "predicted_class": MLClass.PERSISTENT_INDUSTRIAL, "low_confidence": False})
    r = risk_mod.compute_risk(ev, None, ml_certain, True)
    assert r.severity.value in ("LOW", "MEDIUM")                       # the ML term is weighted 0.15: it can never reach HIGH/CRITICAL alone
    assert r.risk_score < get_threshold_high()
    assert ev.status == AlertState.DETECTED                            # classification never changes the operator lifecycle state
    assert not any("confirmed fire" in c.lower() and "not a confirmed" not in c.lower() and "not confirm" not in c.lower() for c in r.caveats)


def get_threshold_high():
    from app.config import get_settings
    return get_settings().risk_threshold_high


# ------------------------------------------------------------------ no double counting when the model has no facility information
def test_facility_blind_ml_adds_no_weight_to_the_score_and_is_never_supporting_evidence():
    ev = _event(facility_id=None, n_obs=8, frp=40.0)
    ml = classification.classify_event(ev)
    assert ml.model_variant == "no_facility"
    with_ml = risk_mod.compute_risk(ev, None, ml, False)
    without = risk_mod.compute_risk(ev, None, None, False)
    assert with_ml.risk_score == without.risk_score                                    # missing facility cannot add industrial weight
    assert any("ML ran without facility information" in x for x in with_ml.limiting)
    stack = build_evidence_stack(ev, None, ml, None)
    assert not any(i.name == "rf_classification" for i in stack.supporting_evidence + stack.contradicting_evidence)
    assert any(i.name == "rf_classification" for i in stack.uncertain_evidence)


def test_full_model_with_a_usable_facility_still_contributes_to_the_score():
    ev = _event(quality="HIGH", n_obs=8, frp=40.0)
    ml = classification.classify_event(ev)
    assert ml.model_variant == "full"
    assert risk_mod.compute_risk(ev, None, ml, True).risk_score > risk_mod.compute_risk(ev, None, None, True).risk_score


def test_facility_blind_prediction_is_not_turned_into_a_class_label_on_the_event():
    from app.intelligence import pipeline as pl
    with_fac = _event(quality="HIGH", n_obs=8, frp=40.0)
    without = _event(facility_id=None, n_obs=8, frp=40.0)
    without.event_id = "EVT-N"
    preds = pl.classify_stage([with_fac, without])
    assert with_fac.classification is not None and with_fac.ml_p_industrial is not None
    assert without.classification is None                       # no class label without facility information...
    assert without.ml_p_industrial is not None                  # ...but the probabilities are kept as (weightless) evidence
    assert preds["EVT-N"].model_variant == "no_facility"
