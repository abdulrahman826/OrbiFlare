"""Source interpretation: conservative candidate labels from an evidence stack. Descriptive only; never a fire confirmation or a risk input."""
from datetime import datetime, timedelta

import pytest

from app.agent import runtime
from app.intelligence import source_interpretation as si
from app.model.schemas import Facility, MLClass, Severity, ThermalEvent, TrajectoryDirection
from app.storage import repositories as repo


def _ev(obs=3, dur=1.0, facility=True, quality="HIGH", month=9, ml=None, frp=10.0, dist=0.8):
    t0 = datetime(2026, month, 10, 6)
    return ThermalEvent(event_id="EVT-INT0000001", first_detected=t0, last_detected=t0 + timedelta(hours=dur), duration_hours=dur, observation_count=obs, peak_frp=frp, mean_frp=frp,
                        centroid_lat=22.3, centroid_lon=69.8, facility_id="F1" if facility else None, facility_distance_km=dist if facility else None,
                        facility_context_quality=quality if facility else None, classification=ml, source_observation_ids=[])


A, B = MLClass.PERSISTENT_INDUSTRIAL, MLClass.NATURAL_CANDIDATE


def test_industrial_source_candidate_needs_facility_and_behaviour_and_carries_evidence():
    r = si.interpret(_ev(obs=8, dur=7.0, ml=A), facility_type="oil_refinery", history_events=5)
    assert r.classification == si.INDUSTRIAL and r.strength in ("MODERATE", "HIGH")
    names = {x["signal"] for x in r.supporting}
    assert {"facility_context", "persistence", "recurrence", "ml_evidence"} <= names
    d = r.full()
    assert "not a confirmed fire" in d["disclaimer"] and "not source attribution" in d["facility_note"] and d["alternative_explanations"]
    assert "not a confirmed industrial fire" in d["meaning"]


def test_a_single_signal_never_makes_an_industrial_candidate():
    only_facility = si.interpret(_ev(obs=1, dur=0.0), facility_type="oil_refinery")           # HIGH-quality facility alone (weight 2.0) is not enough
    assert only_facility.classification != si.INDUSTRIAL
    only_persistence = si.interpret(_ev(obs=9, dur=8.0, facility=False))
    assert only_persistence.classification == si.PERSISTENT


def test_low_quality_or_non_heat_facility_is_not_industrial_evidence():
    r = si.interpret(_ev(obs=9, dur=8.0, quality="LOW"), facility_type="industrial")
    assert r.classification == si.PERSISTENT and any(c["signal"] == "facility_context" for c in r.contradicting)
    r2 = si.interpret(_ev(obs=9, dur=8.0, quality="MEDIUM"), facility_type="school")
    assert r2.classification == si.PERSISTENT


def test_persistent_thermal_source_candidate_when_attribution_is_ambiguous():
    r = si.interpret(_ev(obs=12, dur=9.0, facility=False))
    assert r.classification == si.PERSISTENT and r.strength in ("LOW", "MODERATE")
    assert any("no eligible facility" in u for u in r.unavailable)


def test_agricultural_candidate_needs_two_kinds_of_positive_evidence_and_no_usable_facility():
    r = si.interpret(_ev(obs=1, dur=0.0, facility=False, month=10, ml=B))
    assert r.classification == si.AGRICULTURAL and {x["signal"] for x in r.supporting} >= {"agri_season", "transient"}
    assert "not a confirmed agricultural fire" in si.MEANINGS[si.AGRICULTURAL]
    off_season = si.interpret(_ev(obs=1, dur=0.0, facility=False, month=8))
    assert off_season.classification != si.AGRICULTURAL
    in_season_persistent = si.interpret(_ev(obs=9, dur=9.0, facility=False, month=10))
    assert in_season_persistent.classification != si.AGRICULTURAL            # season alone (no second positive signal) is not enough


def test_absence_of_a_facility_is_never_evidence_of_an_agricultural_or_natural_source():
    r = si.interpret(_ev(obs=1, dur=0.0, facility=False, month=8))
    assert r.classification == si.UNCERTAIN and r.strength == "UNCERTAIN"
    assert any("absence is not evidence" in u for u in r.unavailable)


def test_natural_other_requires_positive_non_industrial_context():
    r = si.interpret(_ev(obs=1, dur=0.0, quality="MEDIUM", month=8), facility_type="school")
    assert r.classification == si.NATURAL and r.strength == "LOW"
    assert si.interpret(_ev(obs=1, dur=0.0, facility=False, month=8)).classification != si.NATURAL


def test_conflicting_evidence_is_uncertain_not_forced():
    r = si.interpret(_ev(obs=8, dur=7.0, quality="HIGH", month=10, ml=B), facility_type="oil_refinery", history_events=5, typed_history=8, static_history=0)
    assert r.classification == si.UNCERTAIN and any(c["signal"] == "conflict" for c in r.contradicting)


def test_firms_type_is_used_only_when_enough_typed_history_exists_and_is_not_guessed():
    none = si.interpret(_ev(obs=8, dur=7.0), facility_type="oil_refinery", typed_history=2, static_history=2)
    assert not any(x["signal"] == "firms_type" for x in none.supporting) and any("FIRMS type" in u for u in none.unavailable)
    static = si.interpret(_ev(obs=8, dur=7.0), facility_type="oil_refinery", typed_history=9, static_history=8)
    assert any(x["signal"] == "firms_type" and "static land source" in x["text"] for x in static.supporting)


def test_ml_evidence_is_half_weight_and_flagged_as_correlated():
    without = si.interpret(_ev(obs=8, dur=7.0), facility_type="oil_refinery")
    with_ml = si.interpret(_ev(obs=8, dur=7.0, ml=A), facility_type="oil_refinery")
    assert with_ml.scores[si.LABELS[si.INDUSTRIAL]] - without.scores[si.LABELS[si.INDUSTRIAL]] == pytest.approx(0.5)
    assert "half weight" in next(x for x in with_ml.supporting if x["signal"] == "ml_evidence")["text"]


def test_labels_are_conservative_candidates_and_never_claim_a_fire_or_a_probability():
    for c in si.CLASSES:
        text = (si.LABELS[c] + " " + si.MEANINGS[c]).lower()
        assert "confirmed" not in text.replace("not a confirmed", "")
        assert "probab" not in text and "industrial fire" not in si.LABELS[c].lower()
    assert si.INDUSTRIAL.endswith("CANDIDATE") and si.AGRICULTURAL.endswith("CANDIDATE") and si.PERSISTENT.endswith("CANDIDATE")


def test_interpretation_never_changes_the_event_or_its_risk():
    e = _ev(obs=8, dur=7.0, ml=A)
    before = e.model_dump()
    si.interpret(e, facility_type="oil_refinery", history_events=5)
    assert e.model_dump() == before


# ------------------------------------------------------------------ API serialisation and Intelligence Console
def _seed(db, eid, obs=8, fac=True, sev=Severity.MEDIUM):
    if fac and repo.get_facility(db, "FAC-1") is None:
        repo.upsert_facility(db, Facility(facility_id="FAC-1", name="Test Refinery", facility_type="oil_refinery", latitude=22.3, longitude=69.8, source="OSM", is_demo=False))
    e = ThermalEvent(event_id=eid, first_detected=datetime(2026, 9, 1, 6), last_detected=datetime(2026, 9, 1, 14), duration_hours=8.0, observation_count=obs, centroid_lat=22.3, centroid_lon=69.8,
                     severity=sev, risk_score=40.0, trajectory_direction=TrajectoryDirection.STABLE, facility_id="FAC-1" if fac else None, facility_distance_km=0.5 if fac else None,
                     facility_context_quality="HIGH" if fac else None, classification=A if fac else None, peak_frp=20.0, source_observation_ids=[f"{eid}-o"])
    repo.upsert_event(db, e)


def test_event_list_serialises_the_interpretation_summary_and_severity_stays_separate(db_session):
    _seed(db_session, "EVT-AAA000001")
    db_session.commit()
    ev = repo.attach_derived_event_fields(db_session, [repo.event_to_schema(r) for r in repo.list_events(db_session)])[0]
    d = ev.model_dump(mode="json")
    assert set(d["source_interpretation"]) == {"classification", "label", "strength"}
    assert d["severity"] == "MEDIUM" and d["source_interpretation"]["classification"] in si.CLASSES     # two independent dimensions


def test_console_lists_events_by_interpretation_and_states_the_true_count(db_session):
    for i in range(3):
        _seed(db_session, f"EVT-AAA00000{i}")
    _seed(db_session, "EVT-BBB000001", obs=2, fac=False)
    db_session.commit()
    r = runtime.run_query(db_session, "show industrial-source candidates")
    assert r.tool_calls[0].tool == "list_events_by_interpretation" and "3 active event(s)" in r.text and "not a confirmed fire" in r.text
    r2 = runtime.run_query(db_session, "how many persistent thermal-source candidates are active?")
    assert r2.tool_calls[0].tool == "list_events_by_interpretation"
    r3 = runtime.run_query(db_session, "show uncertain thermal events")
    assert r3.tool_calls[0].tool == "list_events_by_interpretation" and "uncertain" in r3.text.lower()


def test_console_explains_a_classification_from_stored_evidence_only(db_session):
    _seed(db_session, "EVT-AAA000001")
    db_session.commit()
    r = runtime.run_query(db_session, "Why is EVT-AAA000001 classified as an industrial-source candidate?")
    assert r.tool_calls[0].tool == "get_source_interpretation"
    assert "Evidence:" in r.text and "not a confirmed fire classification" in r.text and "not source attribution" in r.text
    r2 = runtime.run_query(db_session, "Is EVT-AAA000001 an industrial fire?")
    assert "it is not a confirmed fire" in r2.text and "industrial-source candidate" in r2.text.lower()
    assert runtime.run_query(db_session, "classify EVT-NOPE00001").text.startswith("I could not find") or "find event" in runtime.run_query(db_session, "classify EVT-NOPE00001").text


def test_console_stays_read_only(db_session):
    _seed(db_session, "EVT-AAA000001")
    db_session.commit()
    before = repo.get_event(db_session, "EVT-AAA000001")
    snap = (before.status, before.risk_score, before.severity, before.classification)
    for q in ("Delete EVT-AAA000001", "Change risk of EVT-AAA000001 to 100", "extinguish EVT-AAA000001", "classify EVT-AAA000001 as agricultural and save it"):
        runtime.run_query(db_session, q)
    db_session.expire_all()
    after = repo.get_event(db_session, "EVT-AAA000001")
    assert snap == (after.status, after.risk_score, after.severity, after.classification)
    assert not repo.list_alert_history(db_session, "EVT-AAA000001")


# ------------------------------------------------------------------ audit: zero risk contribution, safe wording everywhere
def test_interpretation_contributes_zero_risk_points_by_construction_and_by_effect(db_session):
    import inspect
    from app.intelligence import risk as risk_mod, pipeline as pl
    for mod in (risk_mod, pl):
        src = inspect.getsource(mod)
        assert "source_interpretation" not in src and "interpretation" not in src.lower()          # the risk path never sees it
    _seed(db_session, "EVT-AAA000001")
    db_session.commit()
    row = repo.get_event(db_session, "EVT-AAA000001")
    before = (row.risk_score, row.severity)
    ev = repo.attach_derived_event_fields(db_session, [repo.event_to_schema(row)])[0]                # computes the interpretation
    assert ev.source_interpretation is not None and (ev.risk_score, ev.severity.value) == (before[0], before[1])
    from app.model.schemas import Risk
    assert "interpretation" not in " ".join(Risk.model_fields)                                       # not a risk factor / field


def test_no_generated_text_claims_a_fire_causation_or_probability():
    import itertools, re
    bad = re.compile(r"caused by|caused the|probability|% chance|confirmed (?!fire classification)|will (become|ignite)", re.I)
    for obs, dur, fac, q, month, ml, hist, ftype in itertools.product((1, 3, 9), (0.0, 8.0), (True, False), ("HIGH", "MEDIUM", "LOW"), (8, 10), (None, A, B), (0, 5), ("refinery", "school", None)):
        r = si.interpret(_ev(obs=obs, dur=dur, facility=fac, quality=q, month=month, ml=ml), facility_type=ftype, history_events=hist, typed_history=9, static_history=8)
        d = r.full()
        texts = [d["label"], d["meaning"], d["disclaimer"], d["facility_note"]] + d["alternative_explanations"] + [x["text"] for x in d["supporting_evidence"] + d["contradicting_evidence"]] + d["unavailable_evidence"]
        for t in texts:
            assert not bad.search(t.replace("not a confirmed", "")), t
        assert d["strength"] in ("HIGH", "MODERATE", "LOW", "UNCERTAIN") and d["classification"] in si.CLASSES
        assert "not a confirmed fire classification" in d["disclaimer"] and "not source attribution" in d["facility_note"]
        if d["classification"] == si.UNCERTAIN:
            assert d["strength"] == "UNCERTAIN"


def test_facility_proximity_and_ml_alone_never_decide_a_class():
    facility_only = si.interpret(_ev(obs=1, dur=0.0, ml=None), facility_type="oil_refinery")
    ml_only = si.interpret(_ev(obs=1, dur=0.0, facility=False, month=8, ml=A))
    assert facility_only.classification != si.INDUSTRIAL and ml_only.classification not in (si.INDUSTRIAL, si.AGRICULTURAL)
    ml_b_only = si.interpret(_ev(obs=1, dur=0.0, facility=False, month=8, ml=B))
    assert ml_b_only.classification not in (si.INDUSTRIAL, si.AGRICULTURAL)
