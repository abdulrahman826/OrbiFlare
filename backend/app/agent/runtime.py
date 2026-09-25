"""Agent runtime: message -> intent/entity extraction -> controlled tool
registry -> real data -> response. See app/agent/{deterministic,tools,
response}.py for each stage. This module is the only orchestrator.

Fully deterministic: no LLM is ever consulted, and no user query is ever
sent to any external service. Every response is built exclusively from the
read-only tool registry in app.agent.tools.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.agent import response as resp_mod, tools
from app.agent.deterministic import parse
from app.agent.schemas import AgentResponse, ResultCard, ToolCall, UIAction


def run_query(db: Session, message: str) -> AgentResponse:
    parsed = parse(message)
    tool_calls: list[ToolCall] = []
    cards: list[ResultCard] = []
    ui_action: UIAction | None = None
    text: str

    def record(tool_name: str, args: dict, result) -> None:
        summary = "no result" if result is None else (f"{len(result)} item(s)" if isinstance(result, list) else "1 result")
        tool_calls.append(ToolCall(tool=tool_name, arguments=args, result_summary=summary))

    if parsed.intent == "explain_risk":
        event_id = parsed.event_ids[0]
        inv = tools.get_investigation_tool(db, event_id)
        record("get_investigation", {"event_id": event_id}, inv)
        if inv is None:
            text = f"I couldn't find event {event_id}."
        else:
            text = resp_mod.explain_risk_text(inv)
            cards.append(resp_mod.build_event_card(inv["event"]))
            ui_action = resp_mod.ui_action_for_event(event_id)

    elif parsed.intent == "get_investigation":
        event_id = parsed.event_ids[0]
        inv = tools.get_investigation_tool(db, event_id)
        record("get_investigation", {"event_id": event_id}, inv)
        if inv is None:
            text = f"I couldn't find event {event_id}."
        else:
            text = resp_mod.explain_risk_text(inv)
            cards.append(resp_mod.build_event_card(inv["event"]))
            ui_action = resp_mod.ui_action_for_event(event_id)

    elif parsed.intent == "get_evidence":
        event_id = parsed.event_ids[0]
        ev = tools.get_evidence(db, event_id)
        record("get_evidence", {"event_id": event_id}, ev)
        if ev is None:
            text = f"No evidence stack is available for {event_id}."
        else:
            n_sup, n_con, n_unc = len(ev["supporting_evidence"]), len(ev["contradicting_evidence"]), len(ev["uncertain_evidence"])
            text = (f"{event_id} has {n_sup} supporting, {n_con} contradicting and {n_unc} uncertain evidence item(s). "
                    + " ".join(i["explanation"] for i in ev["supporting_evidence"][:3]))
            ui_action = resp_mod.ui_action_for_event(event_id)

    elif parsed.intent == "get_deviation":
        event_id = parsed.event_ids[0]
        d = tools.get_deviation(db, event_id)
        record("get_deviation", {"event_id": event_id}, d)
        if d is None:
            text = f"No deviation assessment is available for {event_id}."
        elif d["baseline_confidence"] == "INSUFFICIENT":
            text = f"{event_id}: facility baseline is INSUFFICIENT, so deviation could not be assessed."
        else:
            text = " ".join(d[k]["explanation"] for k in ("intensity", "persistence", "duration", "temporal", "spatial", "recurrence"))
        ui_action = resp_mod.ui_action_for_event(event_id)

    elif parsed.intent == "get_trajectory":
        event_id = parsed.event_ids[0]
        t = tools.get_trajectory(db, event_id)
        record("get_trajectory", {"event_id": event_id}, t)
        text = f"No trajectory data for {event_id}." if t is None else \
            f"{event_id} trajectory: " + " -> ".join(f"{p['risk_score']:.0f}" for p in t["points"])
        ui_action = resp_mod.ui_action_for_event(event_id)

    elif parsed.intent == "generate_report":
        event_id = parsed.event_ids[0]
        report = tools.generate_report(db, event_id)
        record("generate_report", {"event_id": event_id}, report)
        text = f"Generated an incident report for {event_id}." if report else f"Could not generate a report for {event_id}."
        if report:
            cards.append(ResultCard(type="report", title=f"Incident report: {event_id}", data=report))
        ui_action = resp_mod.ui_action_for_event(event_id)

    elif parsed.intent == "get_thermal_twin":
        facility_id = parsed.facility_ids[0]
        twin = tools.get_thermal_twin(db, facility_id)
        record("get_thermal_twin", {"facility_id": facility_id}, twin)
        if twin is None:
            text = f"No thermal twin exists yet for {facility_id}."
        else:
            text = (f"{facility_id} baseline confidence: {twin['baseline_confidence']}, built from "
                    f"{twin['historical_event_count']} historical event(s) / {twin['historical_observation_count']} observation(s). "
                    f"Normal FRP median ~{(twin['normal_frp'].get('median') or 0):.0f} MW.")
        ui_action = resp_mod.ui_action_for_facility(facility_id)

    elif parsed.intent == "get_facility":
        facility_id = parsed.facility_ids[0]
        f = tools.get_facility(db, facility_id)
        record("get_facility", {"facility_id": facility_id}, f)
        text = f"No facility found with id {facility_id}." if f is None else f"{f['name']} ({f['facility_type']}) in {f.get('region') or f.get('state') or 'an unspecified region'}."
        ui_action = resp_mod.ui_action_for_facility(facility_id) if f else None

    elif parsed.intent == "compare_events":
        cmp = tools.compare_events(db, parsed.event_ids[0], parsed.event_ids[1])
        record("compare_events", {"a": parsed.event_ids[0], "b": parsed.event_ids[1]}, cmp)
        if cmp is None:
            text = "I couldn't find one or both of those events."
        else:
            text = (f"{cmp['event_a']['event_id']} risk {cmp['event_a']['risk_score']} vs. "
                    f"{cmp['event_b']['event_id']} risk {cmp['event_b']['risk_score']} (delta {cmp['risk_delta']}).")
            cards.append(resp_mod.build_event_card(cmp["event_a"]))
            cards.append(resp_mod.build_event_card(cmp["event_b"]))

    elif parsed.intent == "compare_facilities":
        cmp = tools.compare_facilities(db, parsed.facility_ids[0], parsed.facility_ids[1])
        record("compare_facilities", {"a": parsed.facility_ids[0], "b": parsed.facility_ids[1]}, cmp)
        text = "I couldn't find thermal twins for both facilities." if cmp is None else \
            f"Comparing baselines for {parsed.facility_ids[0]} and {parsed.facility_ids[1]} -- see the cards for details."
        if cmp:
            cards.append(ResultCard(type="comparison", title="Facility comparison", data=cmp))

    elif parsed.intent == "list_high_risk_events":
        events = tools.list_high_risk_events(db, limit=None)   # full list: the answer states the true count, cards show the top 5
        record("list_high_risk_events", {}, events)
        text = f"{len(events)} high/critical risk event(s) currently." if events else "No high or critical risk events right now."
        cards = [resp_mod.build_event_card(e) for e in events[:5]]

    elif parsed.intent == "list_escalating_events":
        events = tools.list_escalating_events(db, limit=None)
        record("list_escalating_events", {}, events)
        text = f"{len(events)} event(s) currently show an ESCALATING risk trajectory." if events else "No events are currently escalating."
        cards = [resp_mod.build_event_card(e) for e in events[:5]]

    elif parsed.intent == "list_events":
        events = tools.list_events(db, severity=parsed.severity, limit=None)
        record("list_events", {"severity": parsed.severity}, events)
        text = f"Found {len(events)} event(s)" + (f" with severity {parsed.severity}" if parsed.severity else "") + "."
        cards = [resp_mod.build_event_card(e) for e in events[:5]]

    elif parsed.intent == "list_persistent_events":
        events = tools.list_persistent_events(db, limit=None)
        record("list_persistent_events", {}, events)
        text = f"{len(events)} active event(s) show persistent thermal activity (6+ observations)." if events else "No events currently meet the persistent-activity threshold."
        cards = [resp_mod.build_event_card(e) for e in events[:5]]

    elif parsed.intent == "list_historical_incidents":
        items = tools.list_historical_incidents(db, state=parsed.state)
        record("list_historical_incidents", {"state": parsed.state}, items)
        if items:
            text = (f"{len(items)} HISTORICAL reference incident(s)" + (f" in {parsed.state}" if parsed.state else "")
                    + ". These are curated historical records -- not FIRMS detections and not live alerts.")
        else:
            text = "No historical reference incidents match."
        cards = [resp_mod.build_incident_card(i) for i in items[:8]]

    elif parsed.intent == "get_historical_incident":
        iid = parsed.incident_ids[0]
        ctx = tools.get_historical_incident(db, iid)
        record("get_historical_incident", {"incident_id": iid}, ctx)
        if ctx is None:
            text = f"I could not find historical incident {iid}."
        else:
            inc = ctx["incident"]
            text = (f"{iid} ({inc['record_kind_label']}, {inc['date']}, {inc['state']}): {inc['name']}. "
                    f"HISTORICAL reference record -- not a FIRMS detection. {ctx['firms_match']['note']} {ctx['unknown'][0]}")
            cards.append(resp_mod.build_incident_card(inc))
            ui_action = UIAction(action="open_incident", target_id=iid)

    elif parsed.intent in ("find_incidents_near_event", "find_incidents_near_facility"):
        if parsed.intent == "find_incidents_near_event":
            tid = parsed.event_ids[0]
            res = tools.find_incidents_near_event(db, tid)
            record("find_incidents_near_event", {"event_id": tid}, res)
            ui_action = resp_mod.ui_action_for_event(tid) if res else None
        else:
            tid = parsed.facility_ids[0]
            res = tools.find_incidents_near_facility(db, tid)
            record("find_incidents_near_facility", {"facility_id": tid}, res)
            ui_action = resp_mod.ui_action_for_facility(tid) if res else None
        if res is None:
            text = f"I could not find {tid}."
        else:
            n = len(res["incidents"])
            if n:
                text = f"{n} historical reference incident(s) within {res['radius_km']:g} km of {tid}. Proximity to a historical record is context only, not causation."
            else:
                text = f"No historical reference incidents within {res['radius_km']:g} km of {tid}."
            cards = [resp_mod.build_incident_card(i) for i in res["incidents"][:8]]

    elif parsed.intent == "list_insufficient_baseline_events":
        events = tools.list_insufficient_baseline_events(db, limit=None)
        record("list_insufficient_baseline_events", {}, events)
        text = (f"{len(events)} event(s) have an INSUFFICIENT facility baseline, so behavioural deviation cannot be assessed for them."
                if events else "Every event currently has at least a limited facility baseline.")
        cards = [resp_mod.build_event_card(e) for e in events[:5]]

    elif parsed.intent == "facility_event_frequency":
        ranking = tools.facility_event_frequency(db)
        record("facility_event_frequency", {}, ranking)
        if not ranking:
            text = "No facility-linked events are on record yet."
        else:
            top = ranking[0]
            text = (f"{top['name']} has the most persistent thermal activity: {top['persistent_event_count']} persistent "
                    f"event(s) out of {top['event_count']} total, of the {len(ranking)} facilit(y/ies) with recorded events.")
            cards.append(ResultCard(type="comparison", title="Facility event frequency", data={"ranking": ranking}))

    elif parsed.intent == "get_event_statistics":
        stats = tools.get_event_statistics(db)
        record("get_event_statistics", {}, [stats])
        text = (f"{stats['total_events']} total event(s), {stats['active_events']} active, {stats['high_risk_events']} high/critical risk, "
                f"{stats['escalating_events']} escalating, {stats['persistent_events']} persistent. "
                f"Average FRP {stats['average_frp']} MW, peak FRP {stats['peak_frp']} MW.")
        cards.append(ResultCard(type="report", title="Event statistics", data=stats))

    elif parsed.intent == "get_facility_statistics":
        facility_id = parsed.facility_ids[0]
        stats = tools.get_facility_statistics(db, facility_id)
        record("get_facility_statistics", {"facility_id": facility_id}, [stats] if stats else None)
        text = f"No facility found with id {facility_id}." if stats is None else \
            (f"{stats['name']}: {stats['total_events']} total event(s), {stats['high_risk_events']} high/critical risk, "
             f"{stats['persistent_events']} persistent, baseline confidence {stats['baseline_confidence']}.")
        if stats:
            cards.append(ResultCard(type="report", title=f"Facility statistics: {facility_id}", data=stats))
        ui_action = resp_mod.ui_action_for_facility(facility_id) if stats else None

    elif parsed.intent == "get_risk_statistics":
        stats = tools.get_risk_statistics(db)
        record("get_risk_statistics", {}, [stats])
        text = (f"{stats['scored_event_count']} scored event(s). Average risk {stats['average_risk_score']}, "
                f"peak risk {stats['peak_risk_score']}. Severity distribution: {stats['severity_distribution']}.")
        cards.append(ResultCard(type="report", title="Risk statistics", data=stats))

    elif parsed.intent == "compare_event_to_baseline":
        event_id = parsed.event_ids[0]
        cmp = tools.compare_event_to_baseline(db, event_id)
        record("compare_event_to_baseline", {"event_id": event_id}, [cmp] if cmp else None)
        if cmp is None:
            text = f"I couldn't find event {event_id}."
        elif cmp["baseline_status"] == "INSUFFICIENT_BASELINE":
            text = f"{event_id}: Insufficient baseline data."
        else:
            text = f"{event_id} vs. its facility baseline (confidence {cmp['baseline_status']}): overall deviation score {cmp['overall_deviation_score']:.0f}/100. See dimensions for NORMAL vs. CURRENT detail."
            cards.append(ResultCard(type="comparison", title=f"{event_id} vs. baseline", data=cmp))
        ui_action = resp_mod.ui_action_for_event(event_id)

    else:
        text = (
            "I can answer questions about specific events (e.g. \"why is EVT-AB12CD34 high risk?\"), "
            "facilities and their thermal twins, high-risk, escalating or persistent events, statistics, "
            "and comparisons (including an event vs. its facility baseline). "
            "Try including an event ID (EVT-...) or facility ID (FAC-...) in your question."
        )

    return AgentResponse(text=text, tool_calls=tool_calls, result_cards=cards, ui_action=ui_action)
