"""Indeterminate geography must not stop accepted position simulation."""

from datetime import datetime, timedelta, timezone

import pytest

from app.mission.pop_status import PopStatusService
from app.simulation.kml_follower import KMLRouteFollower
from app.simulation.pop import SimulationPopObservationProvider
from app.simulation.run_plan import prepare_mission_run
from app.simulation.run_replay import project_run_frame
from tests.unit.simulation_run_fixtures import timed_plan_sources
from tests.unit.test_simulation_pop import catalog
from tests.unit.test_simulation_run_plan import multiplier_input


@pytest.fixture
def antipodal_plan(tmp_path):
    leg, routes, pois = timed_plan_sources(tmp_path)
    route = routes.get_route("replay")
    route.points = [route.points[0], route.points[-1]]
    route.points[0].altitude = 100
    route.points[-1].longitude = 180
    route.points[-1].altitude = 300
    route.metadata.point_count = 2
    return prepare_mission_run("mission-1", leg, multiplier_input(10), routes, pois)


def observation(service, telemetry, plan, seconds):
    return service.snapshot(
        telemetry,
        route=plan.artifacts.route,
        projector=plan.artifacts.projector,
        catalog=catalog(("a", 0, 0), ("b", 0, 180)),
        mode="simulation",
        enabled=True,
        now=plan.preview.planned_departure + timedelta(seconds=seconds),
        observed_now=datetime.now(timezone.utc),
    )


def test_antipodal_kml_preserves_legacy_positions_and_altitude(antipodal_plan):
    follower = KMLRouteFollower(antipodal_plan.artifacts.route, deviation_degrees=0)
    first, second = follower.get_position(0.25), follower.get_position(0.75)
    assert (first["latitude"], first["longitude"], first["altitude"]) == (0, 45, 150)
    assert (second["latitude"], second["longitude"], second["altitude"]) == (
        0,
        135,
        250,
    )


def test_antipodal_ordinary_coordinator_emits_current_position_and_pop(
    antipodal_plan, coordinator, monkeypatch
):
    import app.simulation.position as position_module

    follower = KMLRouteFollower(antipodal_plan.artifacts.route, deviation_degrees=0)
    coordinator.position_sim.set_route_follower(follower)
    # Keep each seek's exact progress while exercising real coordinator collection.
    clock = coordinator.position_sim.last_update_time
    monkeypatch.setattr(position_module.time, "time", lambda: clock)
    service = PopStatusService(observation_provider=SimulationPopObservationProvider())
    for progress, lon, ip, city in [
        (0.25, 45, "192.0.2.1", "A"),
        (0.75, 135, "192.0.2.2", "B"),
    ]:
        coordinator.set_position_progress(progress)
        telemetry = coordinator.update()
        assert (telemetry.position.latitude, telemetry.position.longitude) == (0, lon)
        result = observation(service, telemetry, antipodal_plan, progress * 1200)
        assert (
            result["pop_observation"]["ip"],
            result["pop_observation"]["entry"]["city"],
        ) == (ip, city)
        assert result["pop_forecast"]["status"] == "indeterminate"
        assert result["pop_forecast"]["transitions"] == []


def test_antipodal_replay_preserves_projected_position_clock_and_terminal_pop(
    antipodal_plan, coordinator
):
    service = PopStatusService(observation_provider=SimulationPopObservationProvider())
    previous = None
    for seconds, lon, altitude, ip in [
        (300, -45, 150, "192.0.2.1"),
        (900, -135, 250, "192.0.2.2"),
        (1200, 180, 300, "192.0.2.2"),
    ]:
        mission_time = antipodal_plan.preview.planned_departure + timedelta(
            seconds=seconds
        )
        frame = project_run_frame(antipodal_plan, mission_time, previous)
        previous = frame
        assert frame.simulation_time == mission_time
        assert (frame.position.latitude, frame.position.longitude) == (0, lon)
        assert frame.position.altitude == pytest.approx(altitude * 3.28084)
        telemetry = coordinator.update(replay_frame=frame)
        result = observation(service, telemetry, antipodal_plan, seconds)
        assert result["pop_observation"]["ip"] == ip
        assert result["pop_forecast"]["status"] == "indeterminate"
        assert result["pop_forecast"]["transitions"] == []
    assert previous.progress_percent == 100
    assert previous.phase.value == "post_arrival"
    assert previous.position.speed == 0
