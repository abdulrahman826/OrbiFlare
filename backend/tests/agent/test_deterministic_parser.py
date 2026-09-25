from app.agent.deterministic import parse


def test_explain_risk_intent_with_event_id():
    p = parse("Why is EVT-AB12CD34 high risk?")
    assert p.intent == "explain_risk"
    assert p.event_ids == ["EVT-AB12CD34"]


def test_high_risk_list_intent_without_event_id():
    p = parse("show me the high risk events")
    assert p.intent == "list_high_risk_events"
    assert p.event_ids == []


def test_escalating_list_intent():
    p = parse("which events are escalating right now")
    assert p.intent == "list_escalating_events"


def test_compare_events_intent():
    p = parse("compare EVT-AAAAAAAA and EVT-BBBBBBBB")
    assert p.intent == "compare_events"
    assert len(p.event_ids) == 2


def test_thermal_twin_intent_with_facility_id():
    p = parse("what is the normal baseline for FAC-REF-ALPHA")
    assert p.intent == "get_thermal_twin"
    assert p.facility_ids == ["FAC-REF-ALPHA"]


def test_unknown_intent_for_unrelated_text():
    p = parse("hello there, how are you")
    assert p.intent == "unknown"


def test_evidence_intent_takes_priority_over_generic_list():
    p = parse("what evidence supports EVT-AB12CD34 being high risk")
    assert p.intent == "get_evidence"


def test_persistent_events_intent():
    p = parse("which events are showing persistent thermal activity")
    assert p.intent == "list_persistent_events"


def test_facility_persistence_ranking_intent():
    p = parse("which facilities have the most persistent thermal activity")
    assert p.intent == "facility_event_frequency"


def test_event_statistics_intent_for_how_many_question():
    p = parse("how many high-risk events are active?")
    assert p.intent == "get_event_statistics"


def test_risk_statistics_intent():
    p = parse("show me the risk distribution")
    assert p.intent == "get_risk_statistics"


def test_compare_event_to_baseline_intent():
    p = parse("compare EVT-AB12CD34 with its baseline")
    assert p.intent == "compare_event_to_baseline"
    assert p.event_ids == ["EVT-AB12CD34"]


def test_facility_statistics_intent():
    p = parse("give me statistics for FAC-REF-ALPHA")
    assert p.intent == "get_facility_statistics"
    assert p.facility_ids == ["FAC-REF-ALPHA"]


def test_insufficient_baseline_intent_is_routed_to_dedicated_read_only_tool():
    from app.agent.deterministic import parse
    from app.agent.tools import TOOL_REGISTRY

    for msg in ("which events have insufficient baseline?", "Show events with insufficient baseline."):
        assert parse(msg).intent == "list_insufficient_baseline_events"
    assert "list_insufficient_baseline_events" in TOOL_REGISTRY
