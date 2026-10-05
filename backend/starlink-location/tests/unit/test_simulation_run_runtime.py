"""Behavioral clock, event cursor, endpoint, and publication contracts."""

from dataclasses import replace
from datetime import timedelta

import pytest

from app.models.flight_status import FlightPhase
from app.simulation.run_plan import prepare_mission_run
from app.simulation.run_runtime import SimulationRunRuntime
from tests.unit.simulation_run_fixtures import Clocks, timed_plan_sources
from tests.unit.test_simulation_run_plan import multiplier_input


@pytest.fixture
def setup(tmp_path):
    clocks = Clocks()
    leg, routes, pois = timed_plan_sources(tmp_path)
    plan = prepare_mission_run("mission-1", leg, multiplier_input(10), routes, pois)
    runtime = SimulationRunRuntime(clocks.monotonic, clocks.utc_now, "simulation")
    return runtime, clocks, plan


def tick(runtime):
    return runtime.commit_tick(runtime.prepare_tick())


def test_runtime_uses_monotonic_clock(setup):
    runtime, clocks, plan = setup
    runtime.commit_tick(runtime.prepare_start(plan))
    clocks.advance(12)
    clocks.utc -= timedelta(hours=1)
    tick(runtime)
    assert (
        runtime.status().run.simulation_time
        == plan.preview.planned_departure + timedelta(seconds=120)
    )
    assert runtime.status().run.elapsed_real_seconds == 12


def test_completion_holds_exact_endpoint(setup):
    runtime, clocks, plan = setup
    runtime.commit_tick(runtime.prepare_start(plan))
    clocks.advance(120)
    tick(runtime)
    assert runtime.status().state == "completed"
    assert runtime.frame().progress_percent == 100
    assert runtime.frame().phase == FlightPhase.POST_ARRIVAL
    assert (runtime.frame().position.latitude, runtime.frame().position.longitude) == (
        0,
        2,
    )
    assert runtime.status().run.processed_event_count == len(plan.replay_events)
    clocks.advance(1000)
    assert runtime.prepare_tick() is None
    assert runtime.frame().position.longitude == 2
    assert runtime.seconds_until_next_tick() == 1


def test_reads_do_not_process_events(setup):
    runtime, clocks, plan = setup
    runtime.commit_tick(runtime.prepare_start(plan))
    before = runtime.status()
    clocks.advance(10)
    for _ in range(100):
        assert runtime.status().revision == before.revision
        assert runtime.status().run == before.run
    assert runtime.status().served_at != before.served_at


def test_uncommitted_tick_is_invisible(setup):
    runtime, clocks, plan = setup
    runtime.commit_tick(runtime.prepare_start(plan))
    before = runtime.status().run
    clocks.advance(100)
    candidate = runtime.prepare_tick()
    assert candidate.frame.processed_event_count > before.processed_event_count
    assert runtime.status().run == before
    assert runtime.frame().simulation_time == before.simulation_time


def test_stale_tick_cannot_commit(setup):
    runtime, clocks, plan = setup
    runtime.commit_tick(runtime.prepare_start(plan))
    clocks.advance(1)
    candidate = runtime.prepare_tick()
    runtime.cancel("Deactivated")
    with pytest.raises(ValueError):
        runtime.commit_tick(candidate)
    assert runtime.status().state == "cancelled"
    assert runtime.frame() is None and runtime.selected_plan() is None


def test_terminal_error_does_not_certify_completion(setup):
    runtime, clocks, plan = setup
    runtime.commit_tick(runtime.prepare_start(plan))
    before = runtime.status().run
    clocks.advance(121)
    runtime.prepare_tick()
    runtime.fail("collection_error", "Cannot collect")
    after = runtime.status().run
    assert runtime.status().state == "failed"
    assert after.observed_at == before.observed_at
    assert after.simulation_time == before.simulation_time
    assert after.processed_event_count == before.processed_event_count
    assert after.error.code == "collection_error"


def test_late_completion_reports_actual_lateness(setup):
    runtime, clocks, plan = setup
    runtime.commit_tick(runtime.prepare_start(plan))
    clocks.advance(125)
    tick(runtime)
    assert runtime.status().run.elapsed_real_seconds == 125
    assert runtime.status().run.completion_lateness_seconds == 5
    assert runtime.status().run.simulation_time == plan.preview.planned_arrival


def test_publication_delay_counts_towards_lateness(setup):
    runtime, clocks, plan = setup
    runtime.commit_tick(runtime.prepare_start(plan))
    clocks.advance(120)
    candidate = runtime.prepare_tick()
    clocks.advance(5)
    runtime.commit_tick(candidate)
    assert runtime.status().run.completion_lateness_seconds == 5


def test_same_leg_restart_has_new_cursor_and_handoff_state(setup):
    runtime, clocks, plan = setup
    runtime.commit_tick(runtime.prepare_start(plan))
    old = runtime.status().run.run_id
    clocks.advance(120)
    tick(runtime)
    runtime.commit_tick(runtime.prepare_start(plan))
    assert runtime.status().run.run_id != old
    assert runtime.frame().progress_percent == 0
    assert runtime.frame().processed_event_count < len(plan.replay_events)
    assert runtime.frame().x_context.current_satellite_id == "X-1"


@pytest.mark.parametrize("multiplier", [0.1, 1, 10, 1000])
def test_segment_speed_is_per_simulated_second(setup, multiplier):
    runtime, clocks, plan = setup
    from app.simulation.run_plan import normalize_pacing

    normalized = normalize_pacing(multiplier_input(multiplier), 1200)
    plan = replace(
        plan,
        normalized=normalized,
        preview=plan.preview.model_copy(update=normalized.model_dump()),
    )
    runtime.commit_tick(runtime.prepare_start(plan))
    clocks.advance(150 / multiplier)
    tick(runtime)
    assert runtime.frame().position.longitude == pytest.approx(0.5)
    first = runtime.frame().position.speed
    clocks.advance(600 / multiplier)
    tick(runtime)
    assert runtime.frame().position.longitude == pytest.approx(1.5)
    assert first == pytest.approx(runtime.frame().position.speed * 3)


def test_deadline_aware_delay_and_mode_change(setup):
    runtime, clocks, plan = setup
    runtime.commit_tick(runtime.prepare_start(plan))
    clocks.advance(119.75)
    assert runtime.seconds_until_next_tick() == 0.25
    runtime.set_service_mode("live")
    assert runtime.status().state == "cancelled"
    assert runtime.status().service_mode == "live"
    with pytest.raises(ValueError):
        runtime.prepare_start(plan)


def test_multiple_x_handoffs_are_committed_and_restart_clears_them(setup):
    runtime, clocks, plan = setup
    assignments = (
        (plan.preview.planned_departure, "X-1", None),
        (plan.preview.planned_departure + timedelta(seconds=100), "X-2", "first"),
        (plan.preview.planned_departure + timedelta(seconds=200), "X-3", "second"),
    )
    plan = replace(plan, artifacts=replace(plan.artifacts, x_assignments=assignments))
    runtime.commit_tick(runtime.prepare_start(plan))
    clocks.advance(30)
    tick(runtime)
    assert runtime.frame().x_context.current_satellite_id == "X-3"
    assert runtime.frame().x_context.handoff["transition_id"] == "second"
    assert runtime.frame().x_assignment_count == 3
    runtime.commit_tick(runtime.prepare_start(plan))
    assert runtime.frame().x_assignment_count == 1
    assert runtime.frame().x_context.current_satellite_id == "X-1"


def test_antimeridian_and_stationary_segment(setup):
    from app.mission.timeline_builder.calculator import RouteTemporalProjector
    from app.models.route import RoutePoint
    from app.simulation.run_replay import project_run_frame

    _runtime, _clocks, plan = setup
    start = plan.preview.planned_departure
    route = plan.artifacts.route.model_copy(deep=True)
    route.points = [
        RoutePoint(
            latitude=0,
            longitude=lon,
            sequence=i,
            expected_arrival_time=start + timedelta(seconds=sec),
        )
        for i, (lon, sec) in enumerate(
            [(179, 0), (-179, 300), (-179, 600), (-178, 1200)]
        )
    ]
    projector = RouteTemporalProjector(route, start, plan.preview.planned_arrival)
    plan = replace(
        plan, artifacts=replace(plan.artifacts, route=route, projector=projector)
    )
    frame = project_run_frame(plan, start + timedelta(seconds=150), None)
    assert abs(frame.position.longitude) == 180
    frame = project_run_frame(plan, start + timedelta(seconds=450), frame)
    assert frame.position.longitude == -179
    assert frame.position.speed == 0


def test_generated_x_schedule_drives_paced_handoff(tmp_path):
    from app.mission.models import XTransition

    leg, routes, pois = timed_plan_sources(tmp_path)
    leg.transports.x_transitions = [
        XTransition(id="handoff", latitude=0, longitude=1, target_satellite_id="X-2")
    ]
    plan = prepare_mission_run("mission-1", leg, multiplier_input(10), routes, pois)
    clocks = Clocks()
    runtime = SimulationRunRuntime(clocks.monotonic, clocks.utc_now, "simulation")
    runtime.commit_tick(runtime.prepare_start(plan))
    clocks.advance(30)
    tick(runtime)
    assert runtime.frame().x_context.current_satellite_id == "X-2"
