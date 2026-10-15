"""Bounded research captures must be reproducible and reject incomplete data."""

import gzip
import hashlib
import io
import json
from urllib.error import HTTPError

import pytest
from acceptance.weather_detail_comparison.capture import (
    Downloader,
    RateLimited,
    decompress,
    mrms_objects,
    opera_objects,
    rainviewer_frame,
)
from acceptance.weather_detail_comparison.capture_detail import plan_comparisons
from acceptance.weather_detail_comparison.model import (
    CaptureSet,
    Snapshot,
    TileKey,
    load_capture,
    write_capture,
)


def snapshot(root, source="mrms", time=1791253200):
    path = root / f"{source}-{time}.bin"
    path.write_bytes(b"immutable observations")
    return Snapshot(
        source,
        "PrecipRate" if source == "mrms" else "RATE",
        time,
        time + 60,
        "mm/h",
        "source metadata",
        "https://mrms.ncep.noaa.gov/data/test",
        "public domain",
        "NOAA",
        path,
        hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def test_changed_capture_bytes_are_rejected(tmp_path):
    saved = snapshot(tmp_path)
    write_capture(CaptureSet(tmp_path, (saved,), {}, {}))
    saved.local_path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash"):
        load_capture(tmp_path / "capture.json")


def test_capture_caps_each_source(tmp_path):
    captures = tuple(snapshot(tmp_path, time=1791253200 + i * 60) for i in range(3))
    with pytest.raises(ValueError, match="snapshot"):
        write_capture(CaptureSet(tmp_path, captures, {}, {}))


def test_round_trip_preserves_frame_scoped_identity(tmp_path):
    saved = snapshot(tmp_path)
    write_capture(CaptureSet(tmp_path, (saved,), {}, {"precipitation": "unmeasured"}))
    loaded = load_capture(tmp_path / "capture.json")
    assert loaded.snapshots == (saved,)
    assert loaded.metadata["precipitation"] == "unmeasured"


@pytest.mark.parametrize("values", [(1, 0, 0), (8, 0, 0), (7, 128, 0), (2, -1, 0)])
def test_invalid_xyz_rejected(values):
    with pytest.raises(ValueError):
        TileKey(*values)


def test_manifest_rejects_path_escape(tmp_path):
    saved = snapshot(tmp_path)
    write_capture(CaptureSet(tmp_path, (saved,), {}, {}))
    path = tmp_path / "capture.json"
    data = json.loads(path.read_text())
    data["snapshots"][0]["local_path"] = "../outside.bin"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="path"):
        load_capture(path)


def test_timestamp_mismatch_and_forecast_rejected():
    metadata = {"host": "https://tilecache.rainviewer.com", "radar": {"past": []}}
    with pytest.raises(ValueError):
        rainviewer_frame(metadata)
    metadata["radar"]["past"] = [{"time": -1, "path": "/v2/radar/opaque"}]
    with pytest.raises(ValueError):
        rainviewer_frame(metadata)


def test_product_discovery_excludes_accumulation_and_latest_alias():
    assert mrms_objects('href="MRMS_PrecipRate.latest.grib2.gz"') == []
    assert mrms_objects('href="MRMS_PrecipRate_00.00_20261006-020000.grib2.gz"')
    xml = "<ListBucketResult><Contents><Key>2026/10/06/OPERA/COMP/OPERA@20261006T0200@0@RATE.h5</Key></Contents><Contents><Key>OPERA@20261006T0200@0@ACRR.h5</Key></Contents></ListBucketResult>"
    objects = opera_objects(xml)
    assert len(objects) == 1
    assert objects[0][1].endswith("RATE.h5")


def test_download_bounds_and_partial_cleanup(tmp_path):
    downloader = Downloader(
        tmp_path, opener=lambda *a, **k: io.BytesIO(b"12345"), object_limit=4
    )
    with pytest.raises(ValueError, match="limit"):
        downloader.get("https://mrms.ncep.noaa.gov/a", "sample.bin")
    assert not list(tmp_path.glob("*.partial"))
    assert not (tmp_path / "sample.bin").exists()


def test_aggregate_storage_limit(tmp_path):
    (tmp_path / "existing").write_bytes(b"123")
    downloader = Downloader(
        tmp_path, opener=lambda *a, **k: io.BytesIO(b"456"), storage_limit=5
    )
    with pytest.raises(ValueError, match="limit"):
        downloader.get("https://mrms.ncep.noaa.gov/a", "new")


def test_rate_limit_counts_failed_attempts_and_honors_window(tmp_path):
    now = [0.0]
    calls = []

    def fail(url, **kwargs):
        calls.append(kwargs["timeout"])
        raise HTTPError(url, 503, "unavailable", {}, None)

    downloader = Downloader(
        tmp_path, opener=fail, clock=lambda: now[0], sleep=lambda n: None
    )
    for i in range(15):
        with pytest.raises(HTTPError):
            downloader.get("https://mrms.ncep.noaa.gov/a", str(i))
    with pytest.raises(RateLimited):
        downloader.get("https://mrms.ncep.noaa.gov/a", "exhausted")
    assert len(calls) == 30
    assert set(calls) == {45}
    now[0] = 60.01
    with pytest.raises(HTTPError):
        downloader.get("https://mrms.ncep.noaa.gov/a", "new-window")
    assert len(calls) == 32
    assert downloader.active_limit == 2


def test_retry_after_is_bounded(tmp_path):
    sleeps = []

    def fail(url, **kwargs):
        raise HTTPError(url, 429, "slow down", {"Retry-After": "999999"}, None)

    downloader = Downloader(tmp_path, opener=fail, sleep=sleeps.append)
    with pytest.raises(RateLimited):
        downloader.get("https://mrms.ncep.noaa.gov/a", "limited")
    assert sleeps == []


@pytest.mark.parametrize(
    "url",
    [
        "http://mrms.ncep.noaa.gov/a",
        "https://evil.test/a",
        "https://user@mrms.ncep.noaa.gov/a",
        "https://mrms.ncep.noaa.gov:444/a",
    ],
)
def test_download_rejects_unapproved_origins(tmp_path, url):
    downloader = Downloader(
        tmp_path, opener=lambda *a, **k: pytest.fail("unexpected dial")
    )
    with pytest.raises(ValueError):
        downloader.get(url, "sample")


def test_decompression_is_bounded_and_atomic(tmp_path):
    archive = tmp_path / "sample.gz"
    archive.write_bytes(gzip.compress(b"x" * 1024))
    with pytest.raises(ValueError, match="limit"):
        decompress(archive, tmp_path / "decoded", limit=100)
    assert not (tmp_path / "decoded").exists()
    assert not list(tmp_path.glob("*.partial"))


def test_regional_comparison_uses_matching_observed_frame(tmp_path):
    raw = snapshot(tmp_path)
    metadata_path = tmp_path / "rainviewer.json"
    metadata_path.write_text(
        json.dumps(
            {
                "host": "https://tilecache.rainviewer.com",
                "radar": {"past": [{"time": 1791253200, "path": "/v2/radar/opaque"}]},
            }
        )
    )
    rv = Snapshot(
        "rainviewer",
        "radar",
        1791253200,
        1791253260,
        "provider RGBA",
        "EPSG:3857",
        "https://api.rainviewer.com/public/weather-maps.json",
        "test",
        "RainViewer",
        metadata_path,
        hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
    )
    captures = CaptureSet(
        tmp_path,
        (rv, raw),
        {},
        {
            "regions": {
                "mrms": {"latitude": 40, "longitude": -100, "rain_fraction": 0.8}
            }
        },
    )
    planned = plan_comparisons(captures)
    assert planned.metadata["comparisons"][0]["delta_seconds"] == 0
    assert planned.metadata["comparisons"][0]["rainviewer_identity"] == rv.identity


def test_regional_comparison_refuses_unmatched_time(tmp_path):
    from dataclasses import replace

    raw = snapshot(tmp_path)
    metadata_path = tmp_path / "rainviewer.json"
    metadata_path.write_text(
        json.dumps({"radar": {"past": [{"time": 1791252000, "path": "/v2/radar/old"}]}})
    )
    rv = replace(
        raw,
        source="rainviewer",
        product="radar",
        local_path=metadata_path,
        sha256=hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
    )
    captures = CaptureSet(
        tmp_path,
        (raw, rv),
        {},
        {"regions": {"mrms": {"latitude": 40, "longitude": -100}}},
    )
    with pytest.raises(ValueError, match="five minutes"):
        plan_comparisons(captures)


def test_delayed_eof_exceeds_absolute_deadline(tmp_path):
    now = [0.0]

    class DelayedEOF(io.BytesIO):
        def read(self, size):
            now[0] = 46.0
            return b""

    downloader = Downloader(
        tmp_path, opener=lambda *a, **k: DelayedEOF(), clock=lambda: now[0]
    )
    with pytest.raises(TimeoutError, match="deadline"):
        downloader.get("https://mrms.ncep.noaa.gov/a", "late")
    assert not (tmp_path / "late").exists()
    assert not list(tmp_path.glob("*.partial"))


@pytest.mark.parametrize("phase", ["headers", "body", "eof"])
def test_blocked_exchange_is_cancelled_and_reaped(tmp_path, phase):
    import os
    import sys
    import time

    from acceptance.weather_detail_comparison.exchange import open_exchange

    events = []
    prefix = "" if phase == "headers" else "print('{\"status\":200}', flush=True);"
    body = (
        'sys.stdout.buffer.write(b"x"); sys.stdout.flush();' if phase == "body" else ""
    )
    command = [sys.executable, "-c", f"import sys,time;{prefix}{body}time.sleep(60)"]
    downloader = Downloader(
        tmp_path,
        opener=lambda *a, **k: open_exchange(
            a[0], timeout=0.2, command=command, record=lambda **v: events.append(v)
        ),
    )
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="deadline"):
        downloader.get("https://mrms.ncep.noaa.gov/a", "blocked")
    assert time.monotonic() - started < 2
    child = next(e["pid"] for e in events if e["event"] == "exchange_owner")
    with pytest.raises(ProcessLookupError):
        os.kill(child, 0)
    assert events[-1]["event"] == "exchange_closed"
    assert not (tmp_path / "blocked").exists()
    assert not list(tmp_path.glob("*.partial"))


def test_concurrent_downloads_share_remaining_storage(tmp_path):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    barrier = threading.Barrier(2)

    class ConcurrentResponse(io.BytesIO):
        def read(self, size):
            if self.tell() == 0:
                barrier.wait(timeout=2)
            return super().read(size)

    downloader = Downloader(
        tmp_path,
        opener=lambda *a, **k: ConcurrentResponse(b"x" * 1200),
        storage_limit=2000,
    )

    def download(name):
        try:
            return downloader.get("https://mrms.ncep.noaa.gov/a", name)
        except ValueError:
            return None

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(download, ["first", "second"]))
    assert sum(value is not None for value in results) == 1
    assert sum(p.stat().st_size for p in tmp_path.rglob("*") if p.is_file()) <= 2000
    assert not list(tmp_path.glob("*.partial"))


def test_decompression_uses_remaining_aggregate_budget(tmp_path):
    archive = tmp_path / "sample.gz"
    archive.write_bytes(gzip.compress(b"x" * 500))
    (tmp_path / "existing").write_bytes(b"x" * 1000)
    with pytest.raises(ValueError, match="storage limit"):
        decompress(archive, tmp_path / "decoded", limit=1000, storage_limit=1200)
    assert not (tmp_path / "decoded").exists()
    assert not list(tmp_path.glob("*.partial"))


def test_interrupted_capture_cannot_orphan_exchange_worker(tmp_path):
    import os
    import signal
    import sys
    import time

    from acceptance.weather_detail_comparison.owned import run_owned

    events = tmp_path / "exchange-events.jsonl"
    script = f"""import json,os,sys
from pathlib import Path
from acceptance.weather_detail_comparison.exchange import open_exchange
command=[sys.executable,"-c", "import time; from acceptance.weather_detail_comparison.exchange import arm_parent_death; arm_parent_death("+str(os.getpid())+"); print('{{\\\"status\\\":200}}', flush=True); time.sleep(60)"]
def record(**values):
    with Path({str(events)!r}).open("a") as file: file.write(json.dumps(values)+"\\n")
with open_exchange('https://mrms.ncep.noaa.gov/a',command=command,record=record) as response:
    response.read(1)
"""
    worker = None
    try:
        result = run_owned([sys.executable, "-c", script], 0.6, tmp_path / "owner")
        worker = next(
            event["pid"]
            for event in map(json.loads, events.read_text().splitlines())
            if event["event"] == "exchange_owner"
        )
        assert result == 124
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try:
                os.waitpid(worker, os.WNOHANG)
                os.kill(worker, 0)
            except (ProcessLookupError, ChildProcessError):
                break
            time.sleep(0.02)
        with pytest.raises(ProcessLookupError):
            os.kill(worker, 0)
    finally:
        if worker:
            try:
                os.kill(worker, signal.SIGKILL)
                os.waitpid(worker, 0)
            except (ProcessLookupError, ChildProcessError):
                pass
