"""Unit tests for active v2 mission-leg context resolution."""

import pytest

from app.mission.models import Mission, MissionLeg, TransportConfig
from app.mission.storage import save_mission_v2
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
from app.services.route_manager import RouteManager


def _route(route_id: str) -> ParsedRoute:
    return ParsedRoute(
        metadata=RouteMetadata(
            name=route_id,
            file_path=f"/tmp/{route_id}.kml",
            point_count=2,
        ),
        points=[
            RoutePoint(latitude=0.0, longitude=0.0, sequence=0),
            RoutePoint(latitude=1.0, longitude=1.0, sequence=1),
        ],
    )


def _mission(mission_id: str, leg_id: str, route_id: str) -> Mission:
    return Mission(
        id=mission_id,
        name=mission_id,
        legs=[
            MissionLeg(
                id=leg_id,
                name=leg_id,
                route_id=route_id,
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            )
        ],
    )


@pytest.fixture
def route_manager(tmp_path) -> RouteManager:
    manager = RouteManager(routes_dir=tmp_path / "routes")
    manager.add_route("route-a", _route("route-a"))
    manager.add_route("route-b", _route("route-b"))
    return manager


@pytest.fixture
def v2_mission() -> Mission:
    return _mission("mission-a", "leg-a", "route-a")


def test_resolver_returns_parent_leg_and_route_after_fresh_read(
    route_manager, v2_mission
) -> None:
    from app.mission.active_context import resolve_active_mission_leg_context

    save_mission_v2(_mission("mission-b", "leg-b", "route-b"))
    v2_mission.legs[0].is_active = True
    save_mission_v2(v2_mission)
    assert route_manager.activate_route("route-a") is True

    resolution = resolve_active_mission_leg_context(route_manager)

    assert resolution.state == "available"
    assert resolution.context is not None
    assert resolution.context.parent_mission_id == v2_mission.id
    assert resolution.context.parent_mission.id == v2_mission.id
    assert resolution.context.leg.id == "leg-a"
    assert resolution.context.route_id == "route-a"
    assert resolution.context.route is route_manager.get_route("route-a")


@pytest.mark.parametrize(
    ("state_setup", "expected"),
    [
        ("none", "no_active_mission"),
        ("blank_route", "route_unavailable"),
        ("missing_route", "route_unavailable"),
        ("route_mismatch", "route_unavailable"),
        ("two_active_legs", "inconsistent_active_mission"),
    ],
)
def test_resolver_returns_explicit_failure_without_context(
    state_setup, expected, route_manager
) -> None:
    from app.mission.active_context import resolve_active_mission_leg_context

    mission_a = _mission("mission-a", "leg-a", "route-a")
    mission_b = _mission("mission-b", "leg-b", "route-b")

    if state_setup == "blank_route":
        mission_a.legs[0].route_id = " "
        mission_a.legs[0].is_active = True
    elif state_setup == "missing_route":
        mission_a.legs[0].route_id = "missing-route"
        mission_a.legs[0].is_active = True
    elif state_setup == "route_mismatch":
        mission_a.legs[0].is_active = True
        assert route_manager.activate_route("route-b") is True
    elif state_setup == "two_active_legs":
        mission_a.legs[0].is_active = True
        mission_b.legs[0].is_active = True

    save_mission_v2(mission_a)
    save_mission_v2(mission_b)

    resolution = resolve_active_mission_leg_context(route_manager)

    assert resolution.state == expected
    assert resolution.context is None
