from app.models.route import RoutePoint
from app.services.mission_clock_endpoints import resolve_mission_endpoint_clocks
from app.services.overview_clock_location import ClockLocation


def test_resolves_takeoff_from_first_point_and_landing_from_last_point():
    route_points = [
        RoutePoint(
            latitude=38.9072,
            longitude=-77.0369,
        ),
        RoutePoint(
            latitude=45.0,
            longitude=-30.0,
        ),
        RoutePoint(
            latitude=48.8566,
            longitude=2.3522,
        ),
    ]
    takeoff_clock = ClockLocation(
        label="Washington, DC",
        time_zone="America/New_York",
    )
    landing_clock = ClockLocation(
        label="Paris, FR",
        time_zone="Europe/Paris",
    )

    def resolve_location(latitude: float, longitude: float) -> ClockLocation | None:
        if (latitude, longitude) == (38.9072, -77.0369):
            return takeoff_clock
        if (latitude, longitude) == (48.8566, 2.3522):
            return landing_clock
        raise AssertionError("only route endpoints may be resolved")

    result = resolve_mission_endpoint_clocks(
        route_points,
        resolve_location=resolve_location,
    )
    assert result == (
        takeoff_clock,
        landing_clock,
    )


def test_empty_route_returns_unavailable_endpoints_without_lookup():
    def unexpected_lookup(latitude: float, longitude: float) -> ClockLocation | None:
        raise AssertionError("endpoint lookup must not run for an empty route")

    result = resolve_mission_endpoint_clocks(
        [],
        resolve_location=unexpected_lookup,
    )
    assert result == (
        None,
        None,
    )
