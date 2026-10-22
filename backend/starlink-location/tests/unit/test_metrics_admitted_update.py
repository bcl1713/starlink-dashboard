"""Guarded public APIs and caller-admitted producer contracts."""

from contextlib import nullcontext
from unittest.mock import Mock

import pytest

from app.core.metrics import frame_builder, source_admission
from app.core.metrics import metric_updater as updater
from app.core.metrics import prometheus_metrics as metrics
from app.mission import storage


def counts():
    return {
        instrument._name: sum(
            sample.value
            for family in instrument.collect()
            for sample in family.samples
            if sample.name.endswith(("_total", "_count"))
        )
        for instrument in (
            metrics.simulation_updates_total,
            metrics.starlink_network_latency_ms,
            metrics.starlink_network_throughput_down_mbps,
            metrics.starlink_network_throughput_up_mbps,
        )
    }


def test_public_prepare_acquires_gate_and_forwards_all_arguments(monkeypatch):
    gate = Mock(wraps=storage.get_active_leg_lock())
    gate.__enter__ = Mock(return_value=gate)
    gate.__exit__ = Mock(return_value=False)
    lookup = Mock(return_value=gate)
    monkeypatch.setattr(storage, "get_active_leg_lock", lookup)
    private = Mock(return_value=object())
    monkeypatch.setattr(
        updater, "_prepare_metrics_from_telemetry_admitted", private, raising=False
    )
    args = tuple(object() for _ in range(4))
    kwargs = {
        name: object()
        for name in (
            "flight_events_managed",
            "mission_context",
            "simulation_plan",
            "simulation_frame",
            "route_progress",
            "coordinator_id",
            "_captured_head",
        )
    }
    assert (
        updater.prepare_metrics_from_telemetry(*args, **kwargs) is private.return_value
    )
    private.assert_called_once_with(*args, **kwargs)
    lookup.assert_called_once_with()
    gate.__enter__.assert_called_once()
    gate.__exit__.assert_called_once()
    private.reset_mock()
    updater.prepare_metrics_from_telemetry(args[0])
    private.assert_called_once_with(
        args[0],
        None,
        None,
        None,
        flight_events_managed=False,
        mission_context=None,
        simulation_plan=None,
        simulation_frame=None,
        route_progress=None,
        coordinator_id=None,
        _captured_head=None,
    )
    private.side_effect = RuntimeError("private failure")
    with pytest.raises(RuntimeError, match="private failure"):
        updater.prepare_metrics_from_telemetry(args[0])
    assert gate.__exit__.call_count == 3


@pytest.mark.parametrize(
    "outcomes,prepares,publishes",
    [((False,), 0, 0), ((True, False), 1, 0), ((True, True), 1, 1)],
)
def test_public_update_keeps_entry_and_final_checks(
    monkeypatch, outcomes, prepares, publishes
):
    frame = metrics.FRAME_STORE.read().frame
    head = metrics.FRAME_STORE.invalidate("captured")

    def prepare(*args, **kwargs):
        kwargs["_captured_head"](head)
        return frame

    private = Mock(side_effect=prepare)
    monkeypatch.setattr(
        updater, "_prepare_metrics_from_telemetry_admitted", private, raising=False
    )
    source = Mock(side_effect=outcomes)
    current = Mock(return_value=True)
    monkeypatch.setattr(source_admission, "frame_inputs_are_current", current)
    publish = Mock()
    fail = Mock()
    monkeypatch.setattr(metrics.FRAME_STORE, "publish", publish)
    monkeypatch.setattr(metrics.FRAME_STORE, "fail", fail)
    updater.update_metrics_from_telemetry(object(), source_is_current=source)
    assert private.call_count == prepares
    assert source.call_count == len(outcomes)
    assert publish.call_count == publishes
    assert current.call_count == publishes
    if outcomes == (True, False):
        fail.assert_called_once_with(head, "telemetry source superseded")


def test_private_update_adds_no_admission(monkeypatch):
    helper = updater._update_metrics_from_telemetry_admitted
    frame = metrics.FRAME_STORE.read().frame
    order = []

    def prepare(*args, **kwargs):
        order.append("prepare")
        return frame

    monkeypatch.setattr(updater, "_prepare_metrics_from_telemetry_admitted", prepare)

    def final(value):
        assert value is frame
        order.append("final")
        return True

    original_publish = metrics.FRAME_STORE.publish

    def publish(*args):
        order.append("publish")
        return original_publish(*args)

    monkeypatch.setattr(metrics.FRAME_STORE, "publish", publish)
    original_validate = metrics.FRAME_STORE._validate

    def validate(*args, **kwargs):
        order.append("schema")
        return original_validate(*args, **kwargs)

    monkeypatch.setattr(metrics.FRAME_STORE, "_validate", validate)
    original_swap = metrics.FRAME_STORE._swap

    def swap(*args):
        order.append("cas")
        return original_swap(*args)

    monkeypatch.setattr(metrics.FRAME_STORE, "_swap", swap)
    with storage.get_active_leg_lock(), monkeypatch.context() as patch:
        lookup = Mock(side_effect=AssertionError("extra wrapper admission"))
        patch.setattr(storage, "get_active_leg_lock", lookup)
        helper(object(), final_validation=final)
        lookup.assert_not_called()
    assert order == ["prepare", "final", "publish", "schema", "cas"]


@pytest.mark.parametrize("failure", [False, True])
def test_private_update_targets_post_observation_head(monkeypatch, failure):
    helper = updater._update_metrics_from_telemetry_admitted
    captured = []

    def prepare(*args, **kwargs):
        head = metrics.FRAME_STORE.invalidate("observation reload")
        captured.append(head)
        kwargs["_captured_head"](head)
        if failure:
            raise RuntimeError("builder")
        return frame_builder.prepare_unavailable_frame(frame_builder.FrameInputs(head))

    monkeypatch.setattr(updater, "_prepare_metrics_from_telemetry_admitted", prepare)
    publish = Mock(wraps=metrics.FRAME_STORE.publish)
    fail = Mock(wraps=metrics.FRAME_STORE.fail)
    monkeypatch.setattr(metrics.FRAME_STORE, "publish", publish)
    monkeypatch.setattr(metrics.FRAME_STORE, "fail", fail)
    with storage.get_active_leg_lock():
        helper(object(), final_validation=lambda frame: True)
    if failure:
        fail.assert_called_once_with(captured[0], "telemetry preparation failed")
    else:
        assert publish.call_args.args[0] is captured[0]
        assert metrics.FRAME_STORE.read().status == "ready"


@pytest.mark.parametrize(
    "failure", ["builder", "final_false", "final_raises", "stale_cas"]
)
@pytest.mark.parametrize("mission", [False, True])
def test_private_update_failure_and_stale_cas_count_once(
    coordinator, monkeypatch, caplog, failure, mission
):
    helper = updater._update_metrics_from_telemetry_admitted
    telemetry = coordinator.get_current_telemetry()
    original = frame_builder.prepare_frame
    old = metrics.FRAME_STORE.read()
    newer = []
    observed = Mock(wraps=updater._observe_flight_status)
    monkeypatch.setattr(updater, "_observe_flight_status", observed)

    # Keep real ordinary observation while exercising mission error propagation.
    def observe(*args):
        return observed(*args[:3], None, *args[4:])

    monkeypatch.setattr(updater, "_observe_flight_status", observe)

    def prepare(*args, **kwargs):
        if failure == "builder":
            raise RuntimeError("builder")
        result = original(*args, **kwargs)
        if failure == "stale_cas":
            head = metrics.FRAME_STORE.read()
            assert metrics.FRAME_STORE.publish(head, head.frame)
            newer.append(metrics.FRAME_STORE.read())
        return result

    monkeypatch.setattr(frame_builder, "prepare_frame", prepare)

    def final(frame):
        if failure == "final_raises":
            raise RuntimeError("final")
        return failure != "final_false"

    from app.models.mission_time import MissionTimeContext

    context = (
        MissionTimeContext(
            runtime_id="test",
            run_id="test",
            revision=1,
            simulation_time=telemetry.timestamp,
            observed_at=telemetry.timestamp,
            phase="in_flight",
            effective_multiplier=1,
        )
        if mission
        else None
    )
    before = counts()
    raises = mission and failure in ("builder", "final_raises")
    with storage.get_active_leg_lock(), (
        pytest.raises(RuntimeError) if raises else nullcontext()
    ):
        helper(telemetry, mission_context=context, final_validation=final)
    after = counts()
    assert after.keys() == before.keys()
    for key in before:
        assert after[key] - before[key] == 1
    assert observed.call_count == 1
    errors = [
        record
        for record in caplog.records
        if record.message == "Complete metric frame preparation failed"
    ]
    assert len(errors) == int(not mission and failure in ("builder", "final_raises"))
    if newer:
        assert metrics.FRAME_STORE.read() is newer[0]
        assert newer[0].status == "ready"
    else:
        assert metrics.FRAME_STORE.read().frame is old.frame
        assert metrics.FRAME_STORE.read().status == "failed"


@pytest.mark.parametrize("private", [False, True])
def test_none_preparation_resets_detection_without_observation(monkeypatch, private):
    from app.services.flight_state import get_flight_state_manager

    reset = Mock()
    monkeypatch.setattr(get_flight_state_manager(), "reset_detection", reset)
    before = counts()
    prepare = (
        updater._prepare_metrics_from_telemetry_admitted
        if private
        else updater.prepare_metrics_from_telemetry
    )
    with storage.get_active_leg_lock():
        assert prepare(None) is None
    assert counts() == before
    reset.assert_called_once_with()
    final = Mock()
    publish = Mock()
    monkeypatch.setattr(metrics.FRAME_STORE, "publish", publish)
    with storage.get_active_leg_lock():
        updater._update_metrics_from_telemetry_admitted(None, final_validation=final)
    final.assert_not_called()
    publish.assert_not_called()
    assert counts() == before


def test_final_validation_cannot_be_omitted():
    helper = updater._update_metrics_from_telemetry_admitted
    before = counts()
    with storage.get_active_leg_lock(), pytest.raises(
        TypeError, match="final_validation"
    ):
        helper(object())
    assert counts() == before


def test_detached_frame_ownership_is_unchanged(coordinator, monkeypatch):
    from app.models.poi import POI
    from tests.unit.test_metrics_export import _make_parsed_route
    from tests.unit.test_metrics_frame_builder import values

    telemetry = coordinator.get_current_telemetry()
    config = coordinator.get_config()
    route = _make_parsed_route()
    poi = POI(id="detached", name="Before", latitude=1, longitude=1)
    manager = Mock()
    manager.list_pois.return_value = [poi]
    original = frame_builder.prepare_frame
    captured = []

    def prepare(inputs, **kwargs):
        originals = (
            inputs.telemetry.model_copy(deep=True),
            inputs.config.model_copy(deep=True),
            inputs.active_route.model_copy(deep=True),
            inputs.pois[0].model_copy(deep=True),
            inputs.flight_status.model_copy(deep=True),
        )
        telemetry.position.latitude = -60
        config.update_interval_seconds = 7
        route.metadata.name = "After"
        poi.name = "After"
        from app.models.flight_status import FlightPhase
        from app.services.flight_state import get_flight_state_manager

        get_flight_state_manager().transition_phase(FlightPhase.IN_FLIGHT)
        assert (
            inputs.telemetry,
            inputs.config,
            inputs.active_route,
            inputs.pois[0],
            inputs.flight_status,
        ) == originals
        frame = original(inputs, **kwargs)
        assert frame.identity.observation_id == source_admission.model_identity(
            originals[0]
        )
        assert frame.identity.route_id == source_admission.model_identity(originals[2])
        assert frame.identity.poi_id == source_admission.poi_identity((originals[3],))
        assert frame.identity.phase_id == source_admission.phase_identity(originals[4])
        captured.append(frame)
        return frame

    monkeypatch.setattr(frame_builder, "prepare_frame", prepare)
    frame = updater.prepare_metrics_from_telemetry(telemetry, config, route, manager)
    assert frame is captured[0]
    assert values(frame)["starlink_dish_latitude_degrees"][0][1] != -60
    assert values(frame)["starlink_eta_poi_seconds"][0][0][0] == "Before"
    assert not source_admission.frame_inputs_are_current(frame, route, manager)
