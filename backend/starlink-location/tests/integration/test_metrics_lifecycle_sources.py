"""Explicit reload, source expiry, and lifecycle failure/recovery contracts."""

import json
from datetime import timedelta
from math import isnan
from types import SimpleNamespace

import pytest

import main
from app.core import eta_service
from app.core.metrics import frame_builder
from app.core.metrics import prometheus_metrics as metrics
from app.models.poi import POICreate
from app.models.route import RouteTimingProfile
from tests.integration.test_live_background_route import background_runtime

__all__ = ["background_runtime"]


def independent_samples():
    return tuple(
        (sample.name, tuple(sample.labels.items()), sample.value)
        for family in metrics.REGISTRY.collect()
        if family.type in ("counter", "histogram")
        for sample in family.samples
    )


@pytest.mark.parametrize("background_runtime", ["live", "simulation"], indirect=True)
async def test_dirty_refresh_preserves_all_observation_state(
    background_runtime, monkeypatch
):
    runtime = background_runtime
    monkeypatch.setattr(
        "app.simulation.coordinator.datetime",
        SimpleNamespace(now=lambda tz: runtime.clock[0]),
    )
    main._background_update_tick(main.app.state.poi_manager, 1, 0, 0)
    coordinator = main._coordinator
    observation = coordinator.get_current_telemetry().model_copy(deep=True)
    before = metrics.FRAME_STORE.read().frame
    history = eta_service.get_eta_calculator().get_stats()
    detection = runtime.flight_state.checkpoint()
    independent = independent_samples()
    replay = main.app.state.simulation_run_service.runtime
    run = replay.status().model_dump(exclude={"served_at"})

    def forbidden(*args, **kwargs):
        raise AssertionError("A derived refresh collected or advanced a source")

    monkeypatch.setattr(coordinator, "update", forbidden)
    monkeypatch.setattr(replay, "prepare_tick", forbidden)
    for i in range(5):
        main.app.state.poi_manager.create_poi(
            POICreate(name=f"Dirty {i}", latitude=1, longitude=1)
        )
    await main.app.state.metrics_refresh_owner.refresh_without_collection()
    head = metrics.FRAME_STORE.read()
    assert head.status == "ready"
    assert (
        head.frame.identity.observation_timestamp
        == before.identity.observation_timestamp
    )
    assert head.frame.identity.mode == coordinator.mode
    assert (
        head.frame.last_observation_publication_time
        == before.last_observation_publication_time
    )
    assert coordinator.get_current_telemetry() == observation
    assert eta_service.get_eta_calculator().get_stats() == history
    assert runtime.flight_state.checkpoint() == detection
    assert independent_samples() == independent
    assert replay.status().model_dump(exclude={"served_at"}) == run


@pytest.mark.parametrize("background_runtime", ["live"], indirect=True)
async def test_retained_source_expires_on_existing_deadline_without_reobserving(
    background_runtime, monkeypatch
):
    main._background_update_tick(main.app.state.poi_manager, 1, 0, 0)
    before = metrics.FRAME_STORE.read().frame
    telemetry = main._coordinator.get_current_telemetry()
    independent = independent_samples()
    background_runtime.clock[0] += timedelta(seconds=11)
    monkeypatch.setattr(main._coordinator, "update", lambda: telemetry)
    main._background_update_tick(main.app.state.poi_manager, 1, 1, 0)
    head = metrics.FRAME_STORE.read()
    assert head.status == "ready"
    assert head.frame.identity.observation_id is None
    assert isnan(
        metrics.REGISTRY.get_sample_value("starlink_network_latency_ms_current")
    )
    assert isnan(metrics.REGISTRY.get_sample_value("starlink_dish_latitude_degrees"))
    assert (
        head.frame.last_observation_publication_time
        == before.last_observation_publication_time
    )
    assert telemetry.timestamp.timestamp() == before.identity.observation_timestamp
    assert independent_samples() == independent


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_explicit_external_poi_reload_updates_frame_without_telemetry(
    background_runtime,
):
    manager = main.app.state.poi_manager
    owner = main.app.state.metrics_refresh_owner
    main._coordinator._last_valid_telemetry = None
    manager.create_poi(POICreate(name="Before", latitude=1, longitude=1))
    await owner.refresh_without_collection()
    data = json.loads(manager.pois_file.read_text())
    next(iter(data["pois"].values()))["name"] = "External"
    manager.pois_file.write_text(json.dumps(data))
    manager.reload_pois()
    assert metrics.FRAME_STORE.read().status == "pending"
    await owner.refresh_without_collection()
    names = {
        sample.labels.get("name")
        for family in metrics.REGISTRY.collect()
        if family.name == "starlink_eta_poi_seconds"
        for sample in family.samples
    }
    assert names == {"External"}
    assert metrics.FRAME_STORE.read().frame.identity.observation_id is None


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_timing_only_route_replacement_refreshes_phase_and_route(
    background_runtime,
):
    runtime = background_runtime
    runtime.route_manager.activate_route("first")
    await main.app.state.metrics_refresh_owner.refresh_without_collection()
    replacement = runtime.route.model_copy(deep=True)
    replacement.timing_profile = RouteTimingProfile(
        has_timing_data=True,
        departure_time=runtime.origin + timedelta(hours=1),
        arrival_time=runtime.origin + timedelta(hours=2),
        total_expected_duration_seconds=3600,
    )
    runtime.route_manager.add_route("first", replacement)
    await main.app.state.metrics_refresh_owner.refresh_without_collection()
    assert (
        metrics.REGISTRY.get_sample_value(
            "starlink_route_has_timing_data", {"route_name": "first"}
        )
        == 1
    )
    assert (
        metrics.REGISTRY.get_sample_value("starlink_time_until_departure_seconds")
        == 3600
    )
    assert (
        runtime.flight_state.get_status().scheduled_departure_time
        == runtime.origin + timedelta(hours=1)
    )


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_failed_active_route_parse_clears_planned_context_and_recovers(
    background_runtime,
):
    runtime = background_runtime
    route = runtime.route
    route.timing_profile = RouteTimingProfile(
        has_timing_data=True, departure_time=runtime.origin + timedelta(hours=1)
    )
    runtime.route_manager.activate_route("first")
    owner = main.app.state.metrics_refresh_owner
    await owner.refresh_without_collection()
    path = runtime.route_manager.routes_dir / "first.kml"
    path.write_text("invalid KML")
    runtime.route_manager._load_route_file(str(path))
    assert metrics.FRAME_STORE.read().status == "pending"
    await owner.refresh_without_collection()
    assert runtime.flight_state.get_status().active_route_id is None
    assert (
        metrics.REGISTRY.get_sample_value("starlink_time_until_departure_seconds") == 0
    )
    runtime.route_manager.add_route("first", route)
    await owner.refresh_without_collection()
    assert metrics.FRAME_STORE.read().status == "ready"
    assert runtime.flight_state.get_status().active_route_id == "first"


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_failed_refresh_recovers_on_next_lifecycle_event(
    background_runtime, monkeypatch
):
    owner = main.app.state.metrics_refresh_owner
    prepare = frame_builder.prepare_frame
    before = metrics.FRAME_STORE.read().frame

    def failed(*args, **kwargs):
        raise ValueError("injected calculation failure")

    monkeypatch.setattr(frame_builder, "prepare_frame", failed)
    owner.mark_dirty("test failure")
    await owner.refresh_without_collection()
    assert metrics.FRAME_STORE.read().status == "failed"
    assert metrics.FRAME_STORE.read().frame is before
    assert isnan(metrics.REGISTRY.get_sample_value("starlink_dish_latitude_degrees"))
    monkeypatch.setattr(frame_builder, "prepare_frame", prepare)
    owner.mark_dirty("test recovery")
    await owner.refresh_without_collection()
    assert metrics.FRAME_STORE.read().status == "ready"


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_active_profile_revalidation_failure_invalidates_once(background_runtime):
    from app.services.kml_parser import KMLParseError

    routes = background_runtime.route_manager
    routes.activate_route("first")
    owner = main.app.state.metrics_refresh_owner
    await owner.refresh_without_collection()

    def invalid_profile(_route_id):
        raise KMLParseError("Managed descriptor removed")

    routes._profile_resolver = invalid_profile
    assert routes.get_active_route() is None
    assert metrics.FRAME_STORE.read().status == "pending"
    revision = metrics.FRAME_STORE.read().input_revision
    assert routes.get_active_route() is None
    assert metrics.FRAME_STORE.read().input_revision == revision
    await owner.refresh_without_collection()
    assert background_runtime.flight_state.get_status().active_route_id is None


@pytest.mark.parametrize("background_runtime", ["live"], indirect=True)
async def test_same_timestamp_unadmitted_payload_cannot_be_used_for_refresh(
    background_runtime,
):
    main._background_update_tick(main.app.state.poi_manager, 1, 0, 0)
    before = metrics.FRAME_STORE.read().frame
    candidate = main._coordinator.get_current_telemetry().model_copy(deep=True)
    candidate.position.latitude = 42
    # Collection can replace the coordinator observation before the metrics
    # producer obtains admission. An equal timestamp is insufficient identity.
    main._coordinator._last_valid_telemetry = candidate
    owner = main.app.state.metrics_refresh_owner
    owner.mark_dirty("same timestamp source candidate")
    await owner.refresh_without_collection()
    assert isnan(metrics.REGISTRY.get_sample_value("starlink_dish_latitude_degrees"))
    assert (
        metrics.FRAME_STORE.read().frame.last_observation_publication_time
        == before.last_observation_publication_time
    )
