"""Notification migrations never silently upgrade an existing Operator store."""

import hashlib
import sqlite3

import pytest

from app.operator.errors import OperatorError
from app.operator.schema import MIGRATION, apply_migrations


def legacy_database(connection, clock):
    connection.executescript(MIGRATION.read_text())
    connection.execute(
        "INSERT INTO schema_migrations VALUES (1, ?, ?)",
        (hashlib.sha256(MIGRATION.read_bytes()).hexdigest(), clock.now().isoformat()),
    )
    connection.commit()


def test_new_store_contains_notification_constraints(clock):
    with sqlite3.connect(":memory:") as db:
        apply_migrations(db, clock=clock)
        assert db.execute("SELECT version FROM schema_migrations").fetchall() == [
            (1,),
            (2,),
        ]
        assert db.execute("SELECT count(*) FROM event_acknowledgments").fetchone() == (
            0,
        )


def test_existing_store_requires_explicit_upgrade(clock):
    with sqlite3.connect(":memory:") as db:
        legacy_database(db, clock)
        with pytest.raises(OperatorError, match="schema_upgrade_required"):
            apply_migrations(db, clock=clock)
        assert db.execute("SELECT version FROM schema_migrations").fetchall() == [(1,)]
        apply_migrations(db, clock=clock, upgrade=True)
        apply_migrations(db, clock=clock)
        assert db.execute("SELECT version FROM schema_migrations").fetchall() == [
            (1,),
            (2,),
        ]


def test_failed_upgrade_rolls_back_every_statement(clock, monkeypatch):
    from app.operator import schema

    with sqlite3.connect(":memory:") as db:
        legacy_database(db, clock)
        monkeypatch.setattr(
            schema,
            "migration_sql",
            lambda version: (
                MIGRATION.read_text()
                if version == 1
                else "CREATE TABLE incomplete (id TEXT);\nINVALID SQL;\n"
            ),
        )
        with pytest.raises(sqlite3.Error):
            apply_migrations(db, clock=clock, upgrade=True)
        assert db.execute("SELECT version FROM schema_migrations").fetchall() == [(1,)]
        assert (
            db.execute(
                "SELECT name FROM sqlite_master WHERE name='incomplete'"
            ).fetchall()
            == []
        )


def test_upgrade_backs_up_legacy_and_preserves_identity(tmp_path, clock, monkeypatch):
    from app.operator import schema
    from app.operator.backup import validated_backup
    from app.operator.settings import OperatorSettings
    from app.operator.store import OperatorStore
    from app.operator.upgrade import upgrade_store

    settings = OperatorSettings(enabled=True, root=tmp_path / "store")
    with monkeypatch.context() as patch:
        patch.setattr(schema, "MIGRATIONS", (MIGRATION,))
        legacy = OperatorStore.open(settings, initialize=True, clock=clock)
        identity = legacy.health().store_id
        legacy.close()
    with pytest.raises(OperatorError, match="schema_upgrade_required"):
        OperatorStore.open(settings, initialize=False, clock=clock)
    manifest = upgrade_store(settings, clock=clock)
    info, _ = validated_backup(manifest, clock=clock)
    assert info["schema_version"] == 1
    upgraded = OperatorStore.open(settings, initialize=False, clock=clock)
    try:
        assert upgraded.health().store_id == identity
        with upgraded.connect() as db:
            assert db.execute(
                "SELECT count(*) FROM event_acknowledgments"
            ).fetchone() == (0,)
    finally:
        upgraded.close()
