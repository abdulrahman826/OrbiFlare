"""Risk Trajectory -- tracks how risk evolved across an event's actual
observation history. This is EARLY RISK WARNING language ("observed risk
has increased"), never a prediction of future fire ("this will become a
fire").

The trajectory is computed by literally re-running event-formation +
deviation + classification + risk on successive prefixes of the event's real
observations -- nothing here is fabricated or interpolated. Event Replay
(app/intelligence/replay.py) reuses the same step-by-step evolution.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.intelligence import classification, risk as risk_engine
from app.intelligence.deviation import compute_deviation
from app.intelligence.events import build_event_from_group
from app.model.schemas import (
    Deviation,
    MLPrediction,
    Risk,
    RiskTrajectory,
    ThermalEvent,
    ThermalObservation,
    ThermalTwin,
    TrajectoryDirection,
    TrajectoryPoint,
)


@dataclass
class EvolutionStep:
    observation: ThermalObservation
    partial_event: ThermalEvent
    deviation: Deviation
    ml: MLPrediction
    risk: Risk


def evolve_event(
    observations: list[ThermalObservation], twin: ThermalTwin | None,
    facility_id: str | None, facility_distance_km: float | None,
) -> list[EvolutionStep]:
    obs_sorted = sorted(observations, key=lambda o: o.timestamp)
    steps: list[EvolutionStep] = []
    for k in range(1, len(obs_sorted) + 1):
        prefix = obs_sorted[:k]
        partial_event = build_event_from_group(prefix)
        partial_event.facility_id = facility_id
        partial_event.facility_distance_km = facility_distance_km
        deviation = compute_deviation(partial_event, twin, prefix)
        ml = classification.classify_event(partial_event)
        recent_frp = prefix[-1].frp if prefix[-1].frp is not None else partial_event.peak_frp
        r = risk_engine.compute_risk(partial_event, deviation, ml, facility_present=facility_id is not None, recent_frp=recent_frp)
        steps.append(EvolutionStep(observation=prefix[-1], partial_event=partial_event, deviation=deviation, ml=ml, risk=r))
    return steps


def _direction(scores: list[float]) -> TrajectoryDirection:
    if len(scores) < 2:
        return TrajectoryDirection.INSUFFICIENT_DATA
    net_change = scores[-1] - scores[0]
    deltas = [b - a for a, b in zip(scores, scores[1:])]
    non_decreasing = all(d >= -2.0 for d in deltas)
    if net_change >= 25 and non_decreasing:
        return TrajectoryDirection.ESCALATING
    if net_change >= 8:
        return TrajectoryDirection.INCREASING
    if net_change <= -8:
        return TrajectoryDirection.DECREASING
    return TrajectoryDirection.STABLE


_DIRECTION_TEXT = {
    TrajectoryDirection.ESCALATING: "Observed risk has increased consistently across the event's lifetime, from {first:.0f} to {last:.0f}.",
    TrajectoryDirection.INCREASING: "Observed risk has trended upward during the event, from {first:.0f} to {last:.0f}.",
    TrajectoryDirection.DECREASING: "Observed risk has declined during the event, from {first:.0f} to {last:.0f}.",
    TrajectoryDirection.STABLE: "Observed risk has remained broadly stable throughout the event ({first:.0f} to {last:.0f}).",
    TrajectoryDirection.INSUFFICIENT_DATA: "Not enough observations exist yet to characterize a risk trend for this event.",
}


def compute_trajectory(
    observations: list[ThermalObservation], twin: ThermalTwin | None,
    facility_id: str | None, facility_distance_km: float | None, event_id: str,
) -> tuple[RiskTrajectory, list[EvolutionStep]]:
    steps = evolve_event(observations, twin, facility_id, facility_distance_km)
    scores = [s.risk.risk_score for s in steps]
    direction = _direction(scores)
    text = _DIRECTION_TEXT[direction].format(first=scores[0] if scores else 0, last=scores[-1] if scores else 0)

    points = [
        TrajectoryPoint(timestamp=s.observation.timestamp, risk_score=s.risk.risk_score,
                         deviation_score=s.deviation.overall_deviation_score, severity=s.risk.severity)
        for s in steps
    ]
    return RiskTrajectory(event_id=event_id, points=points, direction=direction, explanation=text), steps
