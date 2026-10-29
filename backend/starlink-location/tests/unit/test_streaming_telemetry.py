"""Lossless exports read active and sealed evidence without blocking recording."""

import csv
import io
import json
import sqlite3
import threading
import zipfile
from datetime import datetime, timezone

import pytest

from app.services.telemetry_archive.store import ArchiveStore
from tests.unit.test_telemetry_package import capture


def test_repeated_compact_series_do_not_repeat_disk_work(tmp_path):
    from app.services.telemetry_archive.compact import SeriesIndex

    index = SeriesIndex(tmp_path / "series.sqlite3", 1024 * 1024)
    statements = []
    index.db.set_trace_callback(statements.append)
    sample = {
        "metric": "starlink_dish_speed_knots",
        "labels": {"source": "accepted_live", "city": "same source"},
    }
    try:
        ids = {index.identify(sample) for _ in range(1000)}
        assert len(ids) == 1
        assert len(list(index.rows())) == 1
        assert len([sql for sql in statements if sql.startswith("INSERT")]) < 10
    finally:
        index.close()


def seed(archive, *, sealed=False, count=7):
    samples = [
        {
            "timestamp": f"2026-01-01T00:00:{i:02d}+00:00",
            "metric": "starlink_dish_altitude_feet",
            "labels": {"source": "accepted_live", "city": f"München-{i}"},
            "value": None if i == 0 else float(i - 1),
            "observed_at": None if i == 0 else f"2026-01-01T00:00:{i:02d}+00:00",
        }
        for i in range(count)
    ]
    item = capture("one", complete=sealed) | {
        "state": "sealed" if sealed else "recording",
        "available_until": "2026-01-01T01:00:00+00:00",
        "samples": samples if sealed else [],
    }
    with archive.ledger.connect() as db:
        db.execute(
            "INSERT INTO captures VALUES (?,?,?,?)",
            ("m", "one", "one", json.dumps(item, ensure_ascii=False)),
        )
        db.execute("INSERT INTO capture_heads VALUES (?,?,?)", ("m", "one", "one"))
    if not sealed:
        archive.append_many(
            [
                (
                    datetime.fromisoformat(s["timestamp"]),
                    s["metric"],
                    s["labels"],
                    s["value"],
                    "live",
                    (
                        datetime.fromisoformat(s["observed_at"])
                        if s["observed_at"]
                        else None
                    ),
                )
                for s in samples
            ]
        )
    return samples


@pytest.mark.parametrize("sealed", [False, True])
@pytest.mark.parametrize("representation", ["full", "compact"])
def test_streamed_formats_reconstruct_every_observation(
    tmp_path, sealed, representation
):
    from app.services.telemetry_archive.stream_package import write_telemetry_package
    from app.services.telemetry_archive.stream_reader import stream_captures

    archive = ArchiveStore(tmp_path / "archive.db")
    expected = seed(archive, sealed=sealed)
    output = io.BytesIO()
    with stream_captures(archive, "m", ["one"]) as captures:
        result = write_telemetry_package(
            output,
            "m",
            captures,
            representation=representation,
            workdir=tmp_path,
            check=lambda: None,
        )
    with zipfile.ZipFile(output) as package:
        rows = list(
            csv.DictReader(
                io.StringIO(package.read("legs/001/observations.csv").decode())
            )
        )
        if representation == "compact":
            series = {
                row["series_id"]: row
                for row in csv.DictReader(
                    io.StringIO(package.read("legs/001/series.csv").decode())
                )
            }
            rows = [
                row
                | {
                    k: v
                    for k, v in series[row["series_id"]].items()
                    if k != "series_id"
                }
                for row in rows
            ]
        reconstructed = [
            {
                "timestamp": row["timestamp_utc"],
                "metric": row["metric"],
                "labels": json.loads(row["labels_json"]),
                "value": float(row["value"]) if row["value"] else None,
                "observed_at": row["source_observed_at_utc"] or None,
            }
            for row in rows
        ]
        assert reconstructed == expected
        assert rows[0]["availability"] == "missing"
        assert result["observation_count"] == 7
        assert package.testzip() is None


def test_pinned_export_allows_recording_and_keeps_original_snapshot(tmp_path):
    from app.services.telemetry_archive.stream_reader import stream_captures

    archive = ArchiveStore(tmp_path / "archive.db")
    seed(archive)
    errors = []
    finished = threading.Event()

    def record():
        try:
            archive.append(
                datetime(2026, 1, 1, 0, 0, 30, tzinfo=timezone.utc),
                "starlink_dish_altitude_feet",
                {},
                999,
                "live",
            )
        except (sqlite3.Error, RuntimeError) as error:
            errors.append(error)
        finally:
            finished.set()

    with stream_captures(archive, "m", ["one"]) as captures:
        item = next(iter(captures))
        samples = iter(item["samples"])
        first = next(samples)
        worker = threading.Thread(target=record)
        worker.start()
        try:
            assert finished.wait(2), "Export reader blocked a recording commit"
        finally:
            # The export connection closes before joining a failed writer.
            remaining = list(samples)
    worker.join(5)
    assert not worker.is_alive()
    assert not errors
    assert len([first, *remaining]) == 7


def test_truncated_sealed_capture_fails_instead_of_exporting_partial_success(tmp_path):
    from app.services.telemetry_archive.stream_reader import stream_captures

    archive = ArchiveStore(tmp_path / "archive.db")
    seed(archive, sealed=True)
    with archive.ledger.connect() as db:
        db.execute("UPDATE captures SET payload=substr(payload,1,length(payload)-4)")
    with pytest.raises(ValueError), stream_captures(archive, "m", ["one"]) as captures:
        for item in captures:
            list(item["samples"])


@pytest.mark.parametrize("representation", ["full", "compact"])
def test_recovering_head_includes_retained_sealed_samples_after_gc(
    tmp_path, representation
):
    from app.services.telemetry_archive.stream_package import write_telemetry_package
    from app.services.telemetry_archive.stream_reader import stream_captures

    archive = ArchiveStore(tmp_path / "archive.db")
    expected = seed(archive, sealed=True)
    head = capture("one", complete=False) | {
        "revision": "corrected",
        "state": "recovering",
        "available_until": "2026-01-01T01:00:00+00:00",
        "samples": [],
    }
    with archive.ledger.connect() as db:
        db.execute(
            "INSERT INTO captures VALUES (?,?,?,?)",
            ("m", "one", "corrected", json.dumps(head)),
        )
        db.execute("UPDATE capture_heads SET revision='corrected'")
    archive.append(
        datetime.fromisoformat(expected[2]["timestamp"]),
        expected[2]["metric"],
        expected[2]["labels"],
        999,
        "live",
        datetime.fromisoformat(expected[2]["observed_at"]),
    )
    expected[2]["value"] = 999.0
    output = io.BytesIO()
    with stream_captures(archive, "m", ["one"], workdir=tmp_path) as captures:
        result = write_telemetry_package(
            output,
            "m",
            captures,
            representation=representation,
            workdir=tmp_path,
            check=lambda: None,
        )
    assert result["observation_count"] == len(expected) == 7
    with zipfile.ZipFile(output) as package:
        rows = list(
            csv.DictReader(
                io.StringIO(package.read("legs/001/observations.csv").decode())
            )
        )
        assert [
            (row["timestamp_utc"], float(row["value"]) if row["value"] else None)
            for row in rows
        ] == [(item["timestamp"], item["value"]) for item in expected]
    assert not list(tmp_path.glob("source-*.sqlite3"))
