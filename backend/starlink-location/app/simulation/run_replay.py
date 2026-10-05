"""Project one candidate frame; publishing owns the irreversible cursor advance."""

from dataclasses import dataclass
from datetime import datetime

from app.mission.models import Transport, TransportState
from app.mission.replay_state import TransportReplayState, apply_transport_event
from app.models.flight_status import FlightPhase
from app.models.telemetry import PositionData
from app.services.active_x_handoff import ActiveXContext, empty_handoff_context
from app.simulation.run_plan import PreparedMissionRun


@dataclass(frozen=True)
class ReplayFrame:
    simulation_time: datetime
    position: PositionData
    progress_percent: float
    phase: FlightPhase
    transport_states: dict[Transport, TransportState]
    processed_event_count: int
    x_context: ActiveXContext
    reducer_state: TransportReplayState
    x_assignment_count: int = 0


def project_run_frame(
    plan: PreparedMissionRun, simulation_time: datetime, previous: ReplayFrame | None
) -> ReplayFrame:
    projector = plan.artifacts.projector
    now = max(projector.start_time, min(simulation_time, projector.end_time))
    if previous:
        now = max(previous.simulation_time, now)
    final = now == projector.end_time
    distance = projector.distance_for_timestamp(now)
    sample = projector.sample_at_distance(distance)
    # An exact terminal coordinate must never use the legacy modulo follower.
    if final:
        endpoint = plan.artifacts.route.points[-1]
        latitude, longitude = endpoint.latitude, endpoint.longitude
        altitude = (
            endpoint.altitude if endpoint.altitude is not None else sample.altitude
        )
    else:
        latitude, longitude, altitude = (
            sample.latitude,
            sample.longitude,
            sample.altitude,
        )
    speed = 0.0
    for i, current in enumerate(plan.artifacts.route.points[1:], 1):
        prior = plan.artifacts.route.points[i - 1]
        start, end = prior.expected_arrival_time, current.expected_arrival_time
        if start <= now < end or (final and i == len(plan.artifacts.route.points) - 1):
            speed = (
                (
                    projector.cumulative_distances[i]
                    - projector.cumulative_distances[i - 1]
                )
                / (end - start).total_seconds()
                / 0.514444
            )
            break
    if final:
        speed = 0.0
    progress = 100.0 if final else 100 * distance / projector.total_distance
    reducer = previous.reducer_state if previous else TransportReplayState()
    cursor = previous.processed_event_count if previous else 0
    while (
        cursor < len(plan.replay_events) and plan.replay_events[cursor].timestamp <= now
    ):
        reducer = apply_transport_event(reducer, plan.replay_events[cursor])
        cursor += 1
    x_cursor = previous.x_assignment_count if previous else 0
    current_x = (
        previous.x_context.current_satellite_id
        if previous
        else plan.initial_x_satellite_id
    )
    handoff = dict(previous.x_context.handoff) if previous else empty_handoff_context()
    assignments = plan.artifacts.x_assignments
    while x_cursor < len(assignments) and assignments[x_cursor][0] <= now:
        _, current_x, transition_id = assignments[x_cursor]
        if transition_id:
            handoff = {
                **handoff,
                "phase": "committed",
                "transition_id": transition_id,
                "transition_satellite_id": current_x,
            }
        x_cursor += 1
    pending = assignments[x_cursor][1] if x_cursor < len(assignments) else None
    handoff["route_progress_percent"] = progress
    position = PositionData(
        latitude=latitude,
        longitude=longitude,
        altitude=altitude * 3.28084,
        speed=speed,
        heading=sample.heading or 0,
    )
    return ReplayFrame(
        now,
        position,
        progress,
        FlightPhase.POST_ARRIVAL if final else FlightPhase.IN_FLIGHT,
        reducer.states(),
        cursor,
        ActiveXContext(current_x, pending, handoff),
        reducer,
        x_cursor,
    )
