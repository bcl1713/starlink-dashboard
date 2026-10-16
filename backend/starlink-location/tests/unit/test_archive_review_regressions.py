"""Independent-review regressions: retained history, raw coverage, bounded retries."""

from datetime import timedelta

from app.services.flight_events.live_adapter import FlightEventRuntime
from app.services.telemetry_archive.store import METRICS
from tests.unit.test_flight_events import START


def prepare(runtime):
    runtime.archive.append_many(
        [
            (
                START + timedelta(seconds=second),
                metric,
                {"source": "accepted_live"},
                1,
                "live",
                None,
            )
            for second in range(-1800, 4001, 5)
            for metric in METRICS
        ]
    )
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
        "m", "l", park.event_id, "destination_complete", "DV offload", "operator"
    )


class CompleteReader:
    def read(self, begin, end):
        return [
            (
                begin + timedelta(seconds=second),
                metric,
                {
                    "source": "prometheus_raw_scrape",
                    "ip": "192.0.2.1" if second < 150 else "192.0.2.2",
                },
                1,
                "live",
                None,
            )
            for second in range(0, int((end - begin).total_seconds()) + 1, 5)
            for metric in METRICS
        ]


def drain(runtime, now):
    for _ in range(40):
        runtime.capture.backfill_one(CompleteReader(), now)
        runtime.capture.recover(now)


def test_correction_after_gc_reuses_sealed_observations(tmp_path):
    runtime = FlightEventRuntime(tmp_path)
    try:
        prepare(runtime)
        now = START + timedelta(seconds=5000)
        runtime.capture.recover(now)
        drain(runtime, now)
        original = runtime.archive.capture("m", "l")
        assert original["state"] == "sealed"
        assert original["complete"]
        runtime.archive.gc(now + timedelta(days=30), None)
        landing = next(
            event for event in runtime.events.events("m", "l") if event.kind == "landed"
        )
        runtime.events.correct_event(
            landing.event_id,
            landing.occurred_at + timedelta(seconds=1),
            "time correction",
            "operator",
            1,
            "m",
            "l",
        )
        runtime.capture.recover(now)
        revised = runtime.archive.capture("m", "l")
        assert revised["revision"] != original["revision"]
        assert revised["state"] == "sealed"
        assert revised["samples"] == original["samples"]
    finally:
        runtime.close()


def test_live_rows_do_not_replace_raw_extraction(tmp_path):
    runtime = FlightEventRuntime(tmp_path)
    try:
        prepare(runtime)
        now = START + timedelta(seconds=5000)
        runtime.capture.recover(now)
        assert not runtime.archive.capture("m", "l")["complete"]
        drain(runtime, now)
        capture = runtime.archive.capture("m", "l")
        raw = [
            sample
            for sample in capture["samples"]
            if sample["labels"].get("source") == "prometheus_raw_scrape"
        ]
        assert raw
        assert {sample["labels"].get("ip") for sample in raw} == {
            "192.0.2.1",
            "192.0.2.2",
        }
        assert capture["raw_coverage"]
    finally:
        runtime.close()


def test_empty_raw_queries_retry_then_finalize_partial_and_release_retention(tmp_path):
    runtime = FlightEventRuntime(tmp_path)
    try:
        prepare(runtime)
        now = START + timedelta(seconds=5000)
        runtime.capture.recover(now)

        class Empty:
            def read(self, begin, end):
                return []

        runtime.capture.max_retries = 2
        for attempt in range(40):
            runtime.capture.backfill_one(
                Empty(), now + timedelta(seconds=attempt * 301)
            )
            runtime.capture.recover(now + timedelta(seconds=attempt * 301))
        capture = runtime.archive.capture("m", "l")
        assert capture["state"] == "sealed"
        assert not capture["complete"]
        assert capture["gaps"]
        assert capture["samples"]
        runtime.archive.gc(now + timedelta(days=30), None)
        assert not runtime.archive.samples(START, START)
    finally:
        runtime.close()
