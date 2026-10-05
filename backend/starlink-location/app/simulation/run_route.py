"""Validate and privately normalize timed routes before replay calculation."""

import math
from itertools import pairwise

from app.mission.timeline_builder.calculator import (
    TimelineComputationError,
    derive_mission_window,
    ensure_timezone,
)
from app.models.route import ParsedRoute, RouteTimingProfile
from app.services.route_eta_calculator import RouteETACalculator


def normalize_timed_route(source: ParsedRoute) -> ParsedRoute:
    route = source.model_copy(deep=True)
    if len(route.points) < 2:
        raise TimelineComputationError("At least two route points are required")
    for point in [*route.points, *route.waypoints]:
        if (
            not math.isfinite(point.latitude)
            or not -90 <= point.latitude <= 90
            or not math.isfinite(point.longitude)
            or not -180 <= point.longitude <= 180
            or (point.altitude is not None and not math.isfinite(point.altitude))
        ):
            raise TimelineComputationError("Route coordinates must be finite and valid")
        if point.expected_arrival_time:
            point.expected_arrival_time = ensure_timezone(point.expected_arrival_time)
    profile = route.timing_profile

    if profile:
        if profile.departure_time:
            profile.departure_time = ensure_timezone(profile.departure_time)
        if profile.arrival_time:
            profile.arrival_time = ensure_timezone(profile.arrival_time)
    start, end = derive_mission_window(route)
    if profile and profile.departure_time and profile.arrival_time:
        start, end = profile.departure_time, profile.arrival_time
    if end <= start:
        raise TimelineComputationError("Arrival must follow departure")
    route.timing_profile = profile or RouteTimingProfile()
    route.timing_profile.departure_time = start
    route.timing_profile.arrival_time = end
    route.timing_profile.total_expected_duration_seconds = (end - start).total_seconds()
    route.timing_profile.has_timing_data = True
    route.timing_profile.segment_count_with_timing = len(route.points) - 1
    for point in [*route.points, *route.waypoints]:
        if (
            point.expected_arrival_time
            and not start <= point.expected_arrival_time <= end
        ):
            raise TimelineComputationError(
                "Timing anchor lies outside the flight window"
            )
    for point, expected in [(route.points[0], start), (route.points[-1], end)]:
        if point.expected_arrival_time and point.expected_arrival_time != expected:
            raise TimelineComputationError(
                "Endpoint timing contradicts the flight window"
            )
        point.expected_arrival_time = expected
    calculator = RouteETACalculator(route)
    distances = [0.0]
    for previous, current in zip(route.points, route.points[1:]):
        distances.append(
            distances[-1]
            + calculator._haversine_distance(
                previous.latitude,
                previous.longitude,
                current.latitude,
                current.longitude,
            )
        )
    if distances[-1] <= 0:
        raise TimelineComputationError("Route must have positive distance")
    anchors = [
        i for i, p in enumerate(route.points) if p.expected_arrival_time is not None
    ]
    for left, right in pairwise(anchors):
        a, b = (
            route.points[left].expected_arrival_time,
            route.points[right].expected_arrival_time,
        )
        if b <= a:
            raise TimelineComputationError("Timing anchors must be strictly increasing")
        span = distances[right] - distances[left]
        for i in range(left + 1, right):
            fraction = (
                (distances[i] - distances[left]) / span
                if span
                else (i - left) / (right - left)
            )
            route.points[i].expected_arrival_time = a + (b - a) * fraction
    for i, current in enumerate(route.points[1:], 1):
        previous = route.points[i - 1]
        duration = (
            current.expected_arrival_time - previous.expected_arrival_time
        ).total_seconds()
        if duration <= 0:
            raise TimelineComputationError(
                "Every normalized segment must have positive duration; "
                "remove duplicate untimed vertices or provide distinct timing anchors"
            )
        speed = (distances[i] - distances[i - 1]) / duration / 0.514444
        declared = current.expected_segment_speed_knots
        if declared is not None and (
            not math.isfinite(declared)
            or declared < 0
            or not math.isclose(declared, speed, rel_tol=0.05, abs_tol=1)
        ):
            raise TimelineComputationError(
                "Segment speed contradicts its timing anchors"
            )
        current.expected_segment_speed_knots = speed
    return route
