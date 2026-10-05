"""Imported waypoint timing remains usable when endpoint roles are absent."""

from pathlib import Path

from app.services.kml_parser import parse_kml_file
from app.simulation.run_plan import prepare_mission_run
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
