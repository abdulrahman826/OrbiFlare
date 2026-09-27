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


def interpretation_text(event_id: str, si: dict, message: str = "") -> str:
    """Answer built only from the stored interpretation (candidate label + the evidence that produced it)."""
    label = si["label"]
    lines = []
    if "industrial fire" in message.lower():
        lines.append(f"OrbiFlare classifies {event_id} as {'an ' if label[0].lower() in 'aeiou' else 'a '}{label.lower()} based on the available evidence; it is not a confirmed fire.")
    else:
        lines.append(f"{event_id}: {label}" + ("" if si["classification"] == "UNCERTAIN" else f" ({si['strength']} evidence)") + ". " + si["meaning"])
    if si["supporting_evidence"]:
        lines.append("Evidence: " + "; ".join(x["text"] for x in si["supporting_evidence"]) + ".")
    if si["contradicting_evidence"]:
        lines.append("Against or limiting: " + "; ".join(x["text"] for x in si["contradicting_evidence"]) + ".")
    if si["unavailable_evidence"]:
        lines.append("Unavailable: " + "; ".join(si["unavailable_evidence"][:3]) + ".")
    lines.append(si["disclaimer"] + " " + si["facility_note"])
    return " ".join(lines)


def build_event_card(event: dict) -> ResultCard:
    parts = [f"{event.get('severity') or 'UNSCORED'} - risk {event.get('risk_score') or 0:.0f}"]
    if event.get("trajectory_direction"):
        parts.append(str(event["trajectory_direction"]))
    if event.get("deviation_label") and event["deviation_label"] != "UNAVAILABLE":
        parts.append(f"deviation {event['deviation_label']}")
    return ResultCard(type="event", title=event["event_id"], subtitle=" · ".join(parts), data=event)


def ui_action_for_event(event_id: str) -> UIAction:
    return UIAction(action="open_investigation", target_id=event_id)


def ui_action_for_facility(facility_id: str) -> UIAction:
    return UIAction(action="open_facility", target_id=facility_id)


def build_incident_card(incident: dict) -> ResultCard:
    parts = [incident.get("record_kind_label", ""), incident.get("date", ""), incident.get("state", ""), "HISTORICAL"]
    if incident.get("distance_km") is not None:
        parts.append(f"{incident['distance_km']} km away")
    return ResultCard(type="incident", title=incident["incident_id"], subtitle=" · ".join(p for p in parts if p), data=incident)
