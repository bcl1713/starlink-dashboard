"""Stdlib failure probes in disposable production-image stores, never the demo DB."""

import errno
import json
import os
import select
import signal
import sqlite3
import time
from pathlib import Path
from uuid import uuid4

from app.mission import storage
from app.operator.backup import backup_store
from app.operator.errors import OperatorError
from app.operator.models import Actor, CreateRecord
from app.operator.recovery import restore_store, verify_store
from app.operator.references import MissionReferences
from app.operator.service import OperatorService
from app.operator.settings import OperatorSettings
from app.operator.store import OperatorStore
from scenario import ScenarioClock, make_demo
from seed import seed_demo

ROOT = Path("/failure")
CLOCK = ScenarioClock()


def open_service(root):
    manifest = seed_demo(root, clock=CLOCK, mode="simulation")
    storage.MISSIONS_DIR = root / "missions"
    settings = OperatorSettings(
        enabled=True,
        root=root / "operator",
        source_mode="simulation",
        simulation_run_id=manifest["run_id"],
    )
    store = OperatorStore.open(settings, initialize=False, clock=CLOCK)
    return OperatorService(
        store, clock=CLOCK, actor=Actor(), references=MissionReferences()
    )


def counts(service):
    with sqlite3.connect(service.store.settings.database_path) as db:
        return [
            db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("records", "revisions", "commands")
        ]


def command():
    original = make_demo(CLOCK)["commands"][0].model_dump(mode="json")
    original["payload"]["title"] = "Synthetic failure probe"
    return CreateRecord.model_validate(original)


def execute(service, key=None, epoch=None):
    return service.execute(
        command(),
        key=key or str(uuid4()),
        epoch=epoch or str(service.store.health().api_epoch),
    )


def crash(barrier):
    root = ROOT / barrier
    service = open_service(root)
    key, epoch = str(uuid4()), str(service.store.health().api_epoch)
    read_fd, write_fd = os.pipe()
    owner = root / "child-owner.json"
    owner.write_text(json.dumps({"intent": "fork crash barrier", "barrier": barrier}))
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        real = service.store._connection

        class Connection:
            def __init__(self):
                self.db = real()

            def __getattr__(self, name):
                return getattr(self.db, name)

            def commit(self):
                if self.db.total_changes and barrier == "before_commit":
                    os.write(write_fd, b"ready")
                    signal.pause()
                self.db.commit()
                if self.db.total_changes and barrier == "after_commit":
                    os.write(write_fd, b"ready")
                    signal.pause()

        service.store._connection = Connection
        execute(service, key, epoch)
        os._exit(2)
    os.close(write_fd)
    owner.write_text(json.dumps({"pid": pid, "pgid": os.getpgrp(), "barrier": barrier}))
    try:
        assert select.select([read_fd], [], [], 10)[0], "Worker missed barrier"
        assert os.read(read_fd, 5) == b"ready"
    finally:
        os.kill(pid, signal.SIGKILL)
        deadline = time.monotonic() + 10
        while os.waitpid(pid, os.WNOHANG)[0] == 0:
            assert time.monotonic() < deadline, "Worker was not reaped"
            time.sleep(0.01)
        os.close(read_fd)
    wal = Path(str(service.store.settings.database_path) + "-wal")
    wal_bytes = wal.stat().st_size if wal.exists() else 0
    service.store.close()
    service.store = OperatorStore.open(
        service.store.settings, initialize=False, clock=CLOCK
    )
    assert verify_store(service.store).ready
    expected = 7 if barrier == "after_commit" else 6
    assert counts(service) == [expected] * 3
    receipt = execute(service, key, epoch)
    assert execute(service, key, epoch) == receipt
    assert counts(service) == [7] * 3
    service.store.close()
    return {
        "barrier": barrier,
        "beforeRetryCounts": [expected] * 3,
        "afterRetryCounts": [7] * 3,
        "walBytes": wal_bytes,
        "childReaped": True,
    }


def media_failure(kind):
    service = open_service(ROOT / kind)
    before = counts(service)
    directory = service.store.settings.database_path.parent
    filler = ROOT / "fill-volume"
    if kind == "full":
        try:
            with filler.open("wb", buffering=0) as output:
                while True:
                    output.write(b"x" * 65536)
        except OSError as error:
            assert error.errno == errno.ENOSPC
        assert os.statvfs(ROOT).f_bavail == 0
    else:
        for path in directory.iterdir():
            path.chmod(0o400)
        directory.chmod(0o500)
    code = None
    try:
        try:
            execute(service)
        except OperatorError as error:
            code = error.code
        assert code in ("store_unavailable", "commit_outcome_unknown")
        assert not service.store.health().ready
    finally:
        if kind == "full":
            filler.unlink()
        else:
            directory.chmod(0o700)
            for path in directory.iterdir():
                path.chmod(0o600)
    assert counts(service) == before
    service.store.close()
    recovered = OperatorStore.open(
        service.store.settings, initialize=False, clock=CLOCK
    )
    assert verify_store(recovered).ready
    recovered.close()
    return {
        "physicalFailure": kind,
        "error": code,
        "countsUnchanged": before,
        "reopenReady": True,
        "filesystem": "private 4 MiB tmpfs",
    }


def recovery():
    service = open_service(ROOT / "restore")
    epoch = str(service.store.health().api_epoch)
    manifest = backup_store(service.store, directory=ROOT / "backups")
    execute(service)
    assert counts(service) == [7] * 3
    restored = restore_store(service.store.settings, manifest=manifest, clock=CLOCK)
    assert restored.ready and str(restored.api_epoch) != epoch
    try:
        execute(service, epoch=epoch)
        raise AssertionError("Old epoch accepted")
    except OperatorError as error:
        assert error.code == "store_epoch_changed"
    assert counts(service) == [6] * 3
    service.store.close()
    failures = {}
    for damage in ("missing", "schema"):
        broken = open_service(ROOT / damage)
        settings = broken.store.settings
        broken.store.close()
        if damage == "missing":
            settings.database_path.unlink()
        else:
            with sqlite3.connect(settings.database_path) as db:
                db.execute("UPDATE schema_migrations SET version=99")
        try:
            OperatorStore.open(settings, initialize=False, clock=CLOCK)
            raise AssertionError("Broken store was opened")
        except OperatorError as error:
            failures[damage] = error.code
        if damage == "missing":
            assert not settings.database_path.exists()
    return {
        "backupH": 6,
        "preRestoreH": 7,
        "restoredH": 6,
        "epochRotated": True,
        "oldEpochRejected": True,
        "failClosed": failures,
    }


if __name__ == "__main__":
    result = {
        "crashes": [crash(b) for b in ("before_commit", "after_commit")],
        "recovery": recovery(),
        "media": [media_failure(k) for k in ("read-only", "full")],
    }
    print(json.dumps(result))
