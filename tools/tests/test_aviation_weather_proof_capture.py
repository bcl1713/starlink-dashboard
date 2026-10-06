"""Reject ignored ranges, mutable replay, unbounded bodies and leaked workers."""

import importlib
import json
import os
import sys
import time

import pytest


@pytest.fixture
def api():
    return importlib.import_module("acceptance.aviation_weather_proof.capture")


def command(status=200, body=b"abc", headers=None, tail=""):
    meta = json.dumps(
        {"status": status, "headers": headers or {"content-length": str(len(body))}}
    )
    return [
        sys.executable,
        "-c",
        f"import sys,time; print({meta!r},flush=True); sys.stdout.buffer.write({body!r}); sys.stdout.buffer.flush(); {tail}",
    ]


def download(api, tmp_path, **kw):
    return api.download(
        "https://noaa-gfs-bdp-pds.s3.amazonaws.com/test",
        tmp_path / "object.bin",
        budget=api.ExchangeBudget(tmp_path.parent / ("admission-" + tmp_path.name)),
        **kw,
    )


def test_range_ignored_cannot_publish(api, tmp_path):
    with pytest.raises(ValueError, match="206"):
        download(api, tmp_path, byte_range=(10, 12), command=command())
    assert list(tmp_path.iterdir()) == []


def test_content_range_mismatch(api, tmp_path):
    with pytest.raises(ValueError, match="Content-Range"):
        download(
            api,
            tmp_path,
            byte_range=(10, 12),
            command=command(
                206, headers={"content-range": "bytes 11-13/99", "content-length": "3"}
            ),
        )
    assert list(tmp_path.iterdir()) == []


def test_partial_download_removed(api, tmp_path):
    with pytest.raises(ValueError, match="length"):
        download(api, tmp_path, command=command(headers={"content-length": "4"}))
    assert list(tmp_path.iterdir()) == []


def test_exact_range(api, tmp_path):
    saved = download(
        api,
        tmp_path,
        byte_range=(10, 12),
        command=command(
            206, headers={"content-range": "bytes 10-12/99", "content-length": "3"}
        ),
    )
    assert saved.byte_size == 3
    assert (
        saved.sha256
        == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    assert (tmp_path / "object.bin").read_bytes() == b"abc"


def test_changed_bytes_reject_replay(api, tmp_path):
    saved = download(api, tmp_path, command=command())
    m = api.CaptureManifest("isigmet", 1791288000000, (saved,), ("NOAA AWC",))
    api.write_manifest(m, tmp_path / "capture.json")
    loaded = api.load_capture(tmp_path / "capture.json")
    assert api.object_path(loaded, loaded.objects[0]) == tmp_path / "object.bin"
    (tmp_path / "object.bin").write_bytes(b"abd")
    with pytest.raises(ValueError, match="hash"):
        api.load_capture(tmp_path / "capture.json")
    with pytest.raises(ValueError, match="hash"):
        api.object_path(loaded, loaded.objects[0])


def test_exchange_deadline_reaps_worker(api, tmp_path):
    events = []
    start = time.monotonic()
    with pytest.raises(TimeoutError):
        download(
            api,
            tmp_path,
            command=command(tail="time.sleep(60)"),
            timeout=0.15,
            record=lambda **x: events.append(x),
        )
    assert time.monotonic() - start < 3
    pid = next(e["pid"] for e in events if e["event"] == "exchange_owner")
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    assert list(tmp_path.iterdir()) == []


def test_over_object_cap_rejected(api, tmp_path):
    with pytest.raises(ValueError, match="32 MiB"):
        download(
            api,
            tmp_path,
            command=command(headers={"content-length": str(32 * 1024 * 1024 + 1)}),
        )
    assert list(tmp_path.iterdir()) == []


def test_stream_without_length_obeys_cap(api, tmp_path):
    cmd = [
        sys.executable,
        "-c",
        'import sys; print(\'{"status":200,"headers":{}}\',flush=True); sys.stdout.buffer.write(b"x"*(32*1024*1024+1))',
    ]
    with pytest.raises(ValueError, match="32 MiB"):
        download(api, tmp_path, command=cmd)
    assert list(tmp_path.iterdir()) == []


def test_rate_admission_twenty_attempts(api, tmp_path):
    budget = api.ExchangeBudget(tmp_path / "budget")
    for _ in range(20):
        with budget.acquire():
            pass
    with pytest.raises(ValueError, match="20 attempts"):
        with budget.acquire():
            pytest.fail("21st request admitted")


def test_two_exchange_admission(api, tmp_path):
    budget = api.ExchangeBudget(tmp_path / "budget")
    with budget.acquire(), budget.acquire():
        with pytest.raises(ValueError, match="two exchanges"):
            with budget.acquire():
                pytest.fail("third exchange admitted")
    with budget.acquire():
        pass


def test_manifest_path_escape(api, tmp_path):
    saved = download(api, tmp_path, command=command())
    api.write_manifest(
        api.CaptureManifest("isigmet", 1791288000000, (saved,), ("NOAA",)),
        tmp_path / "capture.json",
    )
    data = json.loads((tmp_path / "capture.json").read_text())
    data["objects"][0]["relative_path"] = "../outside"
    (tmp_path / "capture.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="path"):
        api.load_capture(tmp_path / "capture.json")


@pytest.mark.parametrize(
    "source,kw",
    [("bad", {}), ("gfs", {"cycle": "latest"}), ("goes19-c13", {"object_key": "../x"})],
)
def test_invalid_capture_input(api, tmp_path, source, kw):
    with pytest.raises(ValueError):
        api.capture(source, tmp_path / "capture", **kw)
    assert list(tmp_path.iterdir()) == []


def test_inventory_uses_following_offsets(api):
    index = "1:100:d=2026100600:TMP:500 mb:6 hour fcst:\n2:111:d=2026100600:RH:500 mb:6 hour fcst:\n3:200:d=2026100600:UGRD:500 mb:6 hour fcst:\n4:217:d=2026100600:VGRD:500 mb:6 hour fcst:\n5:240:d=2026100600:ABSV:500 mb:6 hour fcst:\n"
    assert api.gfs_ranges(index) == {
        "TMP": (100, 110),
        "UGRD": (200, 216),
        "VGRD": (217, 239),
    }


def test_manifest_rejects_unapproved_url(api, tmp_path):
    obj = api.CapturedObject(
        "http://unapproved.example/file",
        None,
        "object.bin",
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        3,
    )
    (tmp_path / "object.bin").write_bytes(b"abc")
    api.write_manifest(
        api.CaptureManifest("isigmet", 1791288000000, (obj,), ("NOAA",)),
        tmp_path / "capture.json",
    )
    with pytest.raises(ValueError, match="HTTPS"):
        api.load_capture(tmp_path / "capture.json")


def test_manifest_range_matches_size(api, tmp_path):
    obj = api.CapturedObject(
        "https://noaa-gfs-bdp-pds.s3.amazonaws.com/file",
        (10, 13),
        "object.bin",
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        3,
    )
    (tmp_path / "object.bin").write_bytes(b"abc")
    api.write_manifest(
        api.CaptureManifest("gfs", 1791288000000, (obj,), ("NOAA",)),
        tmp_path / "capture.json",
    )
    with pytest.raises(ValueError, match="range"):
        api.load_capture(tmp_path / "capture.json")


def test_changed_manifest_rejects_bound_root(api, tmp_path):
    obj = download(api, tmp_path, command=command())
    api.write_manifest(
        api.CaptureManifest("isigmet", 1791288000000, (obj,), ("NOAA",)),
        tmp_path / "capture.json",
    )
    manifest = api.load_capture(tmp_path / "capture.json")
    (tmp_path / "capture.json").write_text(
        (tmp_path / "capture.json").read_text() + " "
    )
    with pytest.raises(ValueError, match="manifest hash"):
        api.capture_manifest_path(manifest)


def test_rate_window_recovers_after_sixty_seconds(api, tmp_path, monkeypatch):
    exchange = importlib.import_module("acceptance.aviation_weather_proof.exchange")
    now = [1000.0]
    monkeypatch.setattr(exchange.time, "time", lambda: now[0])
    budget = api.ExchangeBudget(tmp_path / "budget")
    for _ in range(20):
        with budget.acquire():
            pass
    now[0] = 1059.9
    with pytest.raises(ValueError, match="20 attempts"):
        with budget.acquire():
            pass
    now[0] = 1060.0
    with budget.acquire():
        pass


def test_failed_capture_never_publishes(api, tmp_path, monkeypatch):
    module = importlib.import_module("acceptance.aviation_weather_proof.capture")
    real = module.download

    def broken(url, path, **kwargs):
        return real(
            url,
            path,
            command=command(headers={"content-length": "4"}),
            budget=api.ExchangeBudget(tmp_path.parent / ("admission-" + tmp_path.name)),
            **kwargs,
        )

    monkeypatch.setattr(module, "download", broken)
    with pytest.raises(ValueError, match="length"):
        api.capture("isigmet", tmp_path / "capture")
    assert not (tmp_path / "capture").exists()
    assert not list(tmp_path.glob(".capture-*"))
    assert not list(tmp_path.rglob("*.partial"))


def test_disk_reservations_cannot_overbook_staging(api, tmp_path):
    with (tmp_path / "previous.bin").open("wb") as stream:
        stream.truncate(800 * 1024 * 1024)
    with api.DiskReservation(tmp_path, 128 * 1024 * 1024):
        with pytest.raises(ValueError, match="staging quota"):
            with api.DiskReservation(tmp_path, 128 * 1024 * 1024):
                pass
    with api.DiskReservation(tmp_path, 128 * 1024 * 1024):
        pass


def test_disconnect_reaps_worker_and_removes_partial(api, tmp_path):
    events = []
    with pytest.raises(ConnectionError):
        download(
            api,
            tmp_path,
            command=command(tail="raise SystemExit(7)"),
            record=lambda **x: events.append(x),
        )
    pid = next(e["pid"] for e in events if e["event"] == "exchange_owner")
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    assert list(tmp_path.iterdir()) == []


def test_worker_parent_death_reaps_socket_owner(tmp_path):
    import ctypes
    import signal
    import subprocess

    # Adopt precisely this test's orphan worker so its final zombie is reaped.
    libc = ctypes.CDLL(None, use_errno=True)
    previous = ctypes.c_int()
    assert libc.prctl(37, ctypes.byref(previous), 0, 0, 0) == 0
    assert libc.prctl(36, 1, 0, 0, 0) == 0
    worker_code = """
import os,time,urllib.request
from acceptance.aviation_weather_proof.exchange import worker
class SlowResponse:
    status=200
    headers={}
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,size):time.sleep(60);return b''
class Opener:
    def open(self,*args,**kwargs):return SlowResponse()
urllib.request.build_opener=lambda *args:Opener()
worker('https://aviationweather.gov/test',os.getppid(),None)
"""
    marker = tmp_path / "worker-pid"
    parent_code = f"""import subprocess,sys,time
from pathlib import Path
child=subprocess.Popen([sys.executable,'-c',{worker_code!r}],stdout=subprocess.PIPE,start_new_session=True)
child.stdout.readline()
Path({str(marker)!r}).write_text(str(child.pid))
time.sleep(60)
"""
    cmd = [sys.executable, "-c", parent_code]
    (tmp_path / "intent.json").write_text(
        json.dumps({"owner": os.getpid(), "command": cmd, "marker": str(marker)})
    )
    parent = None
    worker_pid = None
    reaped = False
    try:
        parent = subprocess.Popen(cmd, start_new_session=True)
        (tmp_path / "parent-owner.json").write_text(
            json.dumps({"child_pid": parent.pid, "child_process_group": parent.pid})
        )
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists(), "worker startup did not complete"
        worker_pid = int(marker.read_text())
        parent.kill()
        parent.wait(timeout=2)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            pid, status = os.waitpid(worker_pid, os.WNOHANG)
            if pid:
                reaped = True
                assert os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGTERM
                break
            time.sleep(0.01)
        assert reaped, "worker survived its parent death"
        with pytest.raises(ProcessLookupError):
            os.kill(worker_pid, 0)
    finally:
        if parent is not None and parent.poll() is None:
            parent.kill()
            parent.wait(timeout=2)
        if worker_pid is not None and not reaped:
            try:
                os.kill(worker_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                os.waitpid(worker_pid, 0)
            except ChildProcessError:
                pass
        libc.prctl(36, previous.value, 0, 0, 0)


@pytest.mark.parametrize(
    "contents", ["null", "[]", "{}", '{"source": "isigmet", "objects": null}']
)
def test_malformed_manifest_raises_value_error(api, tmp_path, contents):
    path = tmp_path / "capture.json"
    path.write_text(contents)
    with pytest.raises(ValueError):
        api.load_capture(path)


@pytest.mark.parametrize(
    "section, field, value",
    [
        ("object", "relative_path", None),
        ("object", "relative_path", []),
        ("object", "url", {}),
        ("object", "url", 42),
        ("object", "sha256", []),
        ("object", "byte_size", "3"),
        ("object", "byte_range", [[], 12]),
        ("manifest", "attribution", [{}]),
        ("manifest", "attribution", [None]),
        ("manifest", "attribution", "NOAA"),
        ("manifest", "objects", {}),
        ("manifest", "captured_at_ms", True),
    ],
)
def test_nested_manifest_types_raise_value_error(api, tmp_path, section, field, value):
    # These invalid values must be rejected before path parsing or registry hashing.
    (tmp_path / "object.bin").write_bytes(b"abc")
    data = {
        "source": "isigmet",
        "captured_at_ms": 1791288000000,
        "objects": [
            {
                "url": "https://aviationweather.gov/test",
                "byte_range": None,
                "relative_path": "object.bin",
                "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
                "byte_size": 3,
            }
        ],
        "attribution": ["NOAA"],
    }
    target = data["objects"][0] if section == "object" else data
    target[field] = value
    path = tmp_path / "capture.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        api.load_capture(path)


def test_departed_manifest_raises_value_error(api, tmp_path):
    with pytest.raises(ValueError):
        api.load_capture(tmp_path / "departed.json")


def test_invalid_destination_raises_value_error(api):
    with pytest.raises(ValueError):
        api.capture("isigmet", None)
