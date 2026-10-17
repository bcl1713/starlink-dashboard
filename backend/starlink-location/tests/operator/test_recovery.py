"""Recovery refuses semantic corruption and excludes active access."""

import json
import os
import signal
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from app.operator.errors import OperatorError
from app.operator.store import OperatorStore
from tests.operator.process_helpers import stopped_worker
from tests.operator.service_helpers import create


@pytest.mark.parametrize("damage", ["payload", "json", "links", "database"])
def test_explicit_corruption_failure(service, record_data, damage, clock):
    from app.operator.recovery import verify_store

    first = create(service, record_data)
    second = create(service, record_data)
    path = service.store.settings.database_path
    if damage == "database":
        path.write_bytes(b"truncated database")
    else:
        with sqlite3.connect(path) as db:
            if damage in ("payload", "json"):
                db.execute("DROP TRIGGER revisions_no_update")
                db.execute("PRAGMA ignore_check_constraints=ON")
                db.execute(
                    "UPDATE revisions SET payload_json=?",
                    ("{}" if damage == "payload" else "{broken",),
                )
            else:
                db.execute(
                    "INSERT INTO current_links VALUES (?, 'invented', ?)",
                    (str(first.record_id), str(second.record_id)),
                )
    assert not verify_store(service.store).ready
    assert service.store.health().error_code == "store_corrupt"
    with pytest.raises(OperatorError):
        OperatorStore.open(service.store.settings, initialize=False, clock=clock)


def test_maintenance_excludes_active_transactions(service, tmp_path, clock):
    from app.operator.backup import backup_store
    from app.operator.maintenance import admission
    from app.operator.recovery import restore_store

    manifest = backup_store(service.store, directory=tmp_path / "backups")
    with service.store.connect():
        with pytest.raises(OperatorError) as error:
            restore_store(service.store.settings, manifest=manifest, clock=clock)
        assert error.value.code == "store_busy" and error.value.retryable
    with admission(service.store.settings, exclusive=True):
        with pytest.raises(OperatorError) as error, service.store.connect():
            pytest.fail("Maintenance must prevent admission")
        assert error.value.code == "store_busy"


@pytest.mark.parametrize(
    "barrier",
    [
        "INSERT INTO revisions",
        "UPDATE records",
        "DELETE FROM current_links",
        "INSERT INTO current_links",
        "INSERT INTO commands",
        "before_commit",
        "after_commit",
    ],
)
def test_killed_writer_atomicity(service, record_data, tmp_path, clock, barrier):
    from app.operator.models import CommandReceipt
    from app.operator.recovery import verify_store
    from tests.operator.service_helpers import submit, update

    conference = create(
        service,
        record_data,
        record_type="conference",
        payload={"entry_type": "conference", "title": "Conference"},
    )
    original = create(
        service,
        record_data,
        record_type="call",
        payload={
            "entry_type": "call",
            "title": "Before",
            "conference_id": str(conference.record_id),
        },
    )
    command = update(
        service,
        original,
        payload=original.payload.model_copy(update={"title": "After"}),
    )
    key = str(uuid4())
    config = {
        "mode": "write",
        "barrier": barrier,
        "root": str(service.store.settings.root),
        "missions": str(tmp_path / "missions"),
        "key": key,
        "epoch": str(service.store.health().api_epoch),
        "command": command.model_dump(mode="json"),
    }
    with stopped_worker(tmp_path, config) as (worker, event):
        os.killpg(worker.pid, signal.SIGKILL)
        assert worker.wait(timeout=5) == -signal.SIGKILL
        if barrier == "after_commit":
            assert (
                Path(str(service.store.settings.database_path) + "-wal").stat().st_size
                > 0
            )
        service.store.close()
        service.store = OperatorStore.open(
            service.store.settings, initialize=False, clock=clock
        )
        assert verify_store(service.store).ready
        saved = service.get(str(original.record_id))
        assert saved.version == (2 if barrier == "after_commit" else 1)
        receipt = submit(service, command, key=key)
        assert submit(service, command, key=key) == receipt
        if barrier == "after_commit":
            assert receipt == CommandReceipt.model_validate(event["receipt"])
        assert service.get(str(original.record_id)).payload.title == "After"
        with service.store.connect() as db:
            assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 3
            assert db.execute("SELECT count(*) FROM commands").fetchone()[0] == 3


@pytest.mark.parametrize("write", [False, True])
def test_cross_process_restore_exclusion(service, tmp_path, clock, write):
    from app.operator.backup import backup_store
    from app.operator.recovery import restore_store

    manifest = backup_store(service.store, directory=tmp_path / "backups")
    config = {"mode": "hold", "write": write, "root": str(service.store.settings.root)}
    with stopped_worker(tmp_path, config):
        with pytest.raises(OperatorError) as error:
            restore_store(service.store.settings, manifest=manifest, clock=clock)
        assert error.value.code == "store_busy"
    assert restore_store(service.store.settings, manifest=manifest, clock=clock).ready


@pytest.mark.parametrize("barrier", ["migration", "marker"])
def test_interrupted_initialization_fails_closed(tmp_path, clock, barrier):
    from app.operator.settings import OperatorSettings

    settings = OperatorSettings(enabled=True, root=tmp_path / "store")
    config = {"mode": "initialize", "barrier": barrier, "root": str(settings.root)}
    with stopped_worker(tmp_path, config) as (worker, _):
        os.killpg(worker.pid, signal.SIGKILL)
        worker.wait(timeout=5)
    assert json.loads(settings.identity_path.read_text())["status"] == "initializing"
    with sqlite3.connect(settings.database_path) as db:
        count = db.execute(
            "SELECT count(*) FROM sqlite_master WHERE name='schema_migrations'"
        ).fetchone()[0]
        assert count == (0 if barrier == "migration" else 1)
    before = settings.database_path.read_bytes()
    with pytest.raises(OperatorError, match="store_recovery_required"):
        OperatorStore.open(settings, initialize=True, clock=clock)
    assert settings.database_path.read_bytes() == before


def test_passive_checkpoint_keeps_pinned_reader(service, record_data):
    from app.operator.maintenance import passive_checkpoint

    with service.store.connect() as reader:
        reader.execute("SELECT count(*) FROM revisions").fetchone()
        create(service, record_data)
        busy, pages, checkpointed = passive_checkpoint(service.store)
        assert busy == 0 and pages > checkpointed
        assert reader.execute("SELECT count(*) FROM revisions").fetchone()[0] == 0
        assert (
            Path(str(service.store.settings.database_path) + "-wal").stat().st_size > 0
        )


@pytest.mark.parametrize("damage", ["truncate", "header", "frame"])
def test_damaged_wal_never_loses_acknowledged_command(
    service, record_data, tmp_path, clock, damage
):
    from app.operator.backup import backup_store
    from app.operator.recovery import restore_store, verify_store
    from tests.operator.service_helpers import update

    original = create(service, record_data)
    manifest = backup_store(service.store, directory=tmp_path / "backups")
    command = update(
        service,
        original,
        payload=original.payload.model_copy(update={"title": "After"}),
    )
    config = {
        "mode": "write",
        "barrier": "after_ack",
        "root": str(service.store.settings.root),
        "missions": str(tmp_path / "missions"),
        "key": str(uuid4()),
        "epoch": str(service.store.health().api_epoch),
        "command": command.model_dump(mode="json"),
    }
    with stopped_worker(tmp_path, config) as (worker, _):
        os.killpg(worker.pid, signal.SIGKILL)
        worker.wait(timeout=5)
    wal = Path(str(service.store.settings.database_path) + "-wal")
    data = wal.read_bytes()
    damaged = {
        "truncate": data[:40],
        "header": b"broken!!" + data[8:],
        "frame": data[:56] + bytes([data[56] ^ 1]) + data[57:],
    }[damage]
    wal.write_bytes(damaged)
    service.store.close()
    try:
        recovered = OperatorStore.open(
            service.store.settings, initialize=False, clock=clock
        )
    except OperatorError as error:
        assert not error.retryable
        assert wal.read_bytes() == damaged
        assert restore_store(
            service.store.settings, manifest=manifest, clock=clock
        ).ready
        preserved = next(service.store.settings.root.glob("preserved-*"))
        assert (preserved / wal.name).read_bytes() == damaged
        return
    try:
        assert verify_store(recovered).ready
        with recovered.connect() as db:
            assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 2
            assert db.execute("SELECT count(*) FROM commands").fetchone()[0] == 2
            assert db.execute("SELECT current_version FROM records").fetchone()[0] == 2
    finally:
        recovered.close()


def test_checkpoint_reused_wal_preserves_acknowledged_commands(
    service, record_data, tmp_path, clock
):
    from tests.operator.service_helpers import update

    original = create(service, record_data)
    command = update(service, original)
    config = {
        "mode": "reuse",
        "barrier": "after_ack",
        "root": str(service.store.settings.root),
        "missions": str(tmp_path / "missions"),
        "key": str(uuid4()),
        "epoch": str(service.store.health().api_epoch),
        "command": command.model_dump(mode="json"),
    }
    with stopped_worker(tmp_path, config) as (worker, event):
        os.killpg(worker.pid, signal.SIGKILL)
        worker.wait(timeout=5)
    data = Path(str(service.store.settings.database_path) + "-wal").read_bytes()
    page_size = int.from_bytes(data[8:12], "big")
    # Fixture must actually retain old-salt frames, rather than silently testing
    # a fresh WAL. SQLite's restart leaves these beyond the new valid prefix.
    assert any(
        data[offset + 8 : offset + 16] != data[16:24]
        for offset in range(32, len(data), 24 + page_size)
    )
    service.store.close()
    recovered = OperatorStore.open(
        service.store.settings, initialize=False, clock=clock
    )
    try:
        with recovered.connect() as db:
            assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 6
            actual = {row[0] for row in db.execute("SELECT command_id FROM commands")}
            assert actual == {
                str(original.command_id),
                event["receipt"]["command_id"],
                *event["acknowledged"],
            }
    finally:
        recovered.close()
