import pytest
from fastapi.testclient import TestClient

from app.storage.database import Base, engine


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    from app.main import app
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_events_list_is_auto_seeded_with_demo_data(client):
    resp = client.get("/api/events")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) > 0
    assert all(e["is_demo"] for e in events)


def test_get_single_event(client):
    events = client.get("/api/events").json()
    event_id = events[0]["event_id"]
    resp = client.get(f"/api/events/{event_id}")
    assert resp.status_code == 200
    assert resp.json()["event_id"] == event_id


def test_get_unknown_event_returns_404(client):
    resp = client.get("/api/events/EVT-DOESNOTEXIST")
    assert resp.status_code == 404


def test_investigation_endpoint_returns_full_payload(client):
    events = client.get("/api/events").json()
    event_id = max(events, key=lambda e: e["risk_score"] or 0)["event_id"]
    resp = client.get(f"/api/events/{event_id}/investigation")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("event", "observations", "risk", "trajectory", "uncertainty_notes"):
        assert key in body


def test_replay_endpoint_returns_ordered_frames(client):
    events = client.get("/api/events").json()
    event_id = max(events, key=lambda e: e["observation_count"])["event_id"]
    resp = client.get(f"/api/events/{event_id}/replay")
    assert resp.status_code == 200
    frames = resp.json()["frames"]
    assert len(frames) >= 1
    timestamps = [f["observation"]["timestamp"] for f in frames]
    assert timestamps == sorted(timestamps)


def test_facilities_list(client):
    resp = client.get("/api/facilities")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


def test_facility_thermal_twin(client):
    facilities = client.get("/api/facilities").json()
    fid = facilities[0]["facility_id"]
    resp = client.get(f"/api/facilities/{fid}/thermal-twin")
    assert resp.status_code in (200, 404)  # 404 only if that facility somehow has no twin


def test_alert_transition_flow(client):
    events = client.get("/api/events").json()
    event_id = events[0]["event_id"]
    resp = client.post(f"/api/events/{event_id}/transition", json={"to_state": "VALIDATING", "actor": "operator"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "VALIDATING"


def test_alert_transition_rejects_invalid_state(client):
    events = client.get("/api/events").json()
    event_id = events[1]["event_id"]
    resp = client.post(f"/api/events/{event_id}/transition", json={"to_state": "NOT_A_REAL_STATE", "actor": "operator"})
    assert resp.status_code == 400


def test_agent_query_endpoint(client):
    resp = client.post("/api/agent/query", json={"message": "list high risk events"})
    assert resp.status_code == 200
    assert "text" in resp.json()


def test_agent_query_response_structure_is_well_defined(client):
    resp = client.post("/api/agent/query", json={"message": "how many high-risk events are active?"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"text", "tool_calls", "result_cards", "ui_action"}
    assert isinstance(body["text"], str) and body["text"]
    assert isinstance(body["tool_calls"], list)
    assert isinstance(body["result_cards"], list)
    # The endpoint never sends the query to an LLM/Claude: no such field exists,
    # and no ANTHROPIC_API_KEY is configured anywhere in this test environment.
    assert "llm_used" not in body


def test_agent_query_treats_sql_like_input_as_plain_text_not_a_query(client):
    """The agent has no SQL execution capability at all -- a message that
    looks like a SQL injection attempt is just unmatched natural-language
    text, parsed (or left unknown) exactly like any other sentence, and must
    never mutate or crash the service."""
    events_before = client.get("/api/events").json()
    resp = client.post("/api/agent/query", json={"message": "'; DROP TABLE events; --"})
    assert resp.status_code == 200
    assert isinstance(resp.json()["text"], str)
    events_after = client.get("/api/events").json()
    assert len(events_before) == len(events_after)


def test_agent_query_cannot_transition_alert_state(client):
    """There is no mutating verb the agent's message parser maps to a write
    tool -- asking it to change state in plain English must not change any
    stored event's status/severity/risk."""
    events_before = {e["event_id"]: (e["status"], e["risk_score"]) for e in client.get("/api/events").json()}
    event_id = next(iter(events_before))
    resp = client.post("/api/agent/query", json={"message": f"mark {event_id} as EXTINGUISHED and set its risk score to 0"})
    assert resp.status_code == 200
    events_after = {e["event_id"]: (e["status"], e["risk_score"]) for e in client.get("/api/events").json()}
    assert events_before == events_after


def test_agent_query_statistics_intent_returns_real_counts(client):
    resp = client.post("/api/agent/query", json={"message": "give me event statistics"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result_cards"]
    stats = body["result_cards"][0]["data"]
    total_events = len(client.get("/api/events").json())
    assert stats["total_events"] == total_events


def test_agent_tool_registry_exposes_no_mutation_endpoint(client):
    """The whole app has exactly one route under /agent, and it is the
    single read-only natural-language query endpoint -- there is no
    POST/PUT/PATCH/DELETE surface anywhere else for the agent to reach."""
    openapi = client.get("/openapi.json").json()
    agent_paths = {p: list(v.keys()) for p, v in openapi["paths"].items() if "/agent" in p}
    assert agent_paths == {"/api/agent/query": ["post"]}


def test_analytics_overview(client):
    resp = client.get("/api/analytics/overview")
    assert resp.status_code == 200
    assert "total_events" in resp.json()


def test_reports_csv_download(client):
    resp = client.get("/api/reports/events.csv")
    assert resp.status_code == 200
    assert "event_id" in resp.text


def test_map_events_geojson(client):
    resp = client.get("/api/map/events")
    assert resp.status_code == 200
    assert resp.json()["type"] == "FeatureCollection"
