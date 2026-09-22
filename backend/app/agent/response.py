"""Turns raw tool-call results into the analyst-facing text + result cards
+ suggested UI navigation that app.agent.runtime returns.
"""
from __future__ import annotations

from app.agent.schemas import ResultCard, UIAction


def explain_risk_text(investigation: dict) -> str:
    event = investigation["event"]
    risk = investigation.get("risk")
    deviation = investigation.get("deviation")
    if risk is None:
        return f"No risk assessment is available yet for {event['event_id']}."

    lines = [f"{event['event_id']} is {risk['severity']} risk (score {risk['risk_score']:.0f}/100)."]
    lines.append(risk["explanation"])
    if deviation and deviation.get("baseline_confidence") == "INSUFFICIENT":
        lines.append("Note: the facility baseline is INSUFFICIENT, so behavioural deviation could not fully inform this score.")
    elif deviation:
        notable = [d for d in [deviation.get(k) for k in
                   ("intensity", "persistence", "duration", "temporal", "spatial", "recurrence")]
                   if d and (d.get("is_notable") or d.get("is_significant"))]
        if notable:
            lines.append("Behavioural deviation: " + " ".join(d["explanation"] for d in notable))
    traj = investigation.get("trajectory")
    if traj:
        lines.append(traj["explanation"])
    for c in risk.get("caveats", []):
        lines.append(f"Caveat: {c}")
    return " ".join(lines)


def build_event_card(event: dict) -> ResultCard:
    return ResultCard(
        type="event", title=event["event_id"],
        subtitle=f"{event.get('severity') or 'UNSCORED'} - risk {event.get('risk_score') or 0:.0f}",
        data=event,
    )


def ui_action_for_event(event_id: str) -> UIAction:
    return UIAction(action="open_investigation", target_id=event_id)


def ui_action_for_facility(facility_id: str) -> UIAction:
    return UIAction(action="open_facility", target_id=facility_id)
