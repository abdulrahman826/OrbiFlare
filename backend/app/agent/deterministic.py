"""Deterministic intent + entity parser. The agent works fully without any
LLM configured -- this is the guaranteed fallback (and, in this build, the
only path, since app.agent.llm only *optionally* polishes phrasing).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

EVENT_ID_RE = re.compile(r"\bEVT-[A-Z0-9]{6,12}\b", re.IGNORECASE)
FACILITY_ID_RE = re.compile(r"\bFAC-[A-Z0-9\-]{3,20}\b", re.IGNORECASE)


@dataclass
class ParsedIntent:
    intent: str
    event_ids: list[str] = field(default_factory=list)
    facility_ids: list[str] = field(default_factory=list)
    severity: str | None = None


def parse(message: str) -> ParsedIntent:
    text = message.strip().lower()
    event_ids = [m.upper() for m in EVENT_ID_RE.findall(message)]
    facility_ids = [m.upper() for m in FACILITY_ID_RE.findall(message)]

    severity = None
    for s in ("critical", "high", "medium", "low"):
        if s in text:
            severity = s.upper()
            break

    # Entity-specific intents take priority over generic list intents, since
    # a question like "why is EVT-X high risk?" contains "high risk" as a
    # substring but is asking about ONE event, not the whole high-risk list.
    if "compare" in text and len(event_ids) >= 2:
        return ParsedIntent("compare_events", event_ids=event_ids)
    if "compare" in text and len(facility_ids) >= 2:
        return ParsedIntent("compare_facilities", facility_ids=facility_ids)
    if "compare" in text and len(event_ids) == 1 and ("baseline" in text or "normal" in text):
        return ParsedIntent("compare_event_to_baseline", event_ids=event_ids)
    if ("why" in text or "explain" in text) and event_ids:
        return ParsedIntent("explain_risk", event_ids=event_ids)
    if ("evidence" in text) and event_ids:
        return ParsedIntent("get_evidence", event_ids=event_ids)
    if ("deviat" in text) and event_ids:
        return ParsedIntent("get_deviation", event_ids=event_ids)
    if ("trajectory" in text or "trend" in text) and event_ids:
        return ParsedIntent("get_trajectory", event_ids=event_ids)
    if ("report" in text) and event_ids:
        return ParsedIntent("generate_report", event_ids=event_ids)
    if ("twin" in text or "baseline" in text or "normal" in text) and facility_ids:
        return ParsedIntent("get_thermal_twin", facility_ids=facility_ids)
    if ("statistic" in text or "stats" in text) and facility_ids:
        return ParsedIntent("get_facility_statistics", facility_ids=facility_ids)
    if facility_ids:
        return ParsedIntent("get_facility", facility_ids=facility_ids)
    if event_ids:
        return ParsedIntent("get_investigation", event_ids=event_ids)

    # Generic list/aggregate intents (no specific entity mentioned).
    if "how many" in text or "count of" in text:
        return ParsedIntent("get_event_statistics")
    if "risk" in text and ("statistic" in text or "distribution" in text):
        return ParsedIntent("get_risk_statistics")
    if "persistent" in text or "persistence" in text:
        if "facilit" in text:
            return ParsedIntent("facility_event_frequency")
        return ParsedIntent("list_persistent_events")
    if "escalat" in text:
        return ParsedIntent("list_escalating_events")
    if "high risk" in text or "high-priority" in text or "high priority" in text:
        return ParsedIntent("list_high_risk_events")
    if "statistic" in text or "stats" in text or "average" in text or "distribution" in text:
        return ParsedIntent("get_event_statistics")
    if "list" in text or "events" in text or "show" in text:
        return ParsedIntent("list_events", severity=severity)

    return ParsedIntent("unknown")
