"""Historical mission time and real acquisition freshness stay separate."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.flight_status import FlightPhase
from app.models.poi import POICreate
from app.services.flight_state import get_flight_state_manager
from app.services.position_freshness import position_observation
from app.simulation.run_runtime import SimulationRunRuntime
from app.simulation.run_service import SimulationRunService
from app.simulation.run_timing import mission_time_context, planned_poi_eta
from tests.unit.simulation_run_fixtures import Clocks, timed_plan_sources
from tests.unit.test_simulation_run_plan import multiplier_input


@pytest.fixture
def timing(tmp_path, coordinator, monkeypatch):
    import app.core.metrics.metric_updater as metrics
    import app.simulation.coordinator as simulator

    clocks = Clocks()
    clocks.utc = datetime.now(timezone.utc)

    class RealClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clocks.utc

    monkeypatch.setattr(simulator, "datetime", RealClock)
    monkeypatch.setattr(metrics, "datetime", RealClock)
    leg, routes, pois = timed_plan_sources(tmp_path)
    runtime = SimulationRunRuntime(clocks.monotonic, clocks.utc_now, "simulation")
    service = SimulationRunService(runtime, routes, pois)
    plan = service.prepare_plan("mission-1", leg, multiplier_input(10))
    runtime.commit_tick(runtime.prepare_start(plan))
    coordinator.set_route_manager(routes)
    flight = get_flight_state_manager()
    old = flight.checkpoint()

    def publish(telemetry, tick):
        metrics.update_metrics_from_telemetry(
            telemetry,
            active_route=tick.plan.artifacts.route,
            poi_manager=pois,
            mission_context=mission_time_context(tick.status),
            simulation_plan=tick.plan,
            simulation_frame=tick.frame,
        )

    yield service, clocks, coordinator, publish
    flight.restore_checkpoint(old)


def arrival_poi(service):
    plan = service.runtime.selected_plan()
    poi = service.poi_manager.create_poi(
        POICreate(
            name="Arrival",
            latitude=0,
            longitude=2,
            route_id="replay",
            mission_id="mission-1",
            kind="arrival",
            expected_arrival_time=plan.preview.planned_arrival,
        ),
        active_route=plan.artifacts.route,
        generated_source="mission-timeline",
    )
    return poi


def test_old_planned_date_does_not_make_telemetry_stale(timing):
    service, clocks, coordinator, publish = timing
    poi = arrival_poi(service)
    clocks.advance(12)
    telemetry = service.collect(coordinator, publish)
    context = mission_time_context(service.status())
    assert (
        position_observation(0, 0.4, telemetry.position.observed_at, clocks.utc)[1]
        == "fresh"
    )
    assert telemetry.position.observed_at == clocks.utc
    flight = get_flight_state_manager().get_status(mission_now=context.simulation_time)
    assert flight.time_since_departure_seconds == 120
    assert (
        planned_poi_eta(service.runtime.selected_plan(), service.runtime.frame(), poi)
        == 1080
    )
    assert (
        service.status().run.expected_runtime_seconds
        - service.status().run.elapsed_real_seconds
    ) == 108


def test_simulation_arrival_is_immediate(timing):
    service, clocks, coordinator, publish = timing
    service.collect(coordinator, publish)
    assert (
        get_flight_state_manager()
        .get_status(mission_now=service.status().run.simulation_time)
        .phase
        == FlightPhase.IN_FLIGHT
    )
    clocks.advance(120)
    service.collect(coordinator, publish)
    status = get_flight_state_manager().get_status(
        mission_now=service.status().run.simulation_time
    )
    assert status.phase == FlightPhase.POST_ARRIVAL
    assert status.arrival_time == service.status().run.planned_arrival
    assert status.time_since_departure_seconds == 1200


def test_completed_mission_context_is_frozen_but_real_freshness_continues(timing):
    service, clocks, coordinator, publish = timing
    clocks.advance(120)
    service.collect(coordinator, publish)
    before = mission_time_context(service.status())
    clocks.advance(50)
    telemetry = service.collect(coordinator, publish)
    assert mission_time_context(service.status()) == before
    assert telemetry.position.observed_at == clocks.utc
    assert telemetry.position.speed == 0
    assert (
        get_flight_state_manager()
        .get_status(mission_now=before.simulation_time)
        .time_since_departure_seconds
        == 1200
    )


def test_failed_observation_cannot_renew_age(timing, monkeypatch):
    service, clocks, coordinator, publish = timing
    before = service.collect(coordinator, publish)
    clocks.advance(31)

    def fail():
        raise RuntimeError("Collection failed")

    monkeypatch.setattr(coordinator.network_sim, "update", fail)
    with pytest.raises(RuntimeError):
        service.collect(coordinator, publish)
    retained = coordinator.get_current_telemetry()
    assert retained.position.observed_at == before.position.observed_at
    assert (
        position_observation(
            retained.position.latitude,
            retained.position.longitude,
            retained.position.observed_at,
            clocks.utc,
        )[1]
        == "stale"
    )


def test_speed_smoothing_uses_simulated_intervals():
    from app.services.eta_calculator import ETACalculator

    calc = ETACalculator(smoothing_duration_seconds=120)
    calc.update_speed(300, sample_time_seconds=0)
    calc.update_speed(600, sample_time_seconds=121)
    assert calc.get_smoothed_speed() == 600


def test_paced_generated_poi_uses_authoritative_schedule(timing):
    service, clocks, coordinator, publish = timing
    poi = arrival_poi(service)
    clocks.advance(12)
    service.collect(coordinator, publish)
    assert (
        planned_poi_eta(service.runtime.selected_plan(), service.runtime.frame(), poi)
        == 1080
    )
    poi.expected_arrival_time = None
    assert (
        planned_poi_eta(service.runtime.selected_plan(), service.runtime.frame(), poi)
        == 1080
    )
    poi.latitude = float("nan")
    assert (
        planned_poi_eta(service.runtime.selected_plan(), service.runtime.frame(), poi)
        is None
    )


def test_no_context_keeps_live_eta_and_detection_behavior(timing):
    service, clocks, _coordinator, _publish = timing
    assert mission_time_context(service.status()) is not None
    service.runtime.cancel("Deactivated")
    assert mission_time_context(service.status()) is None
    flight = get_flight_state_manager()
    flight.reset()
    flight.check_departure(300, observed_at=clocks.utc)
    assert flight.get_status().phase == FlightPhase.PRE_DEPARTURE
    flight.check_departure(300, observed_at=clocks.utc + timedelta(seconds=11))
    assert flight.get_status().phase == FlightPhase.IN_FLIGHT


def test_metric_publication_failure_propagates_for_paced_frames(timing, monkeypatch):
    from app.core.metrics import metric_updater

    service, _clocks, coordinator, publish = timing

    def fail(*args, **kwargs):
        raise RuntimeError("ETA publication failure")

    monkeypatch.setattr(
        metric_updater, "starlink_flight_phase", type("Broken", (), {"set": fail})()
    )
    with pytest.raises(RuntimeError):
        service.collect(coordinator, publish)
    assert service.status().state == "failed"


def test_anticipated_eta_accepts_explicit_mission_now(timing):
    from app.models.route import RouteWaypoint
    from app.services.eta_calculator import ETACalculator

    service, _clocks, _coordinator, _publish = timing
    plan = service.runtime.selected_plan()
    route = plan.artifacts.route.model_copy(deep=True)
    route.waypoints = [
        RouteWaypoint(
            name="Arrival",
            latitude=0,
            longitude=2,
            order=0,
            expected_arrival_time=plan.preview.planned_arrival,
        )
    ]
    poi = arrival_poi(service)
    now = plan.preview.planned_departure + timedelta(seconds=120)
    assert (
        ETACalculator()._calculate_route_aware_eta_anticipated(
            0, 0, poi, route, mission_now=now
        )
        == 1080
    )


def test_paced_route_and_mission_progress_metrics_follow_candidate(timing):
    from app.core.metrics.prometheus_metrics import (
        mission_phase_state,
        starlink_route_progress_percent,
    )

    service, clocks, coordinator, publish = timing
    clocks.advance(12)
    service.collect(coordinator, publish)
    assert starlink_route_progress_percent.labels(
        route_name="Replay"
    )._value.get() == pytest.approx(20)
    assert mission_phase_state.labels(mission_id="mission-1")._value.get() == 1
