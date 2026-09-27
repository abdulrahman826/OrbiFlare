"""Deterministic intent + entity parser. The agent works fully without any
LLM configured -- this is the guaranteed fallback (and, in this build, the
only path, since app.agent.llm only *optionally* polishes phrasing).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

EVENT_ID_RE = re.compile(r"\bEVT-[A-Z0-9]{6,12}\b", re.IGNORECASE)
INCIDENT_ID_RE = re.compile(r"\bIND-\d{3}\b", re.IGNORECASE)
FACILITY_ID_RE = re.compile(r"\bFAC-[A-Z0-9\-]{3,20}\b", re.IGNORECASE)


@dataclass
class ParsedIntent:
    intent: str
    event_ids: list[str] = field(default_factory=list)
    facility_ids: list[str] = field(default_factory=list)
    incident_ids: list[str] = field(default_factory=list)
    state: str | None = None
    severity: str | None = None
    interpretation: str | None = None     # source-interpretation class filter (see intelligence/source_interpretation.py)


def parse(message: str) -> ParsedIntent:
    text = message.strip().lower()
    event_ids = [m.upper() for m in EVENT_ID_RE.findall(message)]
    facility_ids = [m.upper() for m in FACILITY_ID_RE.findall(message)]

    incident_ids = [m.upper() for m in INCIDENT_ID_RE.findall(message)]
    severity = None
    for s in ("critical", "high", "medium", "low"):
        if s in text:
            severity = s.upper()
            break

    # Entity-specific intents take priority over generic list intents, since
    # a question like "why is EVT-X high risk?" contains "high risk" as a
    # substring but is asking about ONE event, not the whole high-risk list.
    # Historical reference incidents (never FIRMS detections). Checked before the generic entity intents.
    if incident_ids:
        return ParsedIntent("get_historical_incident", incident_ids=incident_ids)
    near = "near" in text or "around" in text or "close to" in text
    if "incident" in text and near and event_ids:
        return ParsedIntent("find_incidents_near_event", event_ids=event_ids)
    if "incident" in text and near and facility_ids:
        return ParsedIntent("find_incidents_near_facility", facility_ids=facility_ids)
    if ("historical" in text or "incident" in text) and not event_ids and not facility_ids:
        return ParsedIntent("list_historical_incidents", state=_state_in(text))
    if "compare" in text and len(event_ids) >= 2:
        return ParsedIntent("compare_events", event_ids=event_ids)
    if "compare" in text and len(facility_ids) >= 2:
        return ParsedIntent("compare_facilities", facility_ids=facility_ids)
    if "compare" in text and len(event_ids) == 1 and ("baseline" in text or "normal" in text):
        return ParsedIntent("compare_event_to_baseline", event_ids=event_ids)
    # Source interpretation (descriptive candidate labels; never a confirmed fire)
    if event_ids and ("classif" in text or "industrial fire" in text or "industrial-source" in text or "industrial source" in text
                      or "agricultural" in text or "uncertain" in text or "interpret" in text or "candidate" in text):
        return ParsedIntent("explain_interpretation", event_ids=event_ids)
    interp = _interpretation_in(text)
    if interp and not event_ids and not facility_ids:
        return ParsedIntent("list_events_by_interpretation", interpretation=interp)
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
    if "insufficient" in text or ("without" in text and "baseline" in text) or "no baseline" in text:
        return ParsedIntent("list_insufficient_baseline_events")
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


def _interpretation_in(text: str) -> str | None:
    from app.intelligence import source_interpretation as si
    if "persistent thermal-source" in text or "persistent thermal source" in text or "thermal-source candidate" in text:
        return si.PERSISTENT
    if "industrial-source" in text or "industrial source" in text or "industrial candidate" in text or "industrial thermal" in text:
        return si.INDUSTRIAL
    if "agricultur" in text or "vegetation" in text or "crop" in text:
        return si.AGRICULTURAL
    if "uncertain" in text:
        return si.UNCERTAIN
    if "natural" in text and ("candidate" in text or "thermal" in text or "other" in text):
        return si.NATURAL
    return None


def _state_in(text: str) -> str | None:
    """Indian state named in the query, matched against the bundled boundary data (longest name first)."""
    from app.reference import admin
    for name in sorted(admin.summary()["state_names"], key=len, reverse=True):
        if name.lower() in text:
            return name
    return None
