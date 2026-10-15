"""Collection failure compensation and lifecycle ownership contracts."""

import pytest
from fastapi import HTTPException

from app.models.simulation_run import SimulationStart
from app.simulation.run_runtime import SimulationRunRuntime
from app.simulation.run_service import SimulationRunService
from tests.unit.simulation_run_fixtures import Clocks, timed_plan_sources
from tests.unit.test_simulation_run_plan import multiplier_input


@pytest.fixture
def setup(tmp_path, coordinator):
    clocks = Clocks()
    leg, routes, pois = timed_plan_sources(tmp_path)
    runtime = SimulationRunRuntime(clocks.monotonic, clocks.utc_now, "simulation")
    service = SimulationRunService(runtime, routes, pois)
    plan = service.prepare_plan("mission-1", leg, multiplier_input(10))
    coordinator.set_route_manager(routes)
    runtime.commit_tick(runtime.prepare_start(plan))
    return service, clocks, leg, coordinator


def test_publication_failure_is_failed_not_completed(setup):
    service, clocks, _leg, coordinator = setup
    before = service.status().run
    old = coordinator.get_current_telemetry().model_dump()
    clocks.advance(120)

    def fail(telemetry, tick):
        raise RuntimeError("metrics failed")

    with pytest.raises(RuntimeError):
        service.collect(coordinator, fail)
    assert service.status().state == "failed"
    assert service.status().run.observed_at == before.observed_at
    assert service.status().run.processed_event_count == before.processed_event_count
    assert coordinator.get_current_telemetry().model_dump() == old


def test_later_collection_error_preserves_completed_result(setup, monkeypatch):
    service, clocks, _leg, coordinator = setup
    clocks.advance(120)
    service.collect(coordinator, lambda telemetry, tick: None)
    result = service.status().run

    def fail(*args, **kwargs):
        raise RuntimeError("network failed")

    monkeypatch.setattr(coordinator, "update", fail)
    with pytest.raises(RuntimeError):
        service.collect(coordinator, lambda telemetry, tick: None)
    assert service.status().state == "completed"
    assert service.status().run == result


def test_cancellation_ownership_and_edit_guards(setup):
    service, _clocks, leg, coordinator = setup
    service.cancel_owned("other", None, "Delete")
    service.assert_plan_edit_allowed("other", None)
    assert service.status().state == "running"
    with pytest.raises(HTTPException) as error:
        service.assert_plan_edit_allowed("mission-1", leg.id)
    assert error.value.status_code == 409
    service.cancel_owned("mission-1", leg.id, "Deactivated")
    service.assert_plan_edit_allowed("mission-1", leg.id)
    assert service.status().state == "cancelled"
    assert service.collect(coordinator, lambda telemetry, tick: None) is None


def test_changed_plan_and_live_rejected_before_mutation(setup):
    service, _clocks, leg, _coordinator = setup
    plan = service.runtime.selected_plan()
    request = SimulationStart(
        pacing=multiplier_input(10), plan_token=plan.preview.plan_token
    )
    service.route_manager.get_route(leg.route_id).points[-1].longitude = 3
    with pytest.raises(HTTPException) as error:
        service.prepare_start("mission-1", leg, request)
    assert error.value.status_code == 409
    assert service.status().run.plan_token == plan.preview.plan_token
    service.runtime.set_service_mode("live")
    with pytest.raises(HTTPException) as error:
        service.prepare_start("mission-1", leg, request)
    assert error.value.status_code == 409


def test_many_readers_share_one_producer(setup):
    service, clocks, _leg, coordinator = setup
    before = service.status().revision
    clocks.advance(1)
    for _ in range(50):
        service.status()
    service.collect(coordinator, lambda telemetry, tick: None)
    assert service.status().revision == before + 1
    for _ in range(50):
        service.status()
    assert service.status().revision == before + 1
    service.close()
    assert service.runtime.prepare_tick() is None


def test_collection_error_cannot_publish_retained_telemetry(setup, monkeypatch):
    service, clocks, _leg, coordinator = setup
    before = service.status().run

    def fail():
        raise RuntimeError("network generation failed")

    monkeypatch.setattr(coordinator.network_sim, "update", fail)
    clocks.advance(5)
    with pytest.raises(RuntimeError):
        service.collect(coordinator, lambda telemetry, tick: None)
    assert service.status().state == "failed"
    assert service.status().run.observed_at == before.observed_at
