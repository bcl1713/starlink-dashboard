"""Shared departure adjustment and effective Manual AR splice geometry."""

from app.mission.derived_route import (
    build_derived_route_estimate,
    derived_route_for_estimate,
)
from app.mission.timeline_builder.calculator import (
    TimelineComputationError,
    route_with_adjusted_departure,
)
from app.simulation.run_route import normalize_timed_route


def prepare_effective_route(leg, route_manager, normalize_for_simulation=False):
    if not leg.route_id:
        raise TimelineComputationError("Mission is missing route_id")

    route = route_manager.get_route(leg.route_id)
    if not route:
        raise TimelineComputationError(f"Route {leg.route_id} not loaded")

    if normalize_for_simulation:
        route = normalize_timed_route(route)
    route = route_with_adjusted_departure(route, leg.adjusted_departure_time)
    splice = leg.transports.manual_route_splice
    selected_track = None
    splice_available = False
    if splice:
        selected_track = next(
            (
                track
                for track in leg.transports.manual_aar_tracks
                if track.id == splice.enabled_track_id
            ),
            None,
        )
        if selected_track:
            estimate = build_derived_route_estimate(route, selected_track, splice)
            if normalize_for_simulation and not estimate.available:
                raise TimelineComputationError(
                    f"Selected diversion is unavailable: {estimate.unavailable_reason}"
                )
            splice_available = estimate.available
            route = derived_route_for_estimate(route, estimate)
            if normalize_for_simulation and splice_available:
                for point in route.points:
                    point.expected_segment_speed_knots = None
        elif normalize_for_simulation:
            raise TimelineComputationError("Selected diversion track is missing")
    if normalize_for_simulation:
        route = normalize_timed_route(route)
    else:
        route = route.model_copy(deep=True)
    return route
