"""Event Replay -- turns an event's real observation history into a
deterministic, chronologically-ordered sequence of frames for the frontend
"PLAY EVENT" feature. Built on the same evolve_event() stepper as the risk
trajectory, so replay and trajectory are always consistent with each other.
"""
from __future__ import annotations

from app.intelligence.trajectory import evolve_event
from app.model.schemas import EventReplay, ReplayFrame, ThermalObservation, ThermalTwin


def build_replay(
    event_id: str, observations: list[ThermalObservation], twin: ThermalTwin | None,
    facility_id: str | None, facility_distance_km: float | None, facility_quality: str | None = None,
) -> EventReplay:
    steps = evolve_event(observations, twin, facility_id, facility_distance_km, facility_quality)
    frames = [
        ReplayFrame(
            step=i + 1, observation=s.observation, cumulative_observation_count=s.partial_event.observation_count,
            cumulative_peak_frp=s.partial_event.peak_frp, cumulative_mean_frp=s.partial_event.mean_frp,
            cumulative_peak_bt=s.partial_event.peak_bt, centroid_lat=s.partial_event.centroid_lat,
            centroid_lon=s.partial_event.centroid_lon, footprint_radius_km=s.partial_event.footprint_radius_km,
            deviation_score=s.deviation.overall_deviation_score, risk_score=s.risk.risk_score, severity=s.risk.severity,
        )
        for i, s in enumerate(steps)
    ]
    return EventReplay(event_id=event_id, frames=frames)
