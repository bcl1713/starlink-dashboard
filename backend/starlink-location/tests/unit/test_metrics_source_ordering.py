"""Replay visibility and producer source admission, using the real registry."""

from concurrent.futures import ThreadPoolExecutor
from math import isnan
from threading import Event

import pytest
from prometheus_client import generate_latest

from app.core.metrics import metric_updater as updater
from app.core.metrics import prometheus_metrics as metrics
from tests.unit.test_simulation_run_timing import arrival_poi, timing

__all__ = ["timing"]


@pytest.mark.parametrize("failure", [None, "before", "during"])
def test_replay_frame_is_private_until_runtime_commit(timing, monkeypatch, failure):
    service, clocks, coordinator, prepare = timing
    poi = arrival_poi(service)
    previous = metrics.FRAME_STORE.read()
    commit = service.runtime.commit_tick
    clocks.advance(12)
    prepared = []

    def callback(telemetry, tick):
        result = prepare(telemetry, tick)
        prepared.append(result)
        assert metrics.FRAME_STORE.read() is previous
        if failure == "before":
            raise RuntimeError("before commit")
        return result

    def guarded_commit(tick):
        # Real serialization must remain possible while a frame is staged.
        assert generate_latest(metrics.REGISTRY)
        assert metrics.FRAME_STORE.read() is previous
        if failure == "during":
            raise RuntimeError("during commit")
        return commit(tick)

    monkeypatch.setattr(service.runtime, "commit_tick", guarded_commit)
    if failure:
        with pytest.raises(RuntimeError, match=failure):
            service.collect(coordinator, callback)
        assert isnan(
            metrics.REGISTRY.get_sample_value("starlink_dish_longitude_degrees")
        )
        assert service.status().state == "failed"
        assert metrics.FRAME_STORE.read().frame is not prepared[0]
    else:
        telemetry = service.collect(coordinator, callback)
        frame = metrics.FRAME_STORE.read().frame
        assert frame is prepared[0]
        assert frame.identity.replay_revision == str(service.status().revision)
        assert (
            frame.identity.replay_mission_time
            == service.runtime.frame().simulation_time.timestamp()
        )
        assert frame.identity.observation_timestamp == telemetry.timestamp.timestamp()
        assert (
            metrics.REGISTRY.get_sample_value(
                "starlink_route_progress_percent", {"route_name": "Replay"}
            )
            == 20
        )
        assert (
            metrics.REGISTRY.get_sample_value("starlink_dish_longitude_degrees")
            == telemetry.position.longitude
        )
        assert metrics.REGISTRY.get_sample_value("starlink_flight_phase") == 1
        assert (
            metrics.REGISTRY.get_sample_value(
                "starlink_mode_info", {"mode": "simulation"}
            )
            == 1
        )
        assert (
            metrics.REGISTRY.get_sample_value(
                "starlink_route_has_timing_data", {"route_name": "Replay"}
            )
            == 1
        )
        assert (
            metrics.REGISTRY.get_sample_value(
                "starlink_eta_poi_seconds",
                {"name": poi.name, "category": "", "eta_type": "estimated"},
            )
            == 1080
        )
        assert frame.last_observation_publication_time == clocks.utc.timestamp()
        assert telemetry.position.observed_at == clocks.utc
        assert telemetry.position.speed_observed_at == clocks.utc


def test_concurrent_scrapes_cannot_see_precommit_frame(timing, monkeypatch):
    service, clocks, coordinator, prepare = timing
    entered, release = Event(), Event()
    previous = metrics.FRAME_STORE.read()
    commit = service.runtime.commit_tick

    def paused_commit(tick):
        entered.set()
        assert release.wait(5)
        return commit(tick)

    monkeypatch.setattr(service.runtime, "commit_tick", paused_commit)
    clocks.advance(12)
    with ThreadPoolExecutor(max_workers=2) as pool:
        producer = pool.submit(service.collect, coordinator, prepare)
        try:
            assert entered.wait(3)
            for _ in range(20):
                assert generate_latest(metrics.REGISTRY)
                assert metrics.FRAME_STORE.read() is previous
        finally:
            release.set()
        producer.result(timeout=5)
    assert metrics.FRAME_STORE.read() is not previous


def test_config_replaced_during_preparation_rejects_frame(coordinator, monkeypatch):
    from app.core.metrics import frame_builder

    config = coordinator.get_config()
    telemetry = coordinator.get_current_telemetry()
    original = frame_builder.prepare_frame
    before = metrics.REGISTRY.get_sample_value("simulation_updates_total")

    def change_source(*args, **kwargs):
        frame = original(*args, **kwargs)
        coordinator.update_config(
            config.model_copy(update={"update_interval_seconds": 2})
        )
        return frame

    monkeypatch.setattr(frame_builder, "prepare_frame", change_source)
    updater.update_metrics_from_telemetry(
        telemetry,
        config,
        source_is_current=lambda: coordinator.get_config() is config,
    )
    assert metrics.FRAME_STORE.read().status != "ready"
    assert isnan(metrics.REGISTRY.get_sample_value("starlink_dish_latitude_degrees"))
    assert metrics.REGISTRY.get_sample_value("simulation_updates_total") == before + 1


def test_route_progress_snapshot_does_not_advance_source(coordinator):
    from unittest.mock import Mock

    coordinator.position_sim.route_follower = Mock()
    coordinator.position_sim.route_follower.get_point_count.return_value = 3
    coordinator.position_sim.progress = 0.25
    observation = coordinator.get_current_telemetry().model_copy(deep=True)
    assert coordinator.route_progress_snapshot() == (25, 0)
    assert coordinator.get_current_telemetry() == observation
    assert coordinator.position_sim.progress == 0.25


@pytest.mark.parametrize("failure", ["builder", "cas", "commit"])
def test_accepted_replay_counts_once_even_when_frame_cannot_publish(
    timing, monkeypatch, failure
):
    from app.core.metrics import frame_builder

    service, clocks, coordinator, prepare = timing
    clocks.advance(1)
    before_updates = metrics.REGISTRY.get_sample_value("simulation_updates_total")

    # Sum actual public observations rather than assume a status label spelling.
    def observations():
        return sum(
            s.value
            for f in metrics.starlink_network_latency_ms.collect()
            for s in f.samples
            if s.name.endswith("_count")
        )

    before_hist = observations()
    original = frame_builder.prepare_frame

    def failed_builder(*args, **kwargs):
        raise RuntimeError("optional ETA failure")

    def lost_cas(*args, **kwargs):
        frame = original(*args, **kwargs)
        current = metrics.FRAME_STORE.read()
        assert metrics.FRAME_STORE.publish(current, current.frame)
        return frame

    if failure == "builder":
        monkeypatch.setattr(frame_builder, "prepare_frame", failed_builder)
    elif failure == "cas":
        monkeypatch.setattr(frame_builder, "prepare_frame", lost_cas)
    else:
        monkeypatch.setattr(service.runtime, "commit_tick", failed_builder)
    if failure == "cas":
        service.collect(coordinator, prepare)
    else:
        with pytest.raises(RuntimeError):
            service.collect(coordinator, prepare)
    assert (
        metrics.REGISTRY.get_sample_value("simulation_updates_total")
        == before_updates + 1
    )
    # Replay network measurements are explicitly unavailable, never observed.
    assert observations() == before_hist


def test_cancelled_prepared_replay_cannot_publish(timing):
    service, clocks, coordinator, prepare = timing
    clocks.advance(1)
    old = coordinator.get_current_telemetry().model_copy(deep=True)
    staged = []

    def cancel(telemetry, tick):
        staged.append(prepare(telemetry, tick))
        service.cancel_owned(tick.plan.mission_id, None, "Test cancellation")
        return staged[0]

    with pytest.raises(ValueError, match="superseded"):
        service.collect(coordinator, cancel)
    assert service.status().state == "cancelled"
    assert coordinator.get_current_telemetry() == old
    assert metrics.FRAME_STORE.read().frame is not staged[0]
    assert isnan(metrics.REGISTRY.get_sample_value("starlink_dish_longitude_degrees"))


def test_replay_cancellation_invalidates_only_owned_source(timing):
    service, _clocks, coordinator, prepare = timing
    service.collect(coordinator, prepare)
    committed = metrics.FRAME_STORE.read()
    service.cancel_owned("other", None, "Unrelated")
    assert metrics.FRAME_STORE.read() is committed
    service.cancel_owned("mission-1", None, "Stopped")
    assert metrics.FRAME_STORE.read().status == "pending"
    assert isnan(metrics.REGISTRY.get_sample_value("starlink_dish_longitude_degrees"))
    assert metrics.FRAME_STORE.read().frame is committed.frame


def test_old_replay_cancellation_cannot_mask_newer_source(timing):
    from dataclasses import replace

    from app.core.metrics.frames import GaugeFrame

    service, _clocks, coordinator, prepare = timing
    service.collect(coordinator, prepare)
    state = metrics.FRAME_STORE.read()
    newer = GaugeFrame(
        replace(
            state.frame.identity,
            mode="live",
            replay_runtime_id=None,
            replay_run_id=None,
        ),
        state.frame.families,
        state.frame.last_observation_publication_time,
    )
    assert metrics.FRAME_STORE.publish(state, newer)
    committed = metrics.FRAME_STORE.read()
    service.cancel_owned("mission-1", None, "Stale owner cancellation")
    assert metrics.FRAME_STORE.read() is committed


@pytest.mark.parametrize("change", ["route", "poi", "phase", "mission"])
def test_replay_revalidates_inputs_after_runtime_commit(
    timing, monkeypatch, change, isolate_mission_storage
):
    from app.models.flight_status import FlightPhase
    from app.models.poi import POICreate
    from app.services.flight_state import get_flight_state_manager

    service, _clocks, coordinator, prepare = timing
    commit = service.runtime.commit_tick
    old = metrics.FRAME_STORE.read()

    def changed_commit(tick):
        result = commit(tick)
        if change == "route":
            service.route_manager.activate_route("replay")
        elif change == "poi":
            service.poi_manager.create_poi(
                POICreate(name="After preparation", latitude=0, longitude=1)
            )
        elif change == "phase":
            get_flight_state_manager().transition_phase(FlightPhase.PRE_DEPARTURE)
        else:
            from app.mission.models import Mission
            from app.mission.storage import save_mission_v2

            save_mission_v2(Mission(id="mission-1", name="Replaced", legs=[]))
        return result

    monkeypatch.setattr(service.runtime, "commit_tick", changed_commit)
    service.collect(coordinator, prepare)
    assert metrics.FRAME_STORE.read().frame is old.frame
    assert metrics.FRAME_STORE.read().status != "ready"
