"""Scientific hardening: baseline evidence policy, facility-context quality, ML/facility overlap, risk explanation."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.config import get_settings
from app.context.facilities import context_quality
from app.intelligence import classification, risk as risk_mod
from app.intelligence.deviation import _insufficient
from app.intelligence.evidence import build_evidence_stack
from app.intelligence.trajectory import compute_trajectory
from app.model.schemas import (
    BaselineConfidence, DataSource, Deviation, DimensionDeviation, DeviationStatus, Facility, MLClass, MLPrediction, Sensor,
    Severity, ThermalEvent, ThermalObservation,
)

W_DEV = 0.35


def _event(n_obs=3, dur=2.0, frp=20.0, facility_id="F1", dist=0.4, quality="HIGH"):
    t0 = datetime(2026, 9, 24, 6)
    return ThermalEvent(event_id="EVT-T", first_detected=t0, last_detected=t0 + timedelta(hours=dur), duration_hours=dur, observation_count=n_obs,
                        peak_frp=frp, mean_frp=frp, peak_bt=330.0, mean_bt=330.0, centroid_lat=21.0, centroid_lon=72.0,
                        facility_id=facility_id, facility_distance_km=dist if facility_id else None,
                        facility_context_quality=quality if facility_id else None, source_observation_ids=[])


def _dev(baseline, overall=100.0):
    dims = {n: _insufficient(n, "test") for n in ("intensity", "persistence", "duration", "temporal", "spatial", "recurrence")}
    return Deviation(event_id="EVT-T", facility_id="F1", baseline_confidence=baseline, overall_deviation_score=overall, explanations=[], **dims)


def _ml(p=0.6, low=False):
    return MLPrediction(event_id="EVT-T", p_persistent_industrial=p, p_natural_candidate=1 - p, predicted_class=MLClass.PERSISTENT_INDUSTRIAL,
                        low_confidence=low, model_version="rf-proxy-v1")


# ----------------------------------------------------------------------------- baseline evidence policy

def test_established_counts_fully_limited_is_capped_insufficient_is_zero():
    ev = _event()
    est = risk_mod.compute_risk(ev, _dev(BaselineConfidence.ESTABLISHED), _ml(), True)
    lim = risk_mod.compute_risk(ev, _dev(BaselineConfidence.LIMITED), _ml(), True)
    ins = risk_mod.compute_risk(ev, _dev(BaselineConfidence.INSUFFICIENT), _ml(), True)
    none = risk_mod.compute_risk(ev, None, _ml(), True)
    factor = get_settings().risk_limited_baseline_factor
    assert est.deviation_contribution == pytest.approx(100 * W_DEV)                       # 35 points: full weight
    assert lim.deviation_contribution == pytest.approx(100 * W_DEV * factor)              # discounted
    assert lim.deviation_contribution <= lim.deviation_contribution_cap == pytest.approx(100 * W_DEV * factor)
    assert lim.deviation_contribution < est.deviation_contribution
    assert ins.deviation_contribution == 0.0 and ins.deviation_contribution_cap == 0.0
    assert ins.risk_score == none.risk_score                                             # a "deviation" from no baseline changes nothing
    assert est.risk_score > lim.risk_score > ins.risk_score


def test_a_limited_baseline_can_never_exceed_its_configured_cap_whatever_the_deviation(monkeypatch):
    for f in (0.1, 0.25, 0.4, 0.5):
        monkeypatch.setattr(get_settings(), "risk_limited_baseline_factor", f)
        cap = 100 * W_DEV * f
        for dev in (0, 25, 50, 100):
            r = risk_mod.compute_risk(_event(), _dev(BaselineConfidence.LIMITED, dev), _ml(), True)
            assert r.deviation_contribution <= cap + 1e-9 and r.deviation_contribution_cap == pytest.approx(cap)


def test_insufficient_baseline_contributes_zero_even_if_a_deviation_score_were_supplied():
    r = risk_mod.compute_risk(_event(), _dev(BaselineConfidence.INSUFFICIENT, 100.0), _ml(), True)
    assert r.deviation_contribution == 0.0
    assert not any(f.name == "behaviour_deviation" for f in r.risk_factors)
    assert r.baseline_status == "INSUFFICIENT" and any("insufficient baseline" in x for x in r.limiting)


def test_limited_history_cannot_by_itself_reach_a_tier_that_an_established_baseline_would():
    ev = _event(n_obs=1, dur=0.0, frp=3.0)
    est = risk_mod.compute_risk(ev, _dev(BaselineConfidence.ESTABLISHED), _ml(0.5), True)
    lim = risk_mod.compute_risk(ev, _dev(BaselineConfidence.LIMITED), _ml(0.5), True)
    assert est.severity in (Severity.MEDIUM, Severity.HIGH) and lim.severity == Severity.LOW


# ----------------------------------------------------------------------------- facility context quality

@pytest.mark.parametrize("ftype,name,expected", [
    ("industrial", "", "LOW"), ("industrial", "Some Industrial Estate", "LOW"), ("depot", "Bus Depot", "LOW"), ("warehouse", "X", "LOW"),
    ("refinery", "Reliance Refinery", "HIGH"), ("Coal", "Korba TPP", "HIGH"), ("cement", "ACC Cement", "HIGH"),
    ("brickyard", "", "MEDIUM"), ("brickyard", "Shree Bricks", "HIGH"), ("slaughterhouse", "Municipal", "MEDIUM"), ("", "x", "LOW"),
])
def test_context_quality_uses_only_the_record_itself(ftype, name, expected):
    assert context_quality(ftype, name, "OSM")[0] == expected


def test_low_quality_context_is_not_counted_as_facility_evidence():
    high = risk_mod.compute_risk(_event(quality="HIGH"), None, _ml(), True)
    low = risk_mod.compute_risk(_event(quality="LOW"), None, _ml(), True)
    legacy = risk_mod.compute_risk(_event(quality=None), None, _ml(), True)       # synthetic/legacy events keep the old behaviour
    assert high.risk_score - low.risk_score == pytest.approx(15 * 0.10, abs=0.11)
    assert legacy.risk_score == high.risk_score
    assert any("weak facility context" in x for x in low.limiting) and not any("weak facility context" in x for x in high.limiting)


def test_generic_land_use_is_not_shown_to_the_ml_as_an_industrial_facility():
    near = dict(dist=0.3)
    assert classification.build_feature_vector(_event(quality="HIGH", **near)).dist_nearest_facility_km == 0.3
    assert classification.build_feature_vector(_event(quality=None, **near)).dist_nearest_facility_km == 0.3
    # No made-up distance (the old 50 km sentinel is gone): the distance is absent and the state says why.
    low = classification.build_feature_vector(_event(quality="LOW", **near))
    none = classification.build_feature_vector(_event(facility_id=None))
    assert low.dist_nearest_facility_km is None and low.facility_context_state == "LOW_QUALITY"
    assert none.dist_nearest_facility_km is None and none.facility_context_state == "NONE"


# ----------------------------------------------------------------------------- explanation content

def test_low_event_explains_why_and_what_would_raise_it_without_predicting_anything():
    r = risk_mod.compute_risk(_event(n_obs=1, dur=0.0, frp=2.0, facility_id=None), _dev(BaselineConfidence.INSUFFICIENT), _ml(0.2), False)
    assert r.severity == Severity.LOW and "below the MEDIUM threshold" in r.severity_reason
    assert any("no relevant facility context" in x and "does not indicate a natural fire" in x for x in r.limiting)
    assert any("no independent incident confirmation" in x for x in r.limiting)
    assert r.escalation_evidence and all(x.split()[0] in ("more", "longer", "higher", "an") for x in r.escalation_evidence)
    assert "an identified facility within the context radius" in r.escalation_evidence
    assert "independent confirmation of an incident" in r.missing_evidence
    blob = " ".join(r.contributing + r.limiting + r.missing_evidence + r.escalation_evidence + r.caveats + [r.severity_reason]).lower()
    import re
    for banned in ("will become", "fire caused", "refinery fire", "caused by the facility"):
        assert banned not in blob
    assert not re.search(r"(?<!not )(?<!not a )confirmed fire", blob.replace("not a confirmed fire", ""))   # only denials of "confirmed fire" are allowed


def test_medium_event_lists_what_contributes_and_what_limits():
    r = risk_mod.compute_risk(_event(n_obs=10, dur=30.0, frp=30.0), _dev(BaselineConfidence.LIMITED, 50), _ml(0.5), True)
    assert r.severity == Severity.MEDIUM
    text = " | ".join(r.contributing)
    assert "persistent observations" in text and "sustained duration" in text and "limited facility baseline" in text.lower()
    assert any("limited baseline" in x and "insufficient history for strong behavioural inference" in x for x in r.limiting)
    assert r.baseline_status == "LIMITED" and r.facility_context_quality == "HIGH"


def test_ml_overlap_with_facility_and_persistence_is_disclosed_in_risk_and_evidence():
    r = risk_mod.compute_risk(_event(), _dev(BaselineConfidence.ESTABLISHED, 10), _ml(), True)
    assert any("proxy labels derived from facility proximity" in c and "not independent confirmation" in c for c in r.caveats)
    fac = Facility(facility_id="F1", name="X", facility_type="refinery", latitude=21.0, longitude=72.0, source="OSM")
    stack = build_evidence_stack(_event(), _dev(BaselineConfidence.ESTABLISHED, 10), _ml(), fac)
    assert any("partially overlaps" in n and "independent confirmation" in n for n in stack.correlation_notes)
    item = next(i for i in stack.uncertain_evidence if i.name == "facility_proximity")
    assert "spatial CONTEXT only" in item.explanation and "high-quality context" in item.explanation


def test_no_facility_evidence_wording_never_implies_a_natural_fire():
    stack = build_evidence_stack(_event(facility_id=None), None, _ml(), None)
    item = next(i for i in stack.unavailable_evidence if i.name == "facility_proximity_unavailable")
    assert "does not indicate a natural fire" in item.explanation


# ----------------------------------------------------------------------------- trajectory / replay stay consistent with the policy

def _obs(i, minutes, frp):
    return ThermalObservation(observation_id=f"P{i}", timestamp=datetime(2026, 9, 24, 6) + timedelta(minutes=minutes), latitude=21.0, longitude=72.0,
                              sensor=Sensor.VIIRS, frp=frp, brightness_temperature=330.0, source=DataSource.FIRMS, day_night="D")


def test_trajectory_uses_the_same_facility_quality_policy_as_the_stored_risk():
    obs = [_obs(i, i * 60, 10.0 + i) for i in range(5)]
    hi, _ = compute_trajectory(obs, None, "F1", 0.3, "EVT-T", "HIGH")
    lo, _ = compute_trajectory(obs, None, "F1", 0.3, "EVT-T", "LOW")
    legacy, _ = compute_trajectory(obs, None, "F1", 0.3, "EVT-T")
    assert lo.points[-1].risk_score < hi.points[-1].risk_score            # LOW context is not counted, and the ML no longer sees the facility
    assert legacy.points[-1].risk_score == hi.points[-1].risk_score      # unclassified (legacy/synthetic) keeps previous behaviour
