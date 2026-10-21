"""Task 2 producer preparation and the actual 29-family registration."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from math import isnan

import pytest
from prometheus_client import Counter, Gauge, Histogram

from app.core import eta_service
from app.core.metrics import prometheus_metrics as metrics
from app.core.metrics.frame_builder import (
    FrameInputs,
    prepare_frame,
    prepare_unavailable_frame,
)
from app.core.metrics.frames import FrameGaugeView
from app.models.flight_status import ETAMode, FlightPhase, FlightStatus
from app.models.poi import POI
from tests.unit.metrics_frame_support import actual_schema

NOW = datetime.now(UTC)


@pytest.fixture(autouse=True)
def current_test_clock():
    global NOW
    NOW = datetime.now(UTC)


def inputs(telemetry=None, **kwargs):
    return FrameInputs(
        expected=metrics.FRAME_STORE.read(), telemetry=telemetry, now=NOW, **kwargs
    )


def values(frame):
    return {
        definition.name: samples
        for definition, samples in zip(metrics.COUPLED_SCHEMA, frame.families)
    }


def test_actual_registry_has_one_coupled_collector_and_independent_types():
    assert metrics.COUPLED_SCHEMA == actual_schema()
    assert all(
        isinstance(getattr(metrics, d.name), FrameGaugeView) for d in actual_schema()
    )
    assert len(metrics.INDEPENDENT_GAUGES) == 18
    assert all(isinstance(g, Gauge) for g in metrics.INDEPENDENT_GAUGES)
    assert isinstance(metrics.simulation_updates_total, Counter)
    assert isinstance(metrics.starlink_network_latency_ms, Histogram)
    families = list(metrics.REGISTRY.collect())
    names = [f.name for f in families]
    assert all(names.count(d.name) == 1 for d in actual_schema())
    assert names.count("starlink_aircraft_position") == 1
    with pytest.raises(TypeError):
        metrics._current_position["latitude"] = 3


def test_complete_observation_and_derived_frame_preserve_source_and_accounting(
    coordinator,
):
    telemetry = coordinator.get_current_telemetry()
    original = telemetry.model_copy(deep=True)
    poi = POI(
        id="near",
        name="near",
        latitude=telemetry.position.latitude,
        longitude=telemetry.position.longitude,
    )
    before = deepcopy(eta_service.get_eta_calculator().get_stats())
    counters = {
        s.name: s.value
        for f in metrics.REGISTRY.collect()
        for s in f.samples
        if s.name.endswith(("_count", "_total"))
    }
    data = inputs(telemetry, pois=(poi,))
    frame = prepare_frame(data, admit_observation=False)
    assert metrics.FRAME_STORE.read() is data.expected
    assert eta_service.get_eta_calculator().get_stats() == before
    assert (
        eta_service.get_eta_calculator().get_stats()["passed_pois_count"]
        == before["passed_pois_count"]
    )
    assert counters == {
        s.name: s.value
        for f in metrics.REGISTRY.collect()
        for s in f.samples
        if s.name.endswith(("_count", "_total"))
    }
    assert telemetry == original
    assert frame.identity.observation_timestamp == telemetry.timestamp.timestamp()
    assert (
        frame.last_observation_publication_time
        == data.expected.frame.last_observation_publication_time
    )
    assert frame.identity.mode == "simulation"
    assert metrics.FRAME_STORE.publish(data.expected, frame)
    assert (
        metrics.REGISTRY.get_sample_value("starlink_dish_latitude_degrees")
        == telemetry.position.latitude
    )


def test_failed_preparation_and_source_change_expose_no_new_labels(
    coordinator, monkeypatch
):
    telemetry = coordinator.get_current_telemetry()
    data = inputs(telemetry, pois=(POI(id="x", name="new", latitude=1, longitude=1),))

    def fail(*args, **kwargs):
        raise RuntimeError("ETA failed")

    monkeypatch.setattr(eta_service, "derive_eta_metrics", fail)
    with pytest.raises(RuntimeError):
        prepare_frame(data, admit_observation=False)
    assert metrics.FRAME_STORE.read() is data.expected
    assert metrics.FRAME_STORE.fail(data.expected, "failed")
    assert (
        metrics.REGISTRY.get_sample_value(
            "starlink_eta_poi_seconds",
            {"name": "new", "category": "", "eta_type": "anticipated"},
        )
        is None
    )
    assert isnan(metrics.REGISTRY.get_sample_value("starlink_dish_latitude_degrees"))
    monkeypatch.undo()
    pending = metrics.FRAME_STORE.invalidate("source changed")
    candidate = prepare_frame(data, admit_observation=False)
    assert not metrics.FRAME_STORE.publish(data.expected, candidate)
    assert not metrics.FRAME_STORE.fail(data.expected, "obsolete failure")
    assert metrics.FRAME_STORE.read() is pending


@pytest.mark.parametrize("speed", [0, None])
def test_preflight_fallback_preserves_observed_speed_and_150_knots(coordinator, speed):
    telemetry = coordinator.get_current_telemetry().model_copy(deep=True)
    telemetry.position.speed = speed if speed is not None else 0
    telemetry.position.speed_observed_at = NOW if speed is not None else None
    poi = POI(
        id="east",
        name="East",
        latitude=telemetry.position.latitude + 0.1,
        longitude=telemetry.position.longitude,
    )
    data = inputs(telemetry, pois=(poi,))
    frame = prepare_frame(data, admit_observation=False)
    families = values(frame)
    distance = families["starlink_distance_to_poi_meters"][0][1]
    eta = families["starlink_eta_poi_seconds"][0][1]
    assert eta == pytest.approx(distance / 1852 / 150 * 3600)
    assert frame.identity.observation_timestamp == telemetry.timestamp.timestamp()
    assert telemetry.position.speed == 0


@pytest.mark.parametrize("stale", [False, True])
def test_inflight_missing_speed_is_not_an_estimate(coordinator, stale):
    telemetry = coordinator.get_current_telemetry().model_copy(deep=True)
    telemetry.metric_source = "observed"
    telemetry.position.observed_at = NOW
    telemetry.position.speed_observed_at = (
        NOW - timedelta(seconds=20) if stale else None
    )
    data = inputs(
        telemetry,
        pois=(POI(id="p", name="POI", latitude=1, longitude=1),),
        flight_status=FlightStatus(
            phase=FlightPhase.IN_FLIGHT, eta_mode=ETAMode.ESTIMATED
        ),
    )
    frame = prepare_frame(data, admit_observation=False)
    assert isnan(values(frame)["starlink_eta_poi_seconds"][0][1])
    assert frame.identity.mode == "live"


def test_unavailable_preserves_service_time_but_not_old_poi_distances(coordinator):
    data = inputs(coordinator.get_current_telemetry())
    assert metrics.FRAME_STORE.publish(
        data.expected, prepare_frame(data, admit_observation=True)
    )
    head = metrics.FRAME_STORE.read()
    data = inputs(pois=(POI(id="p", name="POI", latitude=1, longitude=1),))
    frame = prepare_unavailable_frame(data)
    assert (
        frame.last_observation_publication_time
        == head.frame.last_observation_publication_time
    )
    assert isnan(values(frame)["starlink_distance_to_poi_meters"][0][1])


@pytest.mark.parametrize("future", [False, True])
@pytest.mark.parametrize("usable_position", [False, True])
def test_timed_preflight_uses_plan_without_fabricated_position(
    coordinator, future, usable_position
):
    from app.models.route import RouteWaypoint
    from tests.unit.test_metrics_export import _make_parsed_route

    route = _make_parsed_route()
    departure = NOW + timedelta(hours=1) if future else NOW - timedelta(hours=3)
    route.timing_profile.departure_time = departure
    route.timing_profile.arrival_time = departure + timedelta(hours=2)
    route.waypoints = [
        RouteWaypoint(
            name="Destination",
            latitude=41,
            longitude=-72,
            order=0,
            expected_arrival_time=departure + timedelta(hours=2),
        )
    ]
    poi = POI(
        id="destination",
        name="Destination",
        latitude=41,
        longitude=-72,
        route_id=route.metadata.file_path,
    )
    telemetry = coordinator.get_current_telemetry().model_copy(deep=True)
    telemetry.position.observed_at = NOW if usable_position else None
    telemetry.position.speed = 0
    data = inputs(telemetry, active_route=route, pois=(poi,))
    frame = prepare_frame(data, admit_observation=False)
    numbers = values(frame)
    assert numbers["starlink_eta_poi_seconds"][0][0][-1] == "anticipated"
    assert numbers["starlink_eta_poi_seconds"][0][1] == pytest.approx(
        10800 if future else 7200, abs=1
    )
    assert numbers["starlink_route_total_duration_seconds"][0][1] == 7200
    assert numbers["starlink_route_segment_count_with_timing"][0][1] == 2
    if not usable_position:
        assert isnan(numbers["starlink_distance_to_poi_meters"][0][1])
        assert isnan(numbers["starlink_dish_latitude_degrees"][0][1])
        assert telemetry.position.observed_at is None


def test_untimed_unavailable_position_and_inflight_zero_remain_unavailable(coordinator):
    telemetry = coordinator.get_current_telemetry().model_copy(deep=True)
    telemetry.position.observed_at = None
    poi = POI(id="p", name="POI", latitude=1, longitude=1)
    frame = prepare_frame(inputs(telemetry, pois=(poi,)), admit_observation=False)
    assert isnan(values(frame)["starlink_eta_poi_seconds"][0][1])
    telemetry.position.observed_at = NOW
    telemetry.position.speed_observed_at = NOW
    telemetry.position.speed = 0
    frame = prepare_frame(
        inputs(
            telemetry,
            pois=(poi,),
            flight_status=FlightStatus(
                phase=FlightPhase.IN_FLIGHT, eta_mode=ETAMode.ESTIMATED
            ),
        ),
        admit_observation=False,
    )
    assert isnan(values(frame)["starlink_eta_poi_seconds"][0][1])
    assert values(frame)["starlink_dish_speed_knots"][0][1] == 0


def test_inputs_detach_route_pois_and_telemetry(coordinator):
    from tests.unit.test_metrics_export import _make_parsed_route

    route = _make_parsed_route()
    telemetry = coordinator.get_current_telemetry()
    poi = POI(id="p", name="Before", latitude=1, longitude=1)
    data = inputs(telemetry, active_route=route, pois=(poi,))
    before = data.telemetry.position.latitude
    telemetry.position.latitude = -60
    route.metadata.name = "After"
    poi.name = "After"
    frame = prepare_frame(data, admit_observation=False)
    assert values(frame)["starlink_dish_latitude_degrees"][0][1] == before
    assert values(frame)["starlink_eta_poi_seconds"][0][0][0] == "Before"
    assert values(frame)["starlink_route_has_timing_data"][0][0] == ("Unit Test Route",)


def test_invalidation_during_derived_preparation_cannot_mask_recovery(
    coordinator, monkeypatch
):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    original = eta_service.derive_eta_metrics
    entered, resume = threading.Event(), threading.Event()
    data = inputs(
        coordinator.get_current_telemetry(),
        pois=(POI(id="p", name="Obsolete", latitude=1, longitude=1),),
    )

    def paused(*args, **kwargs):
        entered.set()
        assert resume.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(eta_service, "derive_eta_metrics", paused)
    with ThreadPoolExecutor(1) as pool:
        worker = pool.submit(prepare_frame, data, False)
        try:
            assert entered.wait(5)
            pending = metrics.FRAME_STORE.invalidate("new source")
            recovered = prepare_unavailable_frame(FrameInputs(pending))
            assert metrics.FRAME_STORE.publish(pending, recovered)
            current = metrics.FRAME_STORE.read()
        finally:
            resume.set()
        obsolete = worker.result(5)
    assert not metrics.FRAME_STORE.publish(data.expected, obsolete)
    assert not metrics.FRAME_STORE.fail(data.expected, "obsolete exception")
    assert metrics.FRAME_STORE.read() is current
    assert (
        metrics.REGISTRY.get_sample_value(
            "starlink_eta_poi_seconds",
            {"name": "Obsolete", "category": "", "eta_type": "anticipated"},
        )
        is None
    )


def test_failure_after_staging_first_poi_publishes_no_labels(coordinator, monkeypatch):
    original = FrameGaugeView.set

    def fail_second(view, value):
        if (
            view.definition.name == "starlink_eta_poi_seconds"
            and view.labelvalues[0] == "Second"
        ):
            raise RuntimeError("second POI")
        return original(view, value)

    monkeypatch.setattr(FrameGaugeView, "set", fail_second)
    data = inputs(
        coordinator.get_current_telemetry(),
        pois=(
            POI(id="a", name="First", latitude=1, longitude=1),
            POI(id="b", name="Second", latitude=2, longitude=2),
        ),
    )
    with pytest.raises(RuntimeError):
        prepare_frame(data, admit_observation=False)
    assert metrics.FRAME_STORE.read() is data.expected
    assert (
        metrics.REGISTRY.get_sample_value(
            "starlink_eta_poi_seconds",
            {"name": "First", "category": "", "eta_type": "anticipated"},
        )
        is None
    )


def test_route_replacement_removes_only_coupled_labels(coordinator):
    from tests.unit.test_metrics_export import _make_parsed_route

    route = _make_parsed_route()
    metrics.mission_phase_state.labels(mission_id="kept").set(1)
    data = inputs(
        coordinator.get_current_telemetry(), active_route=route, progress=(25, 1)
    )
    assert metrics.FRAME_STORE.publish(data.expected, prepare_frame(data, False))
    assert (
        metrics.REGISTRY.get_sample_value(
            "starlink_route_progress_percent", {"route_name": route.metadata.name}
        )
        == 25
    )
    replacement = inputs(coordinator.get_current_telemetry())
    assert metrics.FRAME_STORE.publish(
        replacement.expected, prepare_frame(replacement, False)
    )
    assert (
        metrics.REGISTRY.get_sample_value(
            "starlink_route_progress_percent", {"route_name": route.metadata.name}
        )
        is None
    )
    assert (
        metrics.REGISTRY.get_sample_value("mission_phase_state", {"mission_id": "kept"})
        == 1
    )


@pytest.mark.parametrize("actual_departure", [False, True])
def test_naive_departure_retains_legacy_utc_countdown(coordinator, actual_departure):
    from tests.unit.test_metrics_export import _make_parsed_route

    route = _make_parsed_route()
    status = FlightStatus()
    naive = (NOW + timedelta(hours=1)).replace(tzinfo=None)
    if actual_departure:
        status.departure_time = naive
    else:
        route.timing_profile.departure_time = naive
    frame = prepare_frame(
        inputs(
            coordinator.get_current_telemetry(),
            active_route=route,
            flight_status=status,
        ),
        False,
    )
    assert values(frame)["starlink_time_until_departure_seconds"][0][1] == 3600
    assert naive.tzinfo is None


def test_failed_legacy_preparation_counts_admitted_sample_once(
    coordinator, monkeypatch
):
    from app.core.metrics import frame_builder, metric_updater

    telemetry = coordinator.get_current_telemetry()

    def total(name):
        return sum(
            s.value
            for f in metrics.REGISTRY.collect()
            for s in f.samples
            if s.name == name
        )

    before_updates = total("simulation_updates_total")
    before_hist = total("starlink_network_latency_ms_count")
    head = metrics.FRAME_STORE.read()

    def fail(*args, **kwargs):
        raise RuntimeError("failed complete frame")

    monkeypatch.setattr(frame_builder, "prepare_frame", fail)
    metric_updater.update_metrics_from_telemetry(telemetry)
    assert total("simulation_updates_total") == before_updates + 1
    assert total("starlink_network_latency_ms_count") == before_hist + 1
    state = metrics.FRAME_STORE.read()
    assert state.status == "failed"
    assert state.frame is head.frame
    assert isnan(metrics.REGISTRY.get_sample_value("starlink_dish_latitude_degrees"))
