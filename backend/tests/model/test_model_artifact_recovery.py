"""Regression test for the production FIRMS-refresh failure: a truncated/corrupt on-disk model artifact (left behind
by a process killed mid-write, since joblib.dump is not atomic) made `joblib.load` raise EOFError, which crashed the
entire FIRMS refresh -- observations included, since ingestion and ML re-classification share one transaction that
rolls back on any exception. The fix must detect a corrupt artifact, remove it, and let the caller retrain instead of
propagating the read error; and saving must be atomic so a killed process can never leave a corrupt file again."""
from pathlib import Path

import joblib

from app.model import predict as predict_mod
from app.model import train as train_mod


def test_corrupt_artifact_is_detected_removed_and_reported_as_unloadable(tmp_path):
    full = tmp_path / "rf_model.joblib"
    no_facility = tmp_path / "rf_model_no_facility.joblib"
    # Simulate a process killed mid-`joblib.dump`: a short, non-pickle file at the expected path.
    full.write_bytes(b"truncated")
    no_facility.write_bytes(b"truncated")
    artifacts = {predict_mod.FULL: full, predict_mod.NO_FACILITY: no_facility}

    ok = predict_mod._load_artifacts(artifacts)

    assert ok is False
    # Removed so a subsequent retrain-and-save doesn't hit the same corrupt file again.
    assert not full.exists()
    assert not no_facility.exists()


def test_missing_artifact_is_reported_as_unloadable_without_touching_anything(tmp_path):
    artifacts = {predict_mod.FULL: tmp_path / "missing.joblib", predict_mod.NO_FACILITY: tmp_path / "missing2.joblib"}
    assert predict_mod._load_artifacts(artifacts) is False


def test_valid_artifact_loads_successfully(tmp_path):
    path = tmp_path / "rf_model.joblib"
    joblib.dump({"trained": True}, path)
    artifacts = {predict_mod.FULL: path}
    ok = predict_mod._load_artifacts(artifacts)
    assert ok is True
    assert predict_mod._models[predict_mod.FULL] == {"trained": True}
    predict_mod._models.pop(predict_mod.FULL, None)  # don't leak into other tests


def test_atomic_dump_never_leaves_a_partial_file_at_the_real_path(tmp_path):
    target = tmp_path / "rf_model.joblib"
    train_mod._atomic_dump({"ok": True}, target)
    assert target.exists()
    assert joblib.load(target) == {"ok": True}
    # No leftover temp file after a successful save.
    assert list(tmp_path.iterdir()) == [target]


def test_get_model_recovers_from_a_corrupt_artifact_by_retraining(tmp_path, monkeypatch):
    full = tmp_path / "rf_model.joblib"
    full.write_bytes(b"truncated")
    monkeypatch.setattr(predict_mod.settings, "model_artifact_path", str(full))
    monkeypatch.setattr(predict_mod, "no_facility_artifact_path", lambda: tmp_path / "rf_model_no_facility.joblib")
    predict_mod._models.pop(predict_mod.FULL, None)
    predict_mod._models.pop(predict_mod.NO_FACILITY, None)

    model = predict_mod._get_model(predict_mod.FULL)

    assert model is not None
    assert full.exists()  # retraining saved a fresh, valid artifact in place of the corrupt one
    predict_mod._models.pop(predict_mod.FULL, None)
    predict_mod._models.pop(predict_mod.NO_FACILITY, None)
