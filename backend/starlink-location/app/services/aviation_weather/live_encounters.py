"""Bounded live route timing with the same speed rule as route-aware POIs."""

import hashlib
import json
from math import isfinite

from app.services.eta.calculator import ETACalculator
from app.services.eta.segment_timing import segment_speed
from app.services.position_freshness import position_observation, speed_is_fresh
from app.services.route_eta.calculator import (
    RouteETACalculator,
    project_point_to_line_segment,
)


def project_live_plan(route, planned, phase, telemetry, now):
    if phase == "pre_departure":
        return planned
    times = [None] * len(route.points)
    reasons = ["unavailable-plan"] * len(times)
    reference = int(now.timestamp() * 1000)
    current_position = None
    if phase == "post_arrival":
        current_position = float(len(times))
    elif phase == "in_flight":
        try:
            position = telemetry.position
            fresh = (
                position_observation(
                    position.latitude, position.longitude, position.observed_at, now
                )[1]
                == "fresh"
            )
            if (
                fresh
                and speed_is_fresh(position.speed, position.speed_observed_at, now)
                and route.timing_profile
                and route.timing_profile.has_timing_data
            ):
                current_position = _project_times(
                    route, position, reference, times, reasons
                )
        except (AttributeError, TypeError, ValueError, ArithmeticError, IndexError):
            times = [None] * len(route.points)
            reasons = ["unavailable-plan"] * len(times)
    revision = hashlib.sha256(
        json.dumps(
            [
                planned.revision,
                "route-estimated-utc-v1",
                reference,
                current_position,
                times,
                reasons,
            ],
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return planned.model_copy(
        update={
            "method": "route-estimated-utc-v1",
            "revision": revision,
            "reference_ms": reference,
            "current_position": current_position,
            "times_ms": tuple(times),
            "reasons": tuple(reasons),
        }
    )


def _project_times(route, position, reference, times, reasons):
    calculator = ETACalculator()
    projection = _unique_projection(route, position, calculator)
    index = projection["projected_waypoint_index"]
    point = route.points[index]
    endpoint = route.points[index + 1]
    length = calculator.calculate_distance(
        point.latitude, point.longitude, endpoint.latitude, endpoint.longitude
    )
    travelled = calculator.calculate_distance(
        point.latitude,
        point.longitude,
        projection["projected_lat"],
        projection["projected_lon"],
    )
    fraction = min(1.0, max(0.0, travelled / length)) if length else 0.0
    clock = float(reference)
    first = True
    for i in range(index, len(route.points) - 1):
        start, end = route.points[i : i + 2]
        distance = calculator.calculate_distance(
            start.latitude, start.longitude, end.latitude, end.longitude
        )
        remaining = distance * (1 - fraction) if i == index else distance
        speed = segment_speed(position.speed, end.expected_segment_speed_knots, first)
        if not isfinite(speed) or speed <= 0.5:
            break
        duration = distance / 1852 / speed * 3600000
        if i == index:
            times[i] = max(0, round(clock - duration * fraction))
            reasons[i] = None
        clock += remaining / 1852 / speed * 3600000
        times[i + 1], reasons[i + 1] = round(clock), None
        if remaining > 0.000001:
            first = False
    return index + fraction


def capture_flight_encounters(context, app_state):
    """Capture one live estimate; the weather service owns running this off-loop."""
    from datetime import datetime, timezone

    from app.services.flight_state import get_flight_state_manager
    from app.simulation.run_timing import published_replay

    planned = context.encounter_plan
    selection = published_replay(getattr(app_state, "simulation_run_service", None))
    if context.source == "simulation":
        if (
            selection is None
            or selection[0].route_id != context.route_id
            or selection[2].run_id != context.run_id
        ):
            return project_live_plan(
                context.route, planned, "in_flight", None, datetime.now(timezone.utc)
            )
        _, frame, mission = selection
        # Use published occurrence-aware progress, never infer completion by
        # skipping missing timestamps. Replay POIs use the same mission clock.
        reference = int(mission.simulation_time.timestamp() * 1000)
        current = _replay_position(
            context.route, getattr(frame, "progress_percent", None)
        )
        if current is None:
            return project_live_plan(
                context.route, planned, "in_flight", None, datetime.now(timezone.utc)
            )
        return planned.model_copy(
            update={
                "method": "mission-replay-utc-v1",
                "reference_ms": reference,
                "current_position": current,
                "revision": hashlib.sha256(
                    f"{planned.revision}:{mission.run_id}:{reference}".encode()
                ).hexdigest(),
            }
        )
    now = datetime.now(timezone.utc)
    phase = get_flight_state_manager().get_status().phase.value
    telemetry = None
    coordinator = getattr(app_state, "coordinator", None)
    if coordinator is not None:
        try:
            telemetry = coordinator.get_current_telemetry()
        except (AttributeError, TypeError, ValueError, RuntimeError):
            pass
    return project_live_plan(context.route, planned, phase, telemetry, now)


def _unique_projection(route, position, calculator):
    projection = RouteETACalculator(route).project_poi_to_route(
        position.latitude, position.longitude
    )
    index = projection["projected_waypoint_index"]

    def ordinal(i, lat, lon):
        start, end = route.points[i : i + 2]
        length = calculator.calculate_distance(
            start.latitude, start.longitude, end.latitude, end.longitude
        )
        distance = calculator.calculate_distance(
            start.latitude, start.longitude, lat, lon
        )
        return i + (min(1.0, max(0.0, distance / length)) if length else 0.0)

    selected = ordinal(index, projection["projected_lat"], projection["projected_lon"])
    for i in range(len(route.points) - 1):
        if i == index:
            continue
        start, end = route.points[i : i + 2]
        lat, lon, distance = project_point_to_line_segment(
            position.latitude,
            position.longitude,
            start.latitude,
            start.longitude,
            end.latitude,
            end.longitude,
        )
        if (
            distance <= projection["distance_to_route_meters"] + 1.0
            and abs(ordinal(i, lat, lon) - selected) > 0.000001
        ):
            raise ValueError("Ambiguous current route occurrence")
    return projection


def _replay_position(route, progress):
    if (
        not isinstance(progress, (int, float))
        or isinstance(progress, bool)
        or not isfinite(progress)
        or not 0 <= progress <= 100
    ):
        return None
    calculator = ETACalculator()
    lengths = [
        calculator.calculate_distance(a.latitude, a.longitude, b.latitude, b.longitude)
        for a, b in zip(route.points, route.points[1:])
    ]
    total = sum(lengths)
    if total <= 0:
        return None
    remaining = total * progress / 100
    for index, length in enumerate(lengths):
        if length > 0 and remaining < length:
            return index + remaining / length
        remaining -= length
    return float(len(lengths))
