"""Published SQLite snapshots preserve WAL and restore invalidates old clients."""

import json
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from app.operator.errors import OperatorError
from app.operator.models import CreateRecord
from app.operator.store import OperatorStore
from tests.operator.service_helpers import create, submit


def test_backup_restore_epoch(service, record_data, tmp_path, clock):
    from app.operator.backup import backup_store
    from app.operator.recovery import restore_store, verify_store

    settings = service.store.settings
    old_epoch = str(service.store.health().api_epoch)
    # Keep a connection alive so the committed changes remain in WAL.
    with service.store.connect() as keeper:
        keeper.execute("PRAGMA wal_autocheckpoint=0")
        original = create(service, record_data)
        assert Path(str(settings.database_path) + "-wal").stat().st_size > 0
        manifest = backup_store(service.store, directory=tmp_path / "backups")
    info = json.loads(manifest.read_text())
    assert info["H"] == 1
    assert info["schema_version"] == 2
    assert info["store_id"] == str(service.store.health().store_id)
    later_key = str(uuid4())
    command = CreateRecord.model_validate(record_data)
    submit(service, command, key=later_key)
    health = restore_store(settings, manifest=manifest, clock=clock)
    assert health.ready and str(health.api_epoch) != old_epoch
    assert list(settings.database_path.parent.glob("preserved-*"))
    with pytest.raises(OperatorError) as error:
        service.execute(command, key=later_key, epoch=old_epoch)
    assert error.value.code == "store_epoch_changed"
    reopened = OperatorStore.open(settings, initialize=False, clock=clock)
    try:
        assert verify_store(reopened).ready
        with reopened.connect() as db:
            assert db.execute("SELECT record_id FROM records").fetchall() == [
                (str(original.record_id),)
            ]
        report = json.loads(
            (settings.database_path.parent / "restore-report.json").read_text()
        )
        assert report["restored_H"] == 1
        assert report["previous_H"] == 2
    finally:
        reopened.close()


def test_retention_publishes_before_removal(
    service, record_data, tmp_path, monkeypatch
):
    from app.operator import backup

    directory = tmp_path / "backups"
    for _ in range(4):
        create(service, record_data)
        backup.backup_store(service.store, directory=directory)
    published = sorted(directory.glob("*.json"))
    assert len(published) == 3
    assert sorted(json.loads(path.read_text())["H"] for path in published) == [2, 3, 4]
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    real = backup.os.replace

    def interrupted(source, target):
        if str(target).endswith(".json"):
            raise OSError("interrupted manifest publication")
        return real(source, target)

    monkeypatch.setattr(backup.os, "replace", interrupted)
    with pytest.raises(OperatorError):
        backup.backup_store(service.store, directory=directory)
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == before


def test_restore_rejects_bad_checksum_without_touching_store(service, tmp_path, clock):
    from app.operator.backup import backup_store
    from app.operator.recovery import restore_store

    manifest = backup_store(service.store, directory=tmp_path / "backups")
    info = json.loads(manifest.read_text())
    (manifest.parent / info["database"]).write_bytes(b"damaged")
    before = service.store.settings.database_path.read_bytes()
    with pytest.raises(OperatorError):
        restore_store(service.store.settings, manifest=manifest, clock=clock)
    assert service.store.settings.database_path.read_bytes() == before
    assert service.store.health().ready


def test_backup_blocked_destination_is_bounded(service, tmp_path, monkeypatch):
    import time

    from app.operator import backup

    directory = tmp_path / "backups"
    good = backup.backup_store(service.store, directory=directory)
    saved = good.read_bytes()
    real = sqlite3.connect
    blockers = []

    def blocked(path, *args, **kwargs):
        connection = real(path, *args, **kwargs)
        if str(path).endswith(".pending"):
            blocker = real(path)
            blocker.execute("BEGIN EXCLUSIVE")
            blocker.execute("CREATE TABLE lock_holder (id)")
            blockers.append(blocker)
        return connection

    monkeypatch.setattr(backup.sqlite3, "connect", blocked)
    started = time.monotonic()
    try:
        with pytest.raises(OperatorError, match="maintenance_timeout"):
            backup.backup_store(service.store, directory=directory)
    finally:
        for blocker in blockers:
            blocker.rollback()
            blocker.close()
    assert time.monotonic() - started < 5
    assert good.read_bytes() == saved
    assert len(list(directory.glob("*.json"))) == 1


def test_backup_with_active_writer_uses_committed_snapshot(
    service, record_data, tmp_path
):
    from app.operator import commands
    from app.operator.backup import backup_store
    from app.operator.models import Actor
    from tests.operator.service_helpers import update

    original = create(service, record_data)
    with service.store.connect(write=True) as writer:
        commands.execute_in_transaction(
            writer,
            update(service, original),
            key=str(uuid4()),
            request_hash="pending",
            clock=service.clock,
            actor=Actor(),
        )
        manifest = backup_store(service.store, directory=tmp_path / "backups")
        assert json.loads(manifest.read_text())["H"] == 1


def test_interrupted_restore_preserves_files_and_refuses_ready(
    service, tmp_path, clock, monkeypatch
):
    from app.operator import recovery
    from app.operator.backup import backup_store
    from app.operator.recovery import restore_store

    settings = service.store.settings
    manifest = backup_store(service.store, directory=tmp_path / "backups")
    original = settings.database_path.read_bytes()
    real = recovery.os.replace

    def interrupted(source, target):
        if str(source).endswith(".pending") and target == settings.database_path:
            raise OSError("interrupted replacement")
        return real(source, target)

    monkeypatch.setattr(recovery.os, "replace", interrupted)
    with pytest.raises(OperatorError):
        restore_store(settings, manifest=manifest, clock=clock)
    assert json.loads(settings.identity_path.read_text())["status"] == "restoring"
    preserved = next(settings.root.glob("preserved-*"))
    assert (preserved / "operations.sqlite3").read_bytes() == original
    with pytest.raises(OperatorError):
        OperatorStore.open(settings, initialize=True, clock=clock)


def test_retention_tracks_publication_order_not_uuid_or_high_water(
    service, tmp_path, monkeypatch
):
    from uuid import UUID

    from app.operator import backup

    # All snapshots have the same injected timestamp/H; UUIDs are unordered.
    identifiers = iter(UUID(int=n) for n in (4, 3, 2, 1))
    monkeypatch.setattr(backup, "uuid4", lambda: next(identifiers))
    manifests = [
        backup.backup_store(service.store, directory=tmp_path / "backups")
        for _ in range(4)
    ]
    assert not manifests[0].exists()
    assert all(path.exists() for path in manifests[1:])
