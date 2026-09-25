from app.model.ml_schemas import FeatureVector
from app.model.predict import predict
from app.model.schemas import MLClass
from app.model.train import CLASS_A, CLASS_B, generate_synthetic_training_corpus, train_and_evaluate


def test_training_corpus_has_only_two_classes():
    _, y, _ = generate_synthetic_training_corpus(n=200)
    assert set(y.tolist()) == {CLASS_A, CLASS_B}


def test_train_and_evaluate_produces_metrics_with_proxy_label_caveats():
    _, metrics = train_and_evaluate(save=False)
    assert metrics.is_proxy_label_model is True
    assert len(metrics.caveats) >= 2
    assert set(metrics.precision.keys()) == {CLASS_A, CLASS_B}
    assert metrics.split_strategy.startswith("random_holdout")


def test_prediction_probabilities_sum_to_one():
    features = FeatureVector(bt_kelvin=330, frp_mw=25, persistence_count=3, dist_nearest_facility_km=1.0,
                              agri_season_flag=0.0, day_night_bin=1.0, acq_month=6)
    pred = predict("E1", features)
    assert abs((pred.p_persistent_industrial + pred.p_natural_candidate) - 1.0) < 1e-6
    assert pred.predicted_class in (MLClass.PERSISTENT_INDUSTRIAL, MLClass.NATURAL_CANDIDATE)


def test_low_confidence_flag_set_when_probabilities_are_close():
    # Ambiguous feature vector: moderate distance, moderate persistence.
    features = FeatureVector(bt_kelvin=320, frp_mw=15, persistence_count=2, dist_nearest_facility_km=6.0,
                              agri_season_flag=0.0, day_night_bin=0.0, acq_month=3)
    pred = predict("E2", features)
    max_p = max(pred.p_persistent_industrial, pred.p_natural_candidate)
    assert pred.low_confidence == (max_p < 0.55)


def test_model_is_two_class_only_no_fabricated_third_class():
    _, metrics = train_and_evaluate(save=False)
    assert len(metrics.confusion_matrix.labels) == 2
