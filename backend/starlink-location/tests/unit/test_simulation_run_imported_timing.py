"""Imported waypoint timing remains usable when endpoint roles are absent."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.models.route import RouteWaypoint
from app.services.kml_parser import parse_kml_file
from app.simulation.run_plan import SimulationValidationError, prepare_mission_run
from tests.unit.simulation_run_fixtures import BASE, timed_plan_sources
from tests.unit.test_simulation_run_plan import multiplier_input


def test_adjusted_departure_applies_to_imported_waypoint_only_timing(tmp_path):
    leg, routes, pois = timed_plan_sources(tmp_path)
    asset = (
        Path(__file__).resolve().parents[4]
        / "docs/missions/acceptance-assets/paced-simulation-route.kml"
    )
    route = parse_kml_file(asset)
    assert route.timing_profile is None
    routes._routes[leg.route_id] = route
    plan = prepare_mission_run("mission-1", leg, multiplier_input(10), routes, pois)
    assert plan.preview.planned_departure == leg.adjusted_departure_time
    assert plan.preview.flight_duration_seconds == 1200
    assert (
        plan.artifacts.route.points[0].expected_arrival_time
        == leg.adjusted_departure_time
    )
    assert route.waypoints[0].expected_arrival_time == BASE


def test_imported_matching_waypoint_anchors_preserve_segment_pacing(tmp_path):
    leg, routes, pois = timed_plan_sources(tmp_path)
    asset = (
        Path(__file__).resolve().parents[4]
        / "docs/missions/acceptance-assets/paced-simulation-route.kml"
    )
    routes._routes[leg.route_id] = parse_kml_file(asset)
    plan = prepare_mission_run("mission-1", leg, multiplier_input(10), routes, pois)
    points = plan.artifacts.route.points
    assert (
        points[1].expected_arrival_time - points[0].expected_arrival_time
    ).total_seconds() == 300
    assert (
        points[2].expected_arrival_time - points[1].expected_arrival_time
    ).total_seconds() == 600
    assert (
        points[1].expected_segment_speed_knots
        > 3 * points[2].expected_segment_speed_knots
    )


@pytest.mark.parametrize("adjusted_days", [0, 1])
def test_imported_alternate_airports_do_not_extend_or_reject_main_flight(
    tmp_path, adjusted_days
):
    leg, routes, pois = timed_plan_sources(tmp_path)
    asset = Path(__file__).resolve().parents[4] / "routes/Leg 6 Rev 6.kml"
    source = parse_kml_file(asset)
    before = source.model_dump()
    routes._routes[leg.route_id] = source
    departure = datetime(2025, 11, 4, 9, 15, tzinfo=timezone.utc)
    arrival = datetime(2025, 11, 4, 23, 17, 52, tzinfo=timezone.utc)
    shift = timedelta(days=adjusted_days)
    leg.adjusted_departure_time = departure + shift if adjusted_days else None

    plan = prepare_mission_run("mission-1", leg, multiplier_input(10), routes, pois)

    assert plan.preview.planned_departure == departure + shift
    assert plan.preview.planned_arrival == arrival + shift
    assert plan.preview.flight_duration_seconds == 50572
    assert len(plan.artifacts.route.points) == 76
    assert len(plan.artifacts.route.waypoints) == 89
    assert any(
        w.role == "alternate" and w.expected_arrival_time > plan.preview.planned_arrival
        for w in plan.artifacts.route.waypoints
    )
    assert source.model_dump() == before


@pytest.mark.parametrize(
    "role,seconds,accepted",
    [
        ("alternate", -1, True),
        ("alternate", 1300, True),
        ("waypoint", 1300, False),
        (None, 1300, False),
    ],
)
def test_only_alternate_waypoint_times_may_lie_outside_main_window(
    tmp_path, role, seconds, accepted
):
    leg, routes, pois = timed_plan_sources(tmp_path)
    routes.get_route(leg.route_id).waypoints.append(
        RouteWaypoint(
            name="Outside",
            latitude=0,
            longitude=3,
            order=0,
            role=role,
            expected_arrival_time=BASE + timedelta(seconds=seconds),
        )
    )
    if accepted:
        plan = prepare_mission_run("mission-1", leg, multiplier_input(10), routes, pois)
        assert plan.preview.flight_duration_seconds == 1200
    else:
        with pytest.raises(
            SimulationValidationError, match="outside the flight window"
        ):
            prepare_mission_run("mission-1", leg, multiplier_input(10), routes, pois)
