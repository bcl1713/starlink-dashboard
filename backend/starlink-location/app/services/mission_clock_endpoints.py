from collections.abc import Callable, Sequence

from app.models.route import RoutePoint
from app.services.overview_clock_location import ClockLocation


def resolve_mission_endpoint_clocks(
    route_points: Sequence[RoutePoint],
    *,
    resolve_location: Callable[[float, float], ClockLocation | None],
) -> tuple[ClockLocation | None, ClockLocation | None]:
    """Resolve takeoff and landing clocks from the route endpoints."""
    if not route_points:
        return (
            None,
            None,
        )
    takeoff_point = route_points[0]
    landing_point = route_points[-1]
    return (
        resolve_location(
            takeoff_point.latitude,
            takeoff_point.longitude,
        ),
        resolve_location(
            landing_point.latitude,
            landing_point.longitude,
        ),
    )
