"""Capture boundaries, pinned history, idempotent outbox delivery and gaps."""

from datetime import timedelta

from app.services.flight_events.live_adapter import FlightEventRuntime
from app.services.telemetry_archive.coordinator import CaptureCoordinator
from app.services.telemetry_archive.store import ArchiveStore
from tests.unit.test_archive_review_regressions import CompleteReader, drain
from tests.unit.test_flight_events import START


def test_window_and_restart_idempotence(tmp_path):
    runtime = FlightEventRuntime(tmp_path)
    archive = ArchiveStore(tmp_path / "archive.db")
    capture = CaptureCoordinator(runtime.events, archive)
    for second in range(-1800, 4001):
        archive.append(
            START + timedelta(seconds=second),
            "starlink_dish_speed_knots",
            {},
            10,
            "live",
        )
    runtime.events.record_manual_event(
        "m", "l", "off_blocks", START, "observed", "operator"
    )
    runtime.events.record_manual_event(
        "m", "l", "takeoff", START + timedelta(seconds=100), "observed", "operator"
    )
    runtime.events.record_manual_event(
        "m", "l", "landed", START + timedelta(seconds=1000), "observed", "operator"
    )
    park = runtime.events.record_manual_event(
        "m", "l", "on_blocks", START + timedelta(seconds=2000), "observed", "operator"
    )
    runtime.events.classify_stop(
        "m", "l", park.event_id, "destination_complete", "DV offloaded", "operator"
    )
    capture.recover(START + timedelta(seconds=4000))
    for _ in range(30):
        capture.backfill_one(CompleteReader(), START + timedelta(seconds=4000))
        capture.recover(START + timedelta(seconds=4000))
    first = archive.capture("m", "l")
    assert first["start"] == (START - timedelta(seconds=1800)).isoformat()
    assert first["end"] == (START + timedelta(seconds=3800)).isoformat()
    assert first["state"] == "sealed"
    capture.recover(START + timedelta(seconds=5000))
    assert archive.capture("m", "l")["revision"] == first["revision"]
    assert not runtime.events.pending_events()


def test_missing_start_and_null_are_explicit(tmp_path):
    runtime = FlightEventRuntime(tmp_path)
    archive = ArchiveStore(tmp_path / "archive.db")
    archive.append(START, "starlink_network_latency_ms_current", {}, None, "live")
    archive.append(
        START, "starlink_network_throughput_down_mbps_current", {}, 0, "live"
    )
    runtime.events.record_manual_event(
        "m", "l", "off_blocks", START, "observed", "operator"
    )
    CaptureCoordinator(runtime.events, archive).recover(START)
    status = archive.capture("m", "l")
    assert status["gaps"]
    rows = archive.samples(START, START)
    assert {row["value"] for row in rows} == {None, 0}


def test_candidate_pin_and_distinct_ip_labels(tmp_path):
    archive = ArchiveStore(tmp_path / "archive.db")
    for second in range(-1800, 31):
        archive.append(
            START + timedelta(seconds=second),
            "starlink_ground_entry_point_info",
            {"public_ip": "192.0.2.1", "secret": "exclude"},
            1,
            "live",
        )
    archive.append(
        START + timedelta(seconds=31),
        "starlink_ground_entry_point_info",
        {"public_ip": "192.0.2.2"},
        1,
        "live",
    )
    archive.gc(START + timedelta(seconds=1000), START - timedelta(seconds=1800))
    rows = archive.samples(
        START - timedelta(seconds=1800), START + timedelta(seconds=31)
    )
    assert rows[0]["timestamp"] == (START - timedelta(seconds=1800)).isoformat()
    assert {row["labels"].get("public_ip") for row in rows} == {
        "192.0.2.1",
        "192.0.2.2",
    }
    assert all("secret" not in row["labels"] for row in rows)
    archive.append(START, "starlink_dish_speed_knots", {}, 99, "simulation")
    assert not any(row["value"] == 99 for row in archive.samples(START, START))


def test_recovery_retry_replays_without_losing_pending_work(tmp_path):
    import httpx

    runtime = FlightEventRuntime(tmp_path)
    archive = runtime.archive
    coordinator = runtime.capture
    runtime.events.record_manual_event(
        "m", "l", "off_blocks", START, "observed", "operator"
    )
    coordinator.recover(START)

    class Offline:
        def read(self, begin, end):
            raise httpx.ConnectError("offline")

    coordinator.backfill_one(Offline(), START)
    with archive.ledger.connect() as db:
        job = db.execute(
            "SELECT start, attempts, error FROM raw_windows ORDER BY start LIMIT 1"
        ).fetchone()
    assert job[1] == 1
    assert job[2] == "ConnectError"

    class Online:
        def read(self, begin, end):
            return [
                (
                    begin + timedelta(seconds=second),
                    "starlink_dish_speed_knots",
                    {},
                    0,
                    "live",
                    begin,
                )
                for second in range(int((end - begin).total_seconds()) + 1)
            ]

    coordinator.backfill_one(Online(), START + timedelta(seconds=10))
    with archive.ledger.connect() as db:
        recovered = db.execute(
            "SELECT start, attempts FROM raw_windows ORDER BY start LIMIT 1"
        ).fetchone()
    assert recovered[0] == job[0]
    assert recovered[1] == 2
    runtime.close()


def test_sealed_csv_archive_survives_raw_retention(tmp_path):
    import zipfile

    runtime = FlightEventRuntime(tmp_path)
    archive = runtime.archive
    rows = [
        (
            START + timedelta(seconds=second),
            "starlink_dish_speed_knots",
            {},
            10,
            "live",
            None,
        )
        for second in range(-1800, 4001)
    ]
    archive.append_many(rows)
    for second, kind in [
        (0, "off_blocks"),
        (100, "takeoff"),
        (1000, "landed"),
        (2000, "on_blocks"),
    ]:
        park = runtime.events.record_manual_event(
            "m", "l", kind, START + timedelta(seconds=second), "observed", "operator"
        )
    runtime.events.classify_stop(
        "m", "l", park.event_id, "destination_complete", "DV stop", "operator"
    )
    runtime.capture.recover(START + timedelta(seconds=4000))
    drain(runtime, START + timedelta(seconds=4000))
    paths = list((tmp_path / "sealed").glob("*.zip"))
    assert len(paths) == 1
    before = paths[0].read_bytes()
    archive.gc(START + timedelta(days=30), None)
    assert not archive.samples(START, START)
    assert paths[0].read_bytes() == before
    with zipfile.ZipFile(paths[0]) as package:
        assert "legs/001/observations.csv" in package.namelist()
    runtime.close()


def test_live_capture_preserves_last_known_proxy_without_freshness_claim(
    tmp_path, monkeypatch
):
    from app.services.ground_entry_point import GroundEntryPoint
    from tests.conftest import default_mock_telemetry

    runtime = FlightEventRuntime(tmp_path)
    monkeypatch.setattr(
        "app.services.ground_entry_point.get_cached_ground_entry_point",
        lambda: GroundEntryPoint(
            ip="192.0.2.1", city="Example", country="US", latitude=40, longitude=-70
        ),
    )
    telemetry = default_mock_telemetry()
    runtime.record_live(telemetry)
    rows = runtime.archive.samples(telemetry.timestamp, telemetry.timestamp)
    proxies = [
        row for row in rows if row["metric"] == "starlink_ground_entry_point_info"
    ]
    assert proxies[0]["labels"]["ip"] == "192.0.2.1"
    assert proxies[0]["observed_at"] is None
    assert proxies[0]["labels"]["source"] == "cached_last_known_proxy"
    runtime.close()
