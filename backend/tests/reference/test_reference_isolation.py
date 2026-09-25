"""Structural guarantee: reference data cannot leak into training, feature engineering or the operational pipeline."""
from __future__ import annotations

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"
FORBIDDEN_IN = ("model", "intelligence", "ingestion", "preprocessing", "storage", "alerts")
PATTERN = re.compile(r"app\.reference|from app import reference|data/reference|confirmed_incidents_india|india_admin")


def test_ml_and_pipeline_packages_never_reference_reference_data():
    offenders = []
    for pkg in FORBIDDEN_IN:
        for path in (APP / pkg).rglob("*.py"):
            if PATTERN.search(path.read_text(encoding="utf-8")):
                offenders.append(str(path.relative_to(APP)))
    assert offenders == [], f"reference data must not be used by: {offenders}"


def test_reference_package_does_not_write_to_the_database():
    for path in (APP / "reference").rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        assert not re.search(r"\b(db|session)\.(add|add_all|commit|delete|merge|execute|flush)\(", src), path.name


def test_training_feature_schema_has_no_incident_columns():
    from app.model import ml_schemas
    text = Path(ml_schemas.__file__).read_text(encoding="utf-8").lower()
    assert "incident" not in text
