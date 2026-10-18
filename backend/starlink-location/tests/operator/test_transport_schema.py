"""Schema 003 preserves immutable data and rolls back failed migrations."""

import hashlib
import sqlite3
import pytest
from app.operator import schema
from app.operator.errors import OperatorError
from app.operator.schema import apply_migrations
from app.operator.settings import OperatorSettings
from app.operator.store import OperatorStore
from app.operator.upgrade import upgrade_store
from app.operator.backup import validated_backup
from tests.operator.service_helpers import create


def test_new_schema_contains_transport_type(service):
    with service.store.connect() as db:
        assert (
            db.execute("SELECT max(version) FROM schema_migrations").fetchone()[0] == 3
        )
        assert (
            "transport_decision"
            in db.execute(
                "SELECT sql FROM sqlite_master WHERE name='revisions'"
            ).fetchone()[0]
        )


def test_populated_upgrade_preserves_records_and_guards(
    tmp_path, clock, monkeypatch, record_data
):
    from app.operator.models import Actor
    from app.operator.references import MissionReferences
    from app.operator.service import OperatorService
    from app.mission import storage
    from tests.operator.service_helpers import save_mission

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    save_mission("demo-mission")
    settings = OperatorSettings(enabled=True, root=tmp_path / "store")
    with monkeypatch.context() as patch:
        patch.setattr(schema, "MIGRATIONS", schema.MIGRATIONS[:2])
        store = OperatorStore.open(settings, initialize=True, clock=clock)
        service = OperatorService(
            store, clock=clock, actor=Actor(), references=MissionReferences()
        )
        saved = create(service, record_data)
        with store.connect() as db:
            rows = db.execute("SELECT * FROM revisions").fetchall()
            receipts = db.execute("SELECT * FROM commands").fetchall()
        store.close()
    with pytest.raises(OperatorError, match="schema_upgrade_required"):
        OperatorStore.open(settings, initialize=False, clock=clock)
    manifest = upgrade_store(settings, clock=clock)
    info, _ = validated_backup(manifest, clock=clock)
    assert info["schema_version"] == 2
    reopened = OperatorStore.open(settings, initialize=False, clock=clock)
    try:
        with reopened.connect() as db:
            assert db.execute("SELECT * FROM revisions").fetchall() == rows
            assert db.execute("SELECT * FROM commands").fetchall() == receipts
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []
            assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            assert (
                db.execute(
                    "SELECT seq FROM sqlite_sequence WHERE name='revisions'"
                ).fetchone()[0]
                >= saved.journal_seq
            )
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                db.execute("DELETE FROM revisions")
        with monkeypatch.context() as patch:
            patch.setattr(schema, "MIGRATIONS", schema.MIGRATIONS[:2])
            with pytest.raises(OperatorError, match="unsupported_schema"):
                OperatorStore.open(settings, initialize=False, clock=clock)
    finally:
        reopened.close()


def test_failed_rebuild_rolls_back(clock, monkeypatch):
    with sqlite3.connect(":memory:") as db:
        for i, migration in enumerate(schema.MIGRATIONS[:2], 1):
            db.executescript(migration.read_text())
            db.execute(
                "INSERT INTO schema_migrations VALUES (?,?,?)",
                (
                    i,
                    hashlib.sha256(migration.read_bytes()).hexdigest(),
                    clock.now().isoformat(),
                ),
            )
        db.commit()
        original = schema.migration_sql
        monkeypatch.setattr(
            schema,
            "migration_sql",
            lambda version: original(version)
            + ("\nINVALID SQL;\n" if version == 3 else ""),
        )
        with pytest.raises(sqlite3.Error):
            apply_migrations(db, clock=clock, upgrade=True)
        assert (
            db.execute("SELECT max(version) FROM schema_migrations").fetchone()[0] == 2
        )
        assert (
            "transport_decision"
            not in db.execute(
                "SELECT sql FROM sqlite_master WHERE name='revisions'"
            ).fetchone()[0]
        )
