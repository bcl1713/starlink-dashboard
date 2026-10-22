"""Operation-local reuse must preserve every authoritative publication boundary."""

import asyncio
import inspect
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Event, get_ident
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

import main
from app.core.metrics import frame_builder, source_admission
from app.core.metrics import metric_updater as updater
from app.core.metrics import prometheus_metrics as metrics
from app.mission import storage
from app.models.config import SimulationConfig
from app.models.flight_status import FlightPhase
from app.models.poi import POICreate
from app.models.route import RouteTimingProfile
from tests.integration.test_live_background_route import background_runtime
from tests.unit.test_metrics_admitted_update import counts

__all__ = ["background_runtime"]
MODES = pytest.mark.parametrize(
    "background_runtime", ["live", "simulation"], indirect=True
)
LIVE = pytest.mark.parametrize("background_runtime", ["live"], indirect=True)


@pytest.fixture(autouse=True)
async def manual_publication_owner(background_runtime, monkeypatch):
    # Keep real invalidation subscriptions; the test drives refresh explicitly.
    main.app.state.metrics_refresh_owner._background_enabled = True
    runtime = main.app.state.flight_event_runtime
    coordinator = main._coordinator
    yield
    if main._route_manager is not None:
        monkeypatch.setattr(main.app.state, "flight_event_runtime", runtime)
        monkeypatch.setattr(main, "_coordinator", coordinator)


def assert_observation_counts(before):
    after = counts()
    live = main._current_runtime_config().mode == "live"
    # Fixture live transport supplies no network samples; simulation supplies all.
    assert after["simulation_updates"] == before["simulation_updates"] + 1
    for name in (
        "starlink_network_latency_ms",
        "starlink_network_throughput_down_mbps",
        "starlink_network_throughput_up_mbps",
    ):
        assert after[name] == before[name] + (0 if live else 1), (name, before, after)


def publish_newer_head():
    current = metrics.FRAME_STORE.read()
    frame = replace(
        current.frame,
        identity=replace(current.frame.identity, input_revision=current.input_revision),
    )
    assert metrics.FRAME_STORE.publish(current, frame)
    return metrics.FRAME_STORE.read()


def tick():
    return main._background_update_tick(main.app.state.poi_manager, 1, 0, 0)


def observe(monkeypatch, owner, name, trace, label, predicate=lambda: True):
    original = getattr(owner, name)

    def wrapped(*args, **kwargs):
        if predicate():
            trace.append(label)
        return original(*args, **kwargs)

    monkeypatch.setattr(owner, name, wrapped)
    return original


def called_by_main():
    # Filter out coordinator, domain readers, detached frame hashes and startup.
    return inspect.currentframe().f_back.f_back.f_code.co_filename == main.__file__


def bind_mission(runtime):
    from app.mission.models import Mission, MissionLeg, TransportConfig

    runtime.route_manager.activate_route("first")
    mission = Mission(
        id="operation-mission",
        name="Before",
        legs=[
            MissionLeg(
                id="operation-leg",
                name="Active",
                route_id="first",
                is_active=True,
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            )
        ],
    )
    storage.save_mission_v2(mission)
    return mission


@MODES
async def test_new_tick_reuses_only_immediate_entry_validation(
    background_runtime, monkeypatch
):
    """Redundant reads/admissions fail counts; losing final/schema checks fails order."""
    background_runtime.route_manager.activate_route("first")
    monkeypatch.setattr(main.app.state, "flight_event_runtime", None)
    for index in range(2):
        main.app.state.poi_manager.create_poi(
            POICreate(name=f"POI {index}", latitude=1, longitude=1)
        )
    trace = []
    observe(
        monkeypatch,
        source_admission,
        "route_source_identity",
        trace,
        "source",
        called_by_main,
    )
    observe(
        monkeypatch,
        SimulationConfig,
        "model_dump_json",
        trace,
        "config",
        called_by_main,
    )
    observe(
        monkeypatch,
        background_runtime.route_manager,
        "get_active_route",
        trace,
        "route",
        called_by_main,
    )
    observe(
        monkeypatch, source_admission, "frame_inputs_are_current", trace, "final_inputs"
    )
    observe(
        monkeypatch,
        updater,
        "_prepare_metrics_from_telemetry_admitted",
        trace,
        "prepare",
    )
    observe(monkeypatch, metrics.FRAME_STORE, "_validate", trace, "schema")
    observe(monkeypatch, metrics.FRAME_STORE, "publish", trace, "publish")
    # Only the two wrapper admissions are forbidden, not domain-reader admission.
    lookup = storage.get_active_leg_lock
    direct = []

    def gate_lookup():
        caller = inspect.currentframe().f_back
        if caller.f_code.co_filename == updater.__file__:
            direct.append(caller.f_code.co_name)
        return lookup()

    monkeypatch.setattr(storage, "get_active_leg_lock", gate_lookup)
    before = counts()
    tick()
    assert (trace.count("source"), trace.count("config"), trace.count("route")) == (
        3,
        3,
        3,
    ), trace
    assert (
        trace.count("prepare")
        == trace.count("final_inputs")
        == trace.count("publish")
        == 1
    )
    assert trace.count("schema") == 2
    assert trace.index("prepare") < trace.index("final_inputs") < trace.index("publish")
    assert trace[-1] == "schema"
    assert direct == []
    assert_observation_counts(before)
    frame = metrics.FRAME_STORE.read().frame
    assert (
        frame.identity.observation_timestamp
        == main._coordinator.get_current_telemetry().timestamp.timestamp()
    )
    assert (
        frame.last_observation_publication_time == background_runtime.origin.timestamp()
    )


@LIVE
@pytest.mark.parametrize("record_failure", [False, True])
async def test_live_events_require_another_entry_check(
    background_runtime, monkeypatch, isolate_mission_storage, record_failure
):
    bind_mission(background_runtime)
    trace = []
    runtime = main.app.state.flight_event_runtime
    observe(
        monkeypatch,
        source_admission,
        "route_source_identity",
        trace,
        "check",
        called_by_main,
    )
    from app.mission import active_context

    observe(
        monkeypatch,
        active_context,
        "resolve_active_mission_leg_context",
        trace,
        "resolve",
    )
    for name in ("record_live", "observe_live", "sync_legacy_phase"):
        observe(monkeypatch, runtime, name, trace, name)
    if record_failure:

        def failed(*args):
            trace.append("record_live")
            raise OSError("disk full")

        monkeypatch.setattr(runtime, "record_live", failed)
    observe(
        monkeypatch,
        updater,
        "_update_metrics_from_telemetry_admitted",
        trace,
        "private",
    )
    before = counts()
    tick()
    events = (
        ["record_live"]
        if record_failure
        else ["record_live", "observe_live", "sync_legacy_phase"]
    )
    assert trace == ["check", "check", "resolve", *events, "check", "private", "check"]
    assert_observation_counts(before)


@LIVE
async def test_live_event_source_replacement_is_rejected_before_accounting(
    background_runtime, monkeypatch
):
    runtime = main.app.state.flight_event_runtime
    record = runtime.record_live
    changed_head = []

    def replace(*args):
        result = record(*args)
        coordinator = main._coordinator
        coordinator.update_config(
            coordinator.get_config().model_copy(update={"update_interval_seconds": 2})
        )
        changed_head.append(metrics.FRAME_STORE.read())
        return result

    monkeypatch.setattr(runtime, "record_live", replace)
    prepared = []
    observe(
        monkeypatch,
        updater,
        "_prepare_metrics_from_telemetry_admitted",
        prepared,
        "prepare",
    )
    before = counts()
    tick()
    assert prepared == []
    assert counts() == before
    assert metrics.FRAME_STORE.read() is changed_head[0]


@MODES
async def test_two_ticks_recapture_every_source(background_runtime, monkeypatch):
    monkeypatch.setattr(main.app.state, "flight_event_runtime", None)
    hashes, configs = [], []
    identity = source_admission.route_source_identity
    dump = SimulationConfig.model_dump_json

    def source(route):
        result = identity(route)
        if called_by_tick():
            hashes.append((route, result))
        return result

    def called_by_tick():
        return inspect.currentframe().f_back.f_back.f_code.co_filename == main.__file__

    def config_dump(config, *args, **kwargs):
        result = dump(config, *args, **kwargs)
        if called_by_tick():
            configs.append((config, result))
        return result

    monkeypatch.setattr(source_admission, "route_source_identity", source)
    monkeypatch.setattr(SimulationConfig, "model_dump_json", config_dump)
    background_runtime.route_manager.activate_route("first")
    tick()
    first_hashes, first_configs = hashes[:], configs[:]
    hashes.clear()
    configs.clear()
    with storage.get_active_leg_lock():
        new_config = main._coordinator.get_config().model_copy(
            update={"update_interval_seconds": 2}
        )
        main._coordinator.update_config(new_config)
        background_runtime.route_manager.activate_route("second")
    background_runtime.clock[0] += timedelta(seconds=1)
    tick()
    assert len(first_hashes) == len(first_configs) == len(hashes) == len(configs) == 3
    assert all(route is background_runtime.route for route, _ in first_hashes)
    assert all(route is background_runtime.other_route for route, _ in hashes)
    assert first_hashes[0][1] != hashes[0][1]
    assert all(config is new_config for config, _ in configs)
    assert first_configs[0][1] != configs[0][1]
    assert metrics.FRAME_STORE.read().status == "ready"


@MODES
@pytest.mark.parametrize(
    "change", ["empty", "actual_departure", "actual_arrival", "planned", "geometry"]
)
async def test_planned_route_identity_and_full_frame_identity_stay_distinct(
    background_runtime, monkeypatch, change
):
    monkeypatch.setattr(main.app.state, "flight_event_runtime", None)
    runtime = background_runtime
    runtime.route_manager.activate_route("first")
    route = runtime.route
    planned = source_admission.route_source_identity(route)
    full = source_admission.model_identity(route)
    before, old = counts(), metrics.FRAME_STORE.read()
    if change in ("empty", "actual_departure", "actual_arrival"):
        # Mutation must occur before FrameInputs detaches the full route.
        original = updater._prepare_metrics_from_telemetry_admitted

        def actuals(*args, **kwargs):
            mutate_before_build_value()
            return original(*args, **kwargs)

        def mutate_before_build_value():
            if change == "empty":
                route.timing_profile = RouteTimingProfile()
            elif change == "actual_departure":
                runtime.flight_state.trigger_departure(runtime.origin)
            else:
                runtime.flight_state.trigger_departure(runtime.origin)
                runtime.flight_state.trigger_arrival(
                    runtime.origin + timedelta(seconds=1)
                )

        monkeypatch.setattr(
            updater, "_prepare_metrics_from_telemetry_admitted", actuals
        )
    else:
        collect = main._coordinator.update

        def changed_collection():
            telemetry = collect()
            if change == "planned":
                route.timing_profile = RouteTimingProfile(
                    departure_time=runtime.origin + timedelta(hours=1)
                )
            else:
                route.points[0].latitude += 1
            return telemetry

        monkeypatch.setattr(main._coordinator, "update", changed_collection)
    tick()
    if change in ("empty", "actual_departure", "actual_arrival"):
        assert source_admission.route_source_identity(route) == planned
        assert source_admission.model_identity(route) != full
        assert metrics.FRAME_STORE.read().status == "ready"
        assert (
            metrics.FRAME_STORE.read().frame.identity.route_id
            == source_admission.model_identity(route)
        )
        assert_observation_counts(before)
    else:
        assert counts() == before
        assert metrics.FRAME_STORE.read().frame is old.frame


@LIVE
@pytest.mark.parametrize(
    "adapter_config", [Mock(), None, SimpleNamespace(mode="simulation")]
)
async def test_legacy_adapter_keeps_reference_only_source_checks(
    background_runtime, monkeypatch, adapter_config
):
    with monkeypatch.context() as patch:
        telemetry, config = Mock(), SimpleNamespace(mode="live")
        coordinator = Mock(update=lambda: telemetry)
        coordinator.get_config.return_value = adapter_config
        routes = Mock()
        patch.setattr(main, "_coordinator", coordinator)
        patch.setattr(main, "_route_manager", routes)
        patch.setattr(main, "_simulation_config", config)
        patch.setattr(main.app.state, "simulation_run_service", None)
        patch.setattr(main.app.state, "flight_event_runtime", None)

        def forbidden(*args):
            raise AssertionError("legacy source used domain serialization")

        patch.setattr(source_admission, "route_source_identity", forbidden)
        patch.setattr(source_admission, "model_identity", forbidden)
        frame = metrics.FRAME_STORE.read().frame
        validations = []

        def inputs(staged, route, pois):
            assert staged is frame
            validations.append(route)
            return True

        patch.setattr(source_admission, "frame_inputs_are_current", inputs)
        prepared = Mock(return_value=frame)
        patch.setattr(updater, "_prepare_metrics_from_telemetry_admitted", prepared)
        tick()
        prepared.assert_called_once()
        assert len(validations) == 1
        assert routes.get_active_route.call_count == 1


def mutate(runtime, change, monkeypatch):
    coordinator = main._coordinator
    routes = runtime.route_manager
    if change in ("config", "config_replace"):
        coordinator.update_config(
            coordinator.get_config().model_copy(update={"update_interval_seconds": 2})
        )
    elif change == "config_inplace":
        coordinator.get_config().update_interval_seconds = 2
    elif change == "coordinator":
        from app.simulation.coordinator import SimulationCoordinator

        monkeypatch.setattr(
            main, "_coordinator", SimulationCoordinator(coordinator.get_config())
        )
    elif change == "reset":
        coordinator.reset()
    elif change in ("route_activate", "route"):
        routes.activate_route("second")
    elif change == "route_remove":
        routes._remove_route("first")
    elif change == "route_replace":
        routes.add_route("first", runtime.route.model_copy(deep=True))
    elif change == "route_inplace":
        runtime.route.points[0].latitude += 1
    elif change == "route_planned_timing":
        runtime.route.timing_profile = RouteTimingProfile(
            departure_time=runtime.origin + timedelta(hours=1)
        )
    elif change == "poi":
        main.app.state.poi_manager.create_poi(
            POICreate(name="Changed", latitude=0, longitude=1)
        )
    elif change == "phase":
        runtime.flight_state.transition_phase(FlightPhase.IN_FLIGHT)
    elif change == "telemetry_replace":
        coordinator.update()
    elif change in ("service_revision", "mission"):
        main.app.state.simulation_run_service.runtime.clear_selection()
    else:
        raise AssertionError(change)


@MODES
@pytest.mark.parametrize(
    "change",
    [
        "config",
        "coordinator",
        "reset",
        "route_activate",
        "route_remove",
        "route_planned_timing",
        "service_revision",
    ],
)
@pytest.mark.parametrize("newer", [False, True])
async def test_collection_race_rejects_before_acceptance(
    background_runtime, monkeypatch, change, newer
):
    runtime = background_runtime
    runtime.route_manager.activate_route("first")
    coordinator = main._coordinator
    entered, release = Event(), Event()
    collect = coordinator.update
    old, before = metrics.FRAME_STORE.read(), counts()
    prepared = []
    observe(
        monkeypatch,
        updater,
        "_prepare_metrics_from_telemetry_admitted",
        prepared,
        "prepare",
    )

    def paused():
        telemetry = collect()
        entered.set()
        assert release.wait(5)
        return telemetry

    monkeypatch.setattr(coordinator, "update", paused)
    newer_head = None
    with ThreadPoolExecutor(max_workers=1) as pool:
        producer = pool.submit(tick)
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            with storage.get_active_leg_lock():
                mutate(runtime, change, monkeypatch)
                if newer:
                    newer_head = publish_newer_head()
        finally:
            release.set()
            try:
                producer.result(timeout=5)
            finally:
                monkeypatch.setattr(main, "_coordinator", coordinator)
    assert prepared == []
    assert counts() == before
    if not newer:
        assert metrics.FRAME_STORE.read().frame is old.frame
    if newer:
        assert metrics.FRAME_STORE.read() is newer_head
        assert newer_head.status == "ready"
    else:
        assert metrics.FRAME_STORE.read().status in ("failed", "pending")


@MODES
@pytest.mark.parametrize("change", ["config", "route", "poi", "phase", "mission"])
async def test_writer_waits_through_final_check_and_publication(
    background_runtime, monkeypatch, change
):
    runtime = background_runtime
    runtime.route_manager.activate_route("first")
    entered, release, started, attempting, finished = [Event() for _ in range(5)]
    order = []
    prepare = frame_builder.prepare_frame
    gate = storage.get_active_leg_lock()
    acquire = gate.acquire
    writer_thread = []
    old = metrics.FRAME_STORE.read()
    before = counts()

    def paused(*args, **kwargs):
        frame = prepare(*args, **kwargs)
        entered.set()
        assert release.wait(5)
        return frame

    def acquiring(*args, **kwargs):
        is_writer = writer_thread and get_ident() == writer_thread[0]
        if is_writer:
            attempting.set()
        result = acquire(*args, **kwargs)
        if is_writer:
            order.append("writer acquired")
        return result

    publish = metrics.FRAME_STORE.publish

    def publishing(*args):
        result = publish(*args)
        assert result
        order.append("producer publish")
        return result

    def writer():
        writer_thread.append(get_ident())
        started.set()
        try:
            with gate:
                mutate(runtime, change, monkeypatch)
        finally:
            finished.set()

    monkeypatch.setattr(frame_builder, "prepare_frame", paused)
    monkeypatch.setattr(gate, "acquire", acquiring)
    monkeypatch.setattr(metrics.FRAME_STORE, "publish", publishing)
    with ThreadPoolExecutor(max_workers=2) as pool:
        producer = pool.submit(tick)
        writing = None
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            writing = pool.submit(writer)
            assert await asyncio.to_thread(started.wait, 3)
            assert await asyncio.to_thread(attempting.wait, 3)
            assert not finished.is_set()
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=main.app), base_url="http://test"
            ) as client:
                responses = await asyncio.wait_for(
                    asyncio.gather(*(client.get("/metrics") for _ in range(20))), 3
                )
            assert all(
                response.status_code == 200 and response.text.endswith("# EOF\n")
                for response in responses
            )
            assert metrics.FRAME_STORE.read() is old
        finally:
            release.set()
            producer.result(timeout=5)
            if writing is not None:
                writing.result(timeout=5)
    assert finished.is_set()
    assert order.index("producer publish") < order.index("writer acquired")
    assert order.count("producer publish") == 1
    assert_observation_counts(before)


@MODES
@pytest.mark.parametrize(
    "change",
    [
        "config_replace",
        "config_inplace",
        "route_replace",
        "route_inplace",
        "poi",
        "phase",
        "telemetry_replace",
        "reset",
        "service_revision",
    ],
)
@pytest.mark.parametrize("newer", [False, True])
async def test_reentrant_preparation_change_rejected(
    background_runtime, monkeypatch, change, newer
):
    runtime = background_runtime
    runtime.route_manager.activate_route("first")
    monkeypatch.setattr(main.app.state, "flight_event_runtime", None)
    prepare = frame_builder.prepare_frame
    old, before = metrics.FRAME_STORE.read(), counts()
    newer_head = []
    staged = []

    def changed(*args, **kwargs):
        frame = prepare(*args, **kwargs)
        staged.append(frame)
        mutate(runtime, change, monkeypatch)
        if newer:
            newer_head.append(publish_newer_head())
        return frame

    monkeypatch.setattr(frame_builder, "prepare_frame", changed)
    tick()
    assert len(staged) == 1
    if not newer:
        assert metrics.FRAME_STORE.read().frame is old.frame
    assert_observation_counts(before)
    if newer:
        assert metrics.FRAME_STORE.read() is newer_head[0]
        assert newer_head[0].status == "ready"
    else:
        assert metrics.FRAME_STORE.read().status in ("failed", "pending")


@LIVE
@pytest.mark.parametrize("change", ["edit", "delete", "read_failure"])
async def test_known_live_mission_is_reloaded_before_publish(
    background_runtime, monkeypatch, isolate_mission_storage, change
):
    mission = bind_mission(background_runtime)
    old, before = metrics.FRAME_STORE.read(), counts()
    prepare = frame_builder.prepare_frame
    loads = []
    load = storage.load_mission_v2

    def loading(known_id):
        loads.append(known_id)
        if change == "read_failure":
            raise OSError("mission read failed")
        return load(known_id)

    def changed(*args, **kwargs):
        frame = prepare(*args, **kwargs)
        if change == "edit":
            mission.name = "Changed"
            storage.save_mission_v2(mission)
        elif change == "delete":
            (storage.MISSIONS_DIR / mission.id / "mission.json").unlink()
        monkeypatch.setattr(storage, "load_mission_v2", loading)
        return frame

    monkeypatch.setattr(frame_builder, "prepare_frame", changed)
    tick()
    assert loads and set(loads) == {mission.id}
    assert metrics.FRAME_STORE.read().frame is old.frame
    assert metrics.FRAME_STORE.read().status in ("failed", "pending")
    assert_observation_counts(before)


@MODES
@pytest.mark.parametrize("change", ["planned_edit", "invalid_profile"])
async def test_external_route_reload_invalidates_prepared_head(
    background_runtime, monkeypatch, tmp_path, change
):
    """Real SourceStore validation must invalidate an externally changed owned route."""
    from hashlib import sha256

    from app.mission.planning.sources import SourceStore

    runtime = background_runtime
    routes = runtime.route_manager
    sources = SourceStore(tmp_path / "missions", routes.routes_dir)
    route_id = "first"
    path = routes.routes_dir / "first.kml"
    data = b'<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><LineString><coordinates>0,0,0 1,1,0</coordinates></LineString></Placemark></Document></kml>'
    path.write_bytes(data)
    digest = sha256(data).hexdigest()
    inventory = sources.root / "inventory" / "first.json"
    inventory.parent.mkdir(parents=True, exist_ok=True)
    inventory.write_text(
        json.dumps({"id": route_id, "owner": "operation", "content_hash": digest})
    )
    descriptor = sources.descriptor_path(route_id)
    valid = json.dumps(
        {
            "version": 1,
            "route_id": route_id,
            "owner": "operation",
            "source_hash": digest,
            "ingestion_profile": "planning_v1",
        }
    )
    descriptor.write_text(valid)
    routes._profile_resolver = sources.resolve_profile
    routes.activate_route("first")
    old, before = metrics.FRAME_STORE.read(), counts()
    prepare = frame_builder.prepare_frame
    invalidated = []

    def changed(*args, **kwargs):
        frame = prepare(*args, **kwargs)
        target = path if change == "planned_edit" else descriptor
        replacement = target.with_suffix(".task2-new")
        replacement.write_bytes(
            data.replace(b"1,1,0", b"2,2,0") if change == "planned_edit" else b"{}"
        )
        replacement.replace(target)
        # No local notification: final get_active_route must discover this edit.
        assert metrics.FRAME_STORE.read().status != "failed"
        return frame

    original_get = routes.get_active_route

    def read():
        result = original_get()
        if result is None:
            invalidated.append(metrics.FRAME_STORE.read())
        return result

    monkeypatch.setattr(routes, "get_active_route", read)
    monkeypatch.setattr(frame_builder, "prepare_frame", changed)
    tick()
    assert invalidated
    assert metrics.FRAME_STORE.read() is invalidated[-1]
    assert metrics.FRAME_STORE.read().frame is old.frame
    assert metrics.FRAME_STORE.read().status == "pending"
    assert_observation_counts(before)
    monkeypatch.setattr(frame_builder, "prepare_frame", prepare)
    path.write_bytes(data)
    descriptor.write_text(valid)
    routes.add_route("first", runtime.route)
    main._refresh_metrics_without_collection()
    assert metrics.FRAME_STORE.read().status == "ready"


@MODES
@pytest.mark.parametrize("change", ["edit", "invalid", "lock_failure"])
async def test_external_poi_reload_is_not_bypassed(
    background_runtime, monkeypatch, change
):
    import app.services.poi.manager as poi_module

    manager = main.app.state.poi_manager
    manager.create_poi(POICreate(name="Original", latitude=1, longitude=1))
    data = json.loads(manager.pois_file.read_text())
    next(iter(data["pois"].values()))["name"] = "Recovered"
    old, before = metrics.FRAME_STORE.read(), counts()
    prepare = frame_builder.prepare_frame
    file_lock = poi_module.FileLock

    class BusyLock:
        def __init__(self, *args, **kwargs):
            pass

        def acquire(self, *args, **kwargs):
            raise TimeoutError("injected POI lock failure")

    def changed(*args, **kwargs):
        frame = prepare(*args, **kwargs)
        replacement = manager.pois_file.with_suffix(".task2-new")
        replacement.write_text("[]" if change == "invalid" else json.dumps(data))
        replacement.replace(manager.pois_file)
        if change == "lock_failure":
            monkeypatch.setattr(poi_module, "FileLock", BusyLock)
        return frame

    monkeypatch.setattr(frame_builder, "prepare_frame", changed)
    tick()
    assert metrics.FRAME_STORE.read().frame is old.frame
    assert metrics.FRAME_STORE.read().status in ("failed", "pending")
    assert_observation_counts(before)
    monkeypatch.setattr(frame_builder, "prepare_frame", prepare)
    monkeypatch.setattr(poi_module, "FileLock", file_lock)
    manager.pois_file.write_text(json.dumps(data))
    main._refresh_metrics_without_collection()
    assert metrics.FRAME_STORE.read().status == "ready"
    assert {
        sample.labels.get("name")
        for family in metrics.REGISTRY.collect()
        if family.name == "starlink_eta_poi_seconds"
        for sample in family.samples
    } == {"Recovered"}


@MODES
async def test_final_validation_uses_new_route_read(background_runtime, monkeypatch):
    runtime = background_runtime
    runtime.route_manager.activate_route("first")
    old, before = metrics.FRAME_STORE.read(), counts()
    prepare = frame_builder.prepare_frame
    final = []
    original = runtime.route_manager.get_active_route

    def changed(*args, **kwargs):
        frame = prepare(*args, **kwargs)

        def read():
            final.append(True)
            return runtime.other_route

        monkeypatch.setattr(runtime.route_manager, "get_active_route", read)
        return frame

    monkeypatch.setattr(frame_builder, "prepare_frame", changed)
    tick()
    monkeypatch.setattr(runtime.route_manager, "get_active_route", original)
    assert final
    assert metrics.FRAME_STORE.read().frame is old.frame
    assert metrics.FRAME_STORE.read().status in ("failed", "pending")
    assert_observation_counts(before)


@MODES
async def test_cancelled_loop_drains_admitted_tick_before_shutdown(
    background_runtime, monkeypatch
):
    entered, release, worker_done = Event(), Event(), Event()
    cancelling = asyncio.Event()
    closed = []
    prepare = frame_builder.prepare_frame
    routes = background_runtime.route_manager
    stop = routes.stop_watching

    def stopping():
        closed.append(True)
        return stop()

    monkeypatch.setattr(routes, "stop_watching", stopping)

    def paused(*args, **kwargs):
        frame = prepare(*args, **kwargs)
        entered.set()
        assert release.wait(5)
        return frame

    monkeypatch.setattr(frame_builder, "prepare_frame", paused)
    original_tick = main._background_update_tick

    def owned(*args):
        try:
            return original_tick(*args)
        finally:
            worker_done.set()

    monkeypatch.setattr(main, "_background_update_tick", owned)
    loop_task = asyncio.create_task(
        main._background_update_loop(main.app.state.poi_manager)
    )
    monkeypatch.setattr(main, "_background_task", loop_task)
    cancel = loop_task.cancel

    def cancelling_worker(*args, **kwargs):
        cancelling.set()
        return cancel(*args, **kwargs)

    monkeypatch.setattr(loop_task, "cancel", cancelling_worker)
    shutdown = None
    staged_old = metrics.FRAME_STORE.read().frame
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        shutdown = asyncio.create_task(main.shutdown_event())
        await asyncio.wait_for(cancelling.wait(), 3)
        shutdown.cancel()
        await asyncio.sleep(0)
        shutdown.cancel()
        await asyncio.sleep(0)
        assert not closed and not worker_done.is_set()
        metrics.FRAME_STORE.invalidate("obsolete completion during shutdown")
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await shutdown
        assert worker_done.is_set()
        assert metrics.FRAME_STORE.read().frame is staged_old
        assert main._background_task is None and main._route_manager is None
        assert not hasattr(main.app.state, "metrics_refresh_owner")
        gate = storage.get_active_leg_lock()
        with gate.acquire(timeout=1):
            pass
        assert gate._owner is None
    finally:
        release.set()
        if shutdown is not None:
            await asyncio.gather(shutdown, return_exceptions=True)
        cancel()
        await asyncio.gather(loop_task, return_exceptions=True)
        # Preserve fixture ownership of the live coordinator until its teardown.
        await main.shutdown_event()
