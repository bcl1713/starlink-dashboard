"""Two-leg archive recovery, operational stop, and ordered mission package."""

import io
import json
import zipfile
from datetime import timedelta

import pytest

from app.services.flight_events.live_adapter import FlightEventRuntime
from app.services.telemetry_archive.package import build_telemetry_package
from tests.unit.test_archive_review_regressions import CompleteReader
from tests.unit.test_flight_events import START


def test_two_legs_fuel_stop_crash_replay_and_retention(tmp_path, monkeypatch):
    runtime = FlightEventRuntime(tmp_path)
    runtime.archive.append_many(
        [
            (
                START + timedelta(seconds=second),
                "starlink_dish_speed_knots",
                {},
                0,
                "live",
                None,
            )
            for second in range(-1800, 11001)
        ]
    )
    first = [
        (0, "off_blocks"),
        (100, "takeoff"),
        (1000, "landed"),
        (1300, "on_blocks"),
        (3000, "off_blocks"),
        (3100, "takeoff"),
        (3700, "landed"),
        (4000, "on_blocks"),
    ]
    for second, kind in first:
        stop = runtime.events.record_manual_event(
            "m",
            "first",
            kind,
            START + timedelta(seconds=second),
            "observed",
            "operator",
        )
    runtime.events.classify_stop(
        "m", "first", stop.event_id, "destination_complete", "DV offload", "operator"
    )
    for second, kind in [
        (7000, "off_blocks"),
        (7100, "takeoff"),
        (8000, "landed"),
        (8300, "on_blocks"),
    ]:
        stop = runtime.events.record_manual_event(
            "m",
            "second",
            kind,
            START + timedelta(seconds=second),
            "observed",
            "operator",
        )
    runtime.events.classify_stop(
        "m", "second", stop.event_id, "destination_complete", "arrived", "operator"
    )
    # A crash after capture commit but before acknowledgement must replay once.
    original_ack = runtime.events.acknowledge
    monkeypatch.setattr(
        runtime.events,
        "acknowledge",
        lambda *_: (_ for _ in ()).throw(OSError("injected crash")),
    )
    with pytest.raises(OSError):
        runtime.capture.recover(START + timedelta(seconds=11000))
    assert runtime.events.pending_events()
    monkeypatch.setattr(runtime.events, "acknowledge", original_ack)
    runtime.close()
    runtime = FlightEventRuntime(tmp_path)
    try:
        runtime.capture.recover(START + timedelta(seconds=11000))
        for _ in range(80):
            runtime.capture.backfill_one(
                CompleteReader(), START + timedelta(seconds=11000)
            )
            runtime.capture.recover(START + timedelta(seconds=11000))
        assert not runtime.events.pending_events()
        captures = [runtime.archive.capture("m", leg) for leg in ["first", "second"]]
        assert captures[0]["end"] == (START + timedelta(seconds=5800)).isoformat()
        assert captures[1]["start"] == (START + timedelta(seconds=5200)).isoformat()
        assert (
            len(
                [event for event in captures[0]["events"] if event["kind"] == "takeoff"]
            )
            == 2
        )
        runtime.archive.gc(START + timedelta(days=30), None)
        assert not runtime.archive.samples(START, START)
        package = build_telemetry_package("m", captures, allow_partial=False)
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            assert [leg["leg_id"] for leg in manifest["legs"]] == ["first", "second"]
            assert not manifest["partial"]
    finally:
        runtime.close()
