"""Lifecycle recovery and per-stage failures using real temporary SQLite stores."""

import sqlite3
from datetime import timedelta
from types import SimpleNamespace

from tests.unit.test_flight_events import START


def test_slow_maintenance_does_not_block_recording_health(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    entered, release = Event(), Event()
    owner = lifecycle(tmp_path)
    runtime = owner.reconcile("live")

    def slow_recovery():
        entered.set()
        assert release.wait(5)

    monkeypatch.setattr(runtime, "tick", slow_recovery)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            maintenance = pool.submit(owner.tick)
            try:
                assert entered.wait(2)
                health = pool.submit(owner.status)
                assert health.result(timeout=1)["detection_available"]
            finally:
                release.set()
                maintenance.result(timeout=2)
    finally:
        owner.close()


def lifecycle(tmp_path, clock=None):
    from app.services.flight_events.lifecycle import FlightEventLifecycle

    state = SimpleNamespace(flight_event_runtime=None)
    return FlightEventLifecycle(state, tmp_path, clock=lambda: clock[0] if clock else 0)


def test_initialization_recovers_with_bounded_backoff(tmp_path):
    root = tmp_path / "archive"
    root.write_text("blocked")
    clock = [0]
    owner = lifecycle(root, clock)
    try:
        assert owner.reconcile("simulation") is None
        assert owner.reconcile("live") is None
        assert owner.status()["state"] == "retrying"
        assert owner.status()["cause"] == "storage_path"
        root.unlink()
        clock[0] = 4
        assert owner.reconcile("live") is None
        clock[0] = 5
        runtime = owner.reconcile("live")
        assert runtime is not None
        assert owner.reconcile("live") is runtime
        assert owner.status()["state"] == "ready"
        assert owner.status()["cause"] is None
    finally:
        owner.close()
    assert owner.status()["state"] == "closed"


def test_invalid_policy_is_sanitized_and_retried_without_leaking(tmp_path, monkeypatch):
    monkeypatch.setenv("FLIGHT_DETECTION_POLICY", '{"landing_knots":"secret-value"}')
    clock = [0]
    owner = lifecycle(tmp_path, clock)
    try:
        for second, expected_delay in [
            (0, 5),
            (5, 10),
            (15, 20),
            (35, 40),
            (75, 60),
            (135, 60),
        ]:
            clock[0] = second
            assert owner.reconcile("live") is None
            status = owner.status()
            assert status["cause"] == "invalid_policy"
            assert status["retry_in_seconds"] == expected_delay
            assert "secret-value" not in str(status)
        monkeypatch.setenv("FLIGHT_DETECTION_POLICY", "{}")
        clock[0] = 195
        assert owner.reconcile("live") is not None
    finally:
        owner.close()


def test_corrupt_database_stays_explicit_without_replacing_evidence(tmp_path):
    database = tmp_path / "events.db"
    database.write_bytes(b"retained corrupt evidence")
    owner = lifecycle(tmp_path)
    try:
        assert owner.reconcile("live") is None
        assert owner.status()["cause"] == "database"
        assert database.read_bytes() == b"retained corrupt evidence"
    finally:
        owner.close()


def test_throttled_tick_cannot_clear_failed_maintenance(tmp_path, monkeypatch):
    import app.services.flight_events.live_adapter as adapter

    clock = [100]
    monkeypatch.setattr(adapter.time, "monotonic", lambda: clock[0])
    owner = lifecycle(tmp_path, clock)
    runtime = owner.reconcile("live")
    recover = runtime.capture.recover
    try:

        def fail(_):
            raise sqlite3.OperationalError("disk full")

        monkeypatch.setattr(runtime.capture, "recover", fail)
        owner.tick()
        assert not owner.status()["recording_available"]
        clock[0] = 101
        monkeypatch.setattr(runtime.capture, "recover", recover)
        owner.tick()
        assert not owner.status()["recording_available"]
        clock[0] = 110
        owner.tick()
        assert owner.status()["recording_available"]
    finally:
        owner.close()


def test_retained_capture_maintenance_continues_in_simulation(tmp_path, monkeypatch):
    owner = lifecycle(tmp_path)
    runtime = owner.reconcile("live")
    calls = []
    monkeypatch.setattr(runtime, "tick", lambda: calls.append("maintained"))
    try:
        owner.reconcile("simulation")
        owner.tick()
        assert calls == ["maintained"]
        assert owner.status()["state"] == "inactive"
        assert not owner.status()["recording_available"]
    finally:
        owner.close()


def test_sample_write_failure_does_not_suppress_detector(tmp_path, monkeypatch):
    from app.models.flight_status import FlightPhase
    from app.models.telemetry import TelemetryData
    from app.services.flight_state import get_flight_state_manager

    owner = lifecycle(tmp_path)
    runtime = owner.reconcile("live")
    manager = get_flight_state_manager()
    manager.reset()
    manager.reset_detection()
    # Manual takeoff establishes a durable flight; detector synchronization must
    # still run when the independent raw sample writer fails.
    runtime.events.record_manual_event(
        "m", "l", "off_blocks", START - timedelta(seconds=30), "test", "operator"
    )
    runtime.events.record_manual_event("m", "l", "takeoff", START, "test", "operator")
    telemetry = TelemetryData.model_validate(
        {
            "timestamp": START + timedelta(seconds=1),
            "position": {
                "latitude": 40,
                "longitude": -70,
                "speed": 100,
                "altitude": 1000,
                "observed_at": START + timedelta(seconds=1),
                "speed_observed_at": START + timedelta(seconds=1),
                "altitude_observed_at": START + timedelta(seconds=1),
                "altitude_validity_source": "test",
            },
            "network": {
                "latency_ms": 1,
                "throughput_down_mbps": 1,
                "throughput_up_mbps": 1,
                "packet_loss_percent": 0,
            },
            "obstruction": {"obstruction_percent": 0},
            "environmental": {},
        }
    )
    context = SimpleNamespace(
        parent_mission_id="m",
        leg=SimpleNamespace(id="l"),
        route_id="r",
        route=SimpleNamespace(points=[]),
    )
    original_record = runtime.record_live
    try:

        def fail(_):
            raise sqlite3.OperationalError("disk full with private path")

        monkeypatch.setattr(runtime, "record_live", fail)
        # Phase synchronization must not read the broken raw archive either.
        original_summary = runtime.archive.capture_summary
        monkeypatch.setattr(
            runtime.archive, "capture_summary", lambda *args: fail(None)
        )
        owner.process_live(telemetry, context, manager, lambda: True)
        assert (
            runtime.events.state("m", "l").last_observed_at
            == telemetry.position.observed_at
        )
        assert manager.get_status().phase == FlightPhase.IN_FLIGHT
        assert owner.status()["detection_available"]
        assert not owner.status()["recording_available"]
        assert "private path" not in str(owner.status())
        monkeypatch.setattr(runtime.archive, "capture_summary", original_summary)
        monkeypatch.setattr(runtime, "record_live", original_record)
        owner.process_live(telemetry, context, manager, lambda: True)
        assert owner.status()["recording_available"]
        manager.reset()
        monkeypatch.setattr(runtime, "observe_live", lambda *args, **kwargs: fail(None))
        owner.process_live(telemetry, context, manager, lambda: True)
        assert manager.get_status().phase == FlightPhase.PRE_DEPARTURE
        assert not owner.status()["detection_available"]
    finally:
        owner.close()
        manager.reset()
