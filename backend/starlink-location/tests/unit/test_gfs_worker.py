"""Actual worker/decoder processes prove cancellation and absence semantics."""

import json
import os
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from app.services.aviation_weather.settings import AviationSettingsStore

from tests.fixtures.gfs_fields import RUN


def wait_until(predicate):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("owned worker did not reach expected state")


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # A killed parent's decoder can briefly be a zombie until the container's
    # init reaps it; it no longer owns descriptors/locks or consumes resources.
    return Path(f"/proc/{pid}/stat").read_text().split()[2] != "Z"


@contextmanager
def worker_process(root, mode):
    command = [
        sys.executable,
        "-m",
        "tests.fixtures.gfs_worker_process",
        str(root),
        mode,
    ]
    (root / "owner.json").write_text(
        json.dumps({"command": command, "state": "starting"})
    )
    log = (root / "worker.log").open("w")
    process = subprocess.Popen(
        command,
        cwd=Path(__file__).parents[2],
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    (root / "owner.json").write_text(
        json.dumps({"command": command, "pid": process.pid, "pgid": process.pid})
    )
    try:
        yield process
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=12)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        else:
            process.wait(timeout=5)
        log.close()
        assert not alive(process.pid)


def setup(root):
    from app.services.aviation_weather.gfs.ipc import GfsMailbox

    settings = AviationSettingsStore(root / "settings.json")
    enabled = settings.update({"winds": True, "temperature": True})
    (root / "clock.json").write_text(json.dumps(RUN))
    mailbox = GfsMailbox(root / "mailbox", settings)
    mailbox.renew(uuid.uuid4().hex, enabled, RUN)
    return mailbox, settings, enabled


def test_real_child_publishes_once_and_stops_on_reader_expiry(tmp_path):
    mailbox, _settings, enabled = setup(tmp_path)
    with worker_process(tmp_path, "normal") as process:
        pointer = tmp_path / "artifacts/current.json"
        wait_until(pointer.exists)
        assert json.loads(pointer.read_text())["revision"] == enabled.revision
        assert mailbox.healthy(RUN)
        (tmp_path / "clock.json").write_text(json.dumps(RUN + 120000))
        wait_until(lambda: not list((tmp_path / "artifacts/staging").iterdir()))
        assert process.poll() is None
    assert mailbox.acknowledged(enabled.revision)
    assert not mailbox.worker_present()


@pytest.mark.parametrize(
    "action",
    ["disable", "selection", "kill", "expiry", "withdraw"],
    ids=["disable", "replacement", "parent-death", "expiry", "withdraw"],
)
def test_no_acknowledged_obsolete_decoder_survives(tmp_path, action):
    mailbox, settings, _enabled = setup(tmp_path)
    with worker_process(tmp_path, "blocked") as process:
        ready = tmp_path / "decoder-ready.json"
        wait_until(ready.exists)
        child = json.loads(ready.read_text())["pid"]
        assert alive(child)
        assert mailbox.worker_present()
        if action == "kill":
            process.kill()
            process.wait(timeout=5)
            wait_until(lambda: not alive(child))
            wait_until(lambda: not mailbox.worker_present())
        elif action in {"expiry", "withdraw"}:
            if action == "expiry":
                (tmp_path / "clock.json").write_text(json.dumps(RUN + 120000))
            else:
                owner = next(
                    iter(
                        json.loads((mailbox.root / "demand.json").read_text())["owners"]
                    )
                )
                mailbox.withdraw(owner)
            wait_until(lambda: not alive(child))
            wait_until(lambda: not list((tmp_path / "artifacts/staging").iterdir()))
        else:
            changed = settings.update(
                {"winds": False, "temperature": False}
                if action == "disable"
                else {"gfs_selection": {"pressure_pa": 30000, "horizon_hours": 3}}
            )
            mailbox.invalidate(changed.revision)
            assert not mailbox.acknowledged(changed.revision)
            wait_until(lambda: mailbox.acknowledged(changed.revision))
            assert not alive(child)
            assert not list((tmp_path / "artifacts/staging").iterdir())
        assert not (tmp_path / "artifacts/current.json").exists()
    assert not mailbox.worker_present()
    if action == "kill":
        with worker_process(tmp_path, "normal"):
            wait_until((tmp_path / "artifacts/current.json").exists)
            assert not list((tmp_path / "artifacts/staging").iterdir())


async def test_aclose_waits_for_worker_lock_and_child_release(tmp_path):
    import asyncio

    from app.services.aviation_weather.gfs.store import GfsProductStore
    from app.services.aviation_weather.gfs.worker import GfsWorker

    from tests.fixtures.gfs_worker_process import FixtureTransport

    mailbox, settings, _enabled = setup(tmp_path)
    store = GfsProductStore(
        tmp_path / "artifacts",
        mailbox.root,
        settings,
        clock=lambda: RUN / 1000,
        require_demand=True,
    )
    ready = tmp_path / "decoder-ready.json"
    command = [
        sys.executable,
        str(Path(__file__).parents[1] / "fixtures/gfs_blocked_decoder.py"),
        str(ready),
    ]
    worker = GfsWorker(
        mailbox,
        store,
        FixtureTransport(),
        clock=lambda: RUN / 1000,
        decoder_command=command,
    )
    running = asyncio.create_task(worker.run())
    try:
        async with asyncio.timeout(5):
            while not ready.exists():
                await asyncio.sleep(0.02)
        child = json.loads(ready.read_text())["pid"]
        async with asyncio.timeout(15):
            await worker.aclose()
        assert not alive(child)
        assert not mailbox.worker_present()
        assert not list((tmp_path / "artifacts/staging").iterdir())
    finally:
        worker.stop()
        async with asyncio.timeout(15):
            await running


async def test_scientific_deadline_reaps_child_and_removes_stage(tmp_path, monkeypatch):
    import asyncio

    import app.services.aviation_weather.gfs.worker as module
    from app.services.aviation_weather.gfs.store import GfsProductStore

    from tests.fixtures.gfs_worker_process import FixtureTransport

    monkeypatch.setattr(module, "DECODE_SECONDS", 0.5)
    mailbox, settings, _enabled = setup(tmp_path)
    store = GfsProductStore(
        tmp_path / "artifacts",
        mailbox.root,
        settings,
        clock=lambda: RUN / 1000,
        require_demand=True,
    )
    ready = tmp_path / "decoder-ready.json"
    command = [
        sys.executable,
        str(Path(__file__).parents[1] / "fixtures/gfs_blocked_decoder.py"),
        str(ready),
    ]
    worker = module.GfsWorker(
        mailbox,
        store,
        FixtureTransport(),
        clock=lambda: RUN / 1000,
        decoder_command=command,
    )
    running = asyncio.create_task(worker.run())
    try:
        async with asyncio.timeout(5):
            while not ready.exists():
                await asyncio.sleep(0.02)
            child = json.loads(ready.read_text())["pid"]
            while alive(child) or list((tmp_path / "artifacts/staging").iterdir()):
                await asyncio.sleep(0.02)
        assert not (tmp_path / "artifacts/current.json").exists()
        assert mailbox.healthy(RUN)
    finally:
        async with asyncio.timeout(15):
            await worker.aclose()
            await running


async def test_second_worker_refuses_ownership_and_closes_its_transport(tmp_path):
    from app.services.aviation_weather.gfs.store import GfsProductStore
    from app.services.aviation_weather.gfs.worker import GfsWorker

    from tests.fixtures.gfs_worker_process import FixtureTransport
    from tests.unit.test_gfs_ipc import other_owner

    class OwnedTransport(FixtureTransport):
        closed = False

        async def aclose(self):
            self.closed = True

    mailbox, settings, _enabled = setup(tmp_path)
    store = GfsProductStore(tmp_path / "artifacts", mailbox.root, settings)
    transport = OwnedTransport()
    worker = GfsWorker(mailbox, store, transport)
    with other_owner(mailbox.root / "worker.lock"):
        with pytest.raises(RuntimeError):
            await worker.run()
        assert transport.closed
        assert mailbox.worker_present()
