"""Conservative movement inference; never an exact wheel-contact detector."""

from app.services.flight_events.models import (
    Candidate,
    DetectionPolicy,
    DetectionResult,
    DetectionState,
    FlightEvent,
    FlightObservation,
)
from app.services.kml.geometry import haversine_distance


def advance_detection(
    state: DetectionState, observation: FlightObservation, policy: DetectionPolicy
) -> DetectionResult:
    """Advance only coherent fresh observations; return durable candidate changes."""
    state = state.model_copy(deep=True)
    result = DetectionResult(state=state, leg_completion=state.destination_complete)
    now = observation.observed_at
    previous = state.last_observed_at
    if previous is not None and now <= previous:
        return result
    prior_candidate = state.candidate
    if previous is not None and (now - previous).total_seconds() >= 10:
        state.candidate = None
    state.last_observed_at = now
    if state.destination_complete:
        return result
    if observation.source_mode != "live" or not observation.usable_motion:
        state.uncertain = True
        state.candidate = None
        return _changes(result, prior_candidate)
    speed = observation.speed_knots
    altitude = observation.altitude_feet if observation.usable_altitude else None
    if state.movement == "airborne" and altitude is not None:
        altitude_time = observation.altitude_observed_at
        if (
            state.last_altitude_observed_at is not None
            and altitude_time <= state.last_altitude_observed_at
        ):
            state.uncertain = True
            destination = observation.destination_distance_m
            if speed >= policy.landing_knots or not (
                destination is not None
                and 0 <= destination <= policy.destination_radius_m
            ):
                state.candidate = None
            return _changes(result, prior_candidate)
        state.last_altitude_observed_at = altitude_time
    kind = None
    dwell = 0.0
    target = state.movement
    event_kind = None
    destination = observation.destination_distance_m
    near_destination = (
        destination is not None and 0 <= destination <= policy.destination_radius_m
    )
    state.uncertain = False

    if (
        state.movement in ("unknown", "taxi_in", "probable_landed_rollout")
        and speed < policy.parking_knots
    ):
        kind, dwell = "parking", policy.parking_dwell
        target = (
            "parked"
            if state.movement == "unknown" or near_destination
            else "parked_at_stop"
        )
        event_kind = None if state.movement == "unknown" else "on_blocks"
    elif (
        state.movement in ("parked", "parked_at_stop") and speed > policy.movement_knots
    ):
        kind, dwell, target = "off_blocks", policy.movement_dwell, "taxi_out"
        # An intermediate stop belongs to the same service leg, but retains its own event.
        event_kind = "off_blocks"
    elif state.movement == "taxi_out":
        climb = (
            altitude is not None
            and state.parked_altitude is not None
            and altitude - state.parked_altitude >= policy.altitude_change_feet
        )
        if speed > policy.airborne_knots and climb:
            kind, dwell, target, event_kind = (
                "takeoff",
                policy.airborne_dwell,
                "airborne",
                "takeoff",
            )
        elif speed > policy.airborne_knots:
            state.uncertain = True
    elif state.movement == "airborne":
        if altitude is not None:
            state.max_airborne_altitude = max(
                state.max_airborne_altitude or altitude, altitude
            )
        descent = (
            altitude is not None
            and state.max_airborne_altitude is not None
            and state.max_airborne_altitude - altitude >= policy.altitude_change_feet
        )
        if near_destination and descent and speed < policy.landing_knots:
            kind, dwell, target, event_kind = (
                "landed",
                policy.landing_dwell,
                "probable_landed_rollout",
                "landed",
            )
        elif altitude is None or speed < policy.landing_knots:
            state.uncertain = True
    elif state.movement == "probable_landed_rollout":
        state.movement = "taxi_in"
    elif state.movement == "unknown":
        state.uncertain = True

    # Permit intermediate landing only after an operator has explicitly supplied
    # landed evidence; destination geography is intentionally not guessed elsewhere.
    if kind is None:
        state.candidate = None
        if state.movement == "parked" and altitude is not None:
            state.parked_altitude = altitude
        return _changes(result, prior_candidate)
    candidate = state.candidate
    if candidate is None or candidate.kind != kind:
        candidate = Candidate(
            kind=kind,
            since=now,
            latitude=observation.latitude,
            longitude=observation.longitude,
            altitude_feet=altitude,
        )
        state.candidate = candidate
    if (
        kind == "parking"
        and haversine_distance(
            candidate.latitude,
            candidate.longitude,
            observation.latitude,
            observation.longitude,
        )
        > policy.parking_radius_m
    ):
        state.candidate = Candidate(
            kind=kind,
            since=now,
            latitude=observation.latitude,
            longitude=observation.longitude,
            altitude_feet=altitude,
        )
        return _changes(result, prior_candidate)
    if kind == "landed" and (
        altitude is None
        or candidate.altitude_feet is None
        or abs(altitude - candidate.altitude_feet) > policy.landing_stable_feet
    ):
        state.candidate = Candidate(
            kind=kind,
            since=now,
            latitude=observation.latitude,
            longitude=observation.longitude,
            altitude_feet=altitude,
        )
        return _changes(result, prior_candidate)
    if kind == "landed":
        state.uncertain = True
        candidate.altitude_min = min(
            candidate.altitude_min if candidate.altitude_min is not None else altitude,
            altitude,
        )
        candidate.altitude_max = max(
            candidate.altitude_max if candidate.altitude_max is not None else altitude,
            altitude,
        )
        if candidate.altitude_max - candidate.altitude_min > policy.landing_stable_feet:
            state.candidate = None
            return _changes(result, prior_candidate)
        # Constant-size sufficient statistics for a noise-tolerant linear trend.
        elapsed = (observation.altitude_observed_at - candidate.since).total_seconds()
        candidate.sample_count += 1
        candidate.time_sum += elapsed
        candidate.altitude_sum += altitude
        candidate.time_squared_sum += elapsed * elapsed
        candidate.time_altitude_sum += elapsed * altitude
        if elapsed < dwell:
            return _changes(result, prior_candidate)
        count = candidate.sample_count
        denominator = count * candidate.time_squared_sum - candidate.time_sum**2
        slope = (
            (
                (
                    count * candidate.time_altitude_sum
                    - candidate.time_sum * candidate.altitude_sum
                )
                / denominator
            )
            if denominator > 0
            else float("inf")
        )
        if abs(slope) > policy.landing_trend_feet_per_second:
            state.candidate = None
            return _changes(result, prior_candidate)
    if (now - candidate.since).total_seconds() < dwell:
        return _changes(result, prior_candidate)
    state.movement = target
    state.uncertain = False
    state.candidate = None
    if target in ("parked", "parked_at_stop"):
        state.parked_altitude = altitude
    if target == "airborne":
        state.max_airborne_altitude = altitude
    if event_kind:
        state.destination_complete = event_kind == "on_blocks" and near_destination
        result.leg_completion = state.destination_complete
        result.emitted_events.append(
            FlightEvent(
                mission_id=observation.mission_id,
                leg_id=observation.leg_id,
                kind=event_kind,
                occurred_at=candidate.since,
                detected_at=now,
                source="inferred",
                evidence={
                    "movement": target,
                    "destination_complete": state.destination_complete,
                    "position_source": "collection_time",
                    "altitude_source": observation.altitude_validity_source,
                },
            )
        )
    return _changes(result, prior_candidate)


def _changes(result: DetectionResult, previous: Candidate | None) -> DetectionResult:
    current = result.state.candidate
    if previous != current:
        if previous:
            result.candidate_changes.append(
                {
                    "action": "reset",
                    "kind": previous.kind,
                    "since": previous.since.isoformat(),
                }
            )
        if current:
            result.candidate_changes.append(
                {
                    "action": "created",
                    "kind": current.kind,
                    "since": current.since.isoformat(),
                }
            )
    return result
