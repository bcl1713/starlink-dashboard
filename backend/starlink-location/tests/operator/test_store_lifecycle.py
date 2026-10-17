"""Durable identity, fail-closed startup, and connection ownership."""

import json
import sqlite3
import stat
from dataclasses import replace

import pytest

from app.operator.errors import OperatorError
from app.operator.schema import apply_migrations
from app.operator.settings import OperatorSettings
from app.operator.store import OperatorStore


def test_explicit_initialization_and_mode(tmp_path, clock):
    settings = OperatorSettings(enabled=True, root=tmp_path / "private")
    with pytest.raises(OperatorError):
        OperatorStore.open(settings, initialize=False, clock=clock)
    assert not settings.database_path.exists()
    store = OperatorStore.open(settings, initialize=True, clock=clock)
    identity = store.health()
    try:
        assert identity.ready
        assert identity.store_id and identity.api_epoch
        with store.connect() as db:
            for name, expected in (
                ("journal_mode", "wal"),
                ("synchronous", 2),
                ("foreign_keys", 1),
                ("wal_autocheckpoint", 1000),
                ("busy_timeout", 2000),
            ):
                assert db.execute(f"PRAGMA {name}").fetchone()[0] == expected
            with store.connect() as other:
                assert db is not other
                assert other.execute("SELECT count(*) FROM records").fetchone()[0] == 0
        assert stat.S_IMODE(settings.database_path.stat().st_mode) == 0o600
        assert stat.S_IMODE(settings.database_path.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(settings.identity_path.stat().st_mode) == 0o600
    finally:
        store.close()
    reopened = OperatorStore.open(settings, initialize=False, clock=clock)
    assert reopened.health().store_id == identity.store_id
    assert reopened.health().api_epoch == identity.api_epoch
    reopened.close()
    assert not reopened.health().ready
    with pytest.raises(OperatorError), reopened.connect():
        pass
    settings.database_path.unlink()
    for initialize in (False, True):
        with pytest.raises(OperatorError):
            OperatorStore.open(settings, initialize=initialize, clock=clock)
    assert not settings.database_path.exists()


def test_simulation_identity_is_persisted_and_checked(tmp_path, clock):
    settings = OperatorSettings(
        enabled=True,
        root=tmp_path,
        source_mode="simulation",
        simulation_run_id="run-one",
    )
    store = OperatorStore.open(settings, initialize=True, clock=clock)
    assert store.health().simulation_run_id == "run-one"
    assert store.health().source_mode == "simulation"
    store.close()
    assert (
        settings.database_path
        != replace(settings, simulation_run_id="run-two").database_path
    )
    # A relocated/tampered store must not be opened under a different identity.
    with sqlite3.connect(settings.database_path) as db:
        db.execute("UPDATE store_metadata SET simulation_run_id='run-two'")
    with pytest.raises(OperatorError):
        OperatorStore.open(settings, initialize=False, clock=clock)


@pytest.mark.parametrize(
    "damage",
    ["checksum", "version", "marker", "pointer", "database-only", "empty-database"],
)
def test_damaged_store_fails_closed(tmp_path, clock, damage):
    settings = OperatorSettings(enabled=True, root=tmp_path)
    store = OperatorStore.open(settings, initialize=True, clock=clock)
    store.close()
    if damage == "marker":
        settings.identity_path.write_text(json.dumps({"status": "initializing"}))
    elif damage == "database-only":
        settings.identity_path.unlink()
    elif damage == "empty-database":
        settings.database_path.write_bytes(b"")
    else:
        with sqlite3.connect(settings.database_path) as db:
            if damage == "checksum":
                db.execute("UPDATE schema_migrations SET checksum='bad'")
            elif damage == "version":
                db.execute("INSERT INTO schema_migrations VALUES (999, 'new', 'now')")
            else:
                db.execute("INSERT INTO records VALUES ('missing', 1)")
    before = settings.database_path.read_bytes()
    with pytest.raises(OperatorError):
        OperatorStore.open(settings, initialize=True, clock=clock)
    assert settings.database_path.read_bytes() == before


def test_connections_pin_read_snapshots(tmp_path, clock):
    store = OperatorStore.open(
        OperatorSettings(enabled=True, root=tmp_path), initialize=True, clock=clock
    )
    try:
        with store.connect() as reader:
            assert reader.execute("SELECT count(*) FROM commands").fetchone()[0] == 0
            with store.connect() as writer:
                writer.execute(
                    "INSERT INTO commands VALUES ('x','x','x',1,'now',200,'{}')"
                )
            assert reader.execute("SELECT count(*) FROM commands").fetchone()[0] == 0
        with store.connect() as reader:
            assert reader.execute("SELECT count(*) FROM commands").fetchone()[0] == 1
    finally:
        store.close()


def test_writer_admission_is_bounded_and_readers_remain_available(tmp_path, clock):
    store = OperatorStore.open(
        OperatorSettings(enabled=True, root=tmp_path), initialize=True, clock=clock
    )
    try:
        with store.connect(write=True) as writer:
            with store.connect() as reader:
                assert reader.execute("SELECT count(*) FROM records").fetchone()[0] == 0
            with pytest.raises(OperatorError, match="store_busy"), store.connect(
                write=True
            ):
                pytest.fail("A second writer cannot enter before admission")
            writer.execute("INSERT INTO commands VALUES ('x','x','x',1,'now',200,'{}')")
    finally:
        store.close()


def test_simulation_directories_are_private(tmp_path, clock):
    settings = OperatorSettings(
        enabled=True,
        root=tmp_path / "operator",
        source_mode="simulation",
        simulation_run_id="run",
    )
    store = OperatorStore.open(settings, initialize=True, clock=clock)
    store.close()
    for path in (
        settings.root,
        settings.root / "simulation",
        settings.database_path.parent,
    ):
        assert stat.S_IMODE(path.stat().st_mode) == 0o700


def test_clock_rollback_is_visible_without_rewriting_revisions(tmp_path, clock):
    from test_schema import insert_receipt, insert_revision

    store = OperatorStore.open(
        OperatorSettings(enabled=True, root=tmp_path), initialize=True, clock=clock
    )
    try:
        with store.connect() as db:
            insert_revision(db)
            db.execute("INSERT INTO records VALUES ('record', 1)")
            insert_receipt(db)
        clock.advance(-60)
        assert store.health().clock_regression
        with store.connect() as db:
            assert (
                db.execute("SELECT recorded_at FROM revisions").fetchone()[0]
                == "2026-10-17T16:00:00.000000Z"
            )
    finally:
        store.close()


def test_connection_transaction_commit_rollback_and_busy(tmp_path, clock):
    store = OperatorStore.open(
        OperatorSettings(enabled=True, root=tmp_path), initialize=True, clock=clock
    )
    try:
        with pytest.raises(RuntimeError), store.connect() as db:
            db.execute("INSERT INTO commands VALUES ('x','x','x',1,'now',200,'{}')")
            raise RuntimeError("abort")
        with store.connect() as first, store.connect() as second:
            assert first.execute("SELECT count(*) FROM commands").fetchone()[0] == 0
            first.execute("INSERT INTO commands VALUES ('x','x','x',1,'now',200,'{}')")
            assert second.execute("SELECT count(*) FROM commands").fetchone()[0] == 0
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                second.execute(
                    "INSERT INTO commands VALUES ('y','y','y',1,'now',200,'{}')"
                )
        with pytest.raises(sqlite3.ProgrammingError):
            first.execute("SELECT 1")
        with store.connect() as db:
            assert db.execute("SELECT count(*) FROM commands").fetchone()[0] == 1
    finally:
        store.close()


def test_migrations_are_checksummed_and_idempotent(clock):
    with sqlite3.connect(":memory:") as db:
        apply_migrations(db, clock=clock)
        apply_migrations(db, clock=clock)
        assert db.execute("SELECT version FROM schema_migrations").fetchall() == [(1,)]
        db.execute("UPDATE schema_migrations SET checksum='bad'")
        with pytest.raises(OperatorError):
            apply_migrations(db, clock=clock)


def test_settings_default_disabled_and_isolate_runs(monkeypatch, tmp_path, clock):
    for name in (
        "OPERATOR_ENABLED",
        "OPERATOR_ROOT",
        "OPERATOR_SOURCE_MODE",
        "OPERATOR_SIMULATION_RUN_ID",
        "STARLINK_MODE",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = OperatorSettings.from_env()
    assert not settings.enabled
    assert str(settings.database_path) == "data/operator/operations.sqlite3"
    assert settings.capacity_bytes == 1024**3
    assert settings.backup_count == 3
    store = OperatorStore.open(
        replace(settings, root=tmp_path / "disabled"), initialize=True, clock=clock
    )
    assert not store.health().ready
    assert not (tmp_path / "disabled").exists()
    store.close()
    monkeypatch.setenv("OPERATOR_ENABLED", "true")
    monkeypatch.setenv("OPERATOR_SOURCE_MODE", "simulation")
    monkeypatch.setenv("OPERATOR_SIMULATION_RUN_ID", "../escape")
    with pytest.raises(ValueError):
        OperatorSettings.from_env()
