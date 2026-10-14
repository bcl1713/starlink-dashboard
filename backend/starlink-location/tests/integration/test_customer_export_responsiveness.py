"""Real sockets retain deadline failures and probe actual application endpoints."""

import importlib.util
import json
import os
import signal
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
PROBE = ROOT / "tools/acceptance/itinerary-planning/export_probes.py"


def probes():
    spec = importlib.util.spec_from_file_location("export_probes", PROBE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def server(tmp_path, *, blocking=False):
    # Reserve the listener and pass its FD; record ownership before starting a server.
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    owner = {
        "command": "owned Uvicorn responsiveness fixture",
        "port": port,
        "pid": None,
        "pgid": None,
        "temporary_root": str(tmp_path),
    }
    ownership = tmp_path / "server-ownership.json"
    ownership.write_text(json.dumps(owner))
    script = Path(__file__).with_name("customer_export_server.py")
    with (tmp_path / "server.log").open("wb") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                str(script),
                str(tmp_path),
                str(listener.fileno()),
                "blocking" if blocking else "normal",
            ],
            pass_fds=(listener.fileno(),),
            start_new_session=True,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        owner.update(pid=process.pid, pgid=process.pid)
        ownership.write_text(json.dumps(owner))
        listener.close()
        origin = f"http://127.0.0.1:{port}"
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    pytest.fail((tmp_path / "server.log").read_text()[-4000:])
                if probes().probe_request(origin + "/health")["status"] == 200:
                    break
                time.sleep(0.05)
            else:
                pytest.fail("Owned Uvicorn server did not become ready")
            yield origin
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(5)
            owner.update(exit_code=process.returncode, reaped=True)
            with socket.socket() as check:
                owner["listener_gone"] = check.connect_ex(("127.0.0.1", port)) != 0
            ownership.write_text(json.dumps(owner))
            assert owner["listener_gone"]
            with pytest.raises(ProcessLookupError):
                os.killpg(process.pid, 0)


def test_probe_retains_deadline_failures(tmp_path):
    module = probes()
    with server(tmp_path, blocking=True) as origin:
        result = module.probe_request(origin + "/block")
        assert result["error"] == "deadline"
        assert result["elapsed_seconds"] >= 2
        assert result["headers_seconds"] is None
        report = module.probe_series(
            origin, "m", seconds=0.1, output=tmp_path / "negative.json"
        )
        assert report["failures"]
        assert (
            json.loads((tmp_path / "negative.json").read_text())["requests"]
            == report["requests"]
        )


def test_cold_warm_and_save_are_responsive(tmp_path):
    module = probes()
    with server(tmp_path) as origin:
        start = module.probe_request(
            origin + "/api/v2/missions/m/export", method="POST", payload={}
        )
        assert start["status"] == 202
        job = json.loads(start["body"])
        report = module.probe_series(
            origin, "m", seconds=2, output=tmp_path / "cold.json"
        )
        assert not report["failures"]
        deadline = time.monotonic() + 30
        path = origin + f"/api/v2/missions/m/export-preparations/{job['id']}"
        while time.monotonic() < deadline:
            current = json.loads(module.probe_request(path)["body"])
            if current["state"] == "ready":
                break
            assert current["state"] in {"queued", "preparing"}, current
            time.sleep(0.05)
        else:
            pytest.fail("Fixture export did not become ready")
        warm = module.probe_request(path + "/download")
        again = module.probe_request(path + "/download")
        assert warm["status"] == 200 and not warm["error"]
        assert warm["sha256"] == again["sha256"]
        assert warm["headers_seconds"] <= warm["body_seconds"] < 2
        changed = module.probe_request(
            origin + "/api/v2/missions/m", method="PATCH", payload={"name": "Changed"}
        )
        assert changed["status"] == 200
        assert not module.probe_series(
            origin, "m", seconds=1, output=tmp_path / "save.json"
        )["failures"]
        after = module.probe_request(
            origin + "/api/v2/missions/m/export", method="POST", payload={}
        )
        assert after["status"] == 202
        assert json.loads(after["body"])["fingerprint"] != job["fingerprint"]
        while time.monotonic() < deadline:
            second = json.loads(
                module.probe_request(
                    origin
                    + f"/api/v2/missions/m/export-preparations/{json.loads(after['body'])['id']}"
                )["body"]
            )
            if second["state"] == "ready":
                break
            time.sleep(0.05)
        assert second["state"] == "ready"
        assert {"capture", "queue", "assembling"} <= second["stage_timings"].keys()
        assert (
            module.probe_request(origin + "/control/fail-next", method="POST")["status"]
            == 200
        )
        assert (
            module.probe_request(
                origin + "/api/v2/missions/m",
                method="PATCH",
                payload={"name": "Failure control"},
            )["status"]
            == 200
        )
        failed_start = module.probe_request(
            origin + "/api/v2/missions/m/export", method="POST", payload={}
        )
        failed_path = (
            origin
            + f"/api/v2/missions/m/export-preparations/{json.loads(failed_start['body'])['id']}"
        )
        while time.monotonic() < deadline:
            failed = json.loads(module.probe_request(failed_path)["body"])
            if failed["state"] == "failed":
                break
            time.sleep(0.05)
        assert failed["state"] == "failed" and failed["error_code"] == "runtime"
        assert not module.probe_series(
            origin, "m", seconds=0.5, output=tmp_path / "worker-failure.json"
        )["failures"]


def test_thread_saturation_keeps_failed_samples(tmp_path):
    module = probes()
    with server(tmp_path) as origin:
        assert (
            module.probe_request(origin + "/control/saturate", method="POST")["status"]
            == 200
        )
        report = module.probe_series(
            origin, "m", seconds=0.1, output=tmp_path / "saturation.json"
        )
        assert any(
            r["path"].endswith("/m") and r["error"] == "deadline"
            for r in report["failures"]
        )
