"""Schema 003 preserves immutable data and rolls back failed migrations."""

import hashlib
import sqlite3

import pytest

from app.operator import schema
from app.operator.backup import validated_backup
from app.operator.errors import OperatorError
from app.operator.schema import apply_migrations
from app.operator.settings import OperatorSettings
from app.operator.store import OperatorStore
from app.operator.upgrade import upgrade_store
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
    from datetime import timedelta
    from uuid import uuid4

    from app.mission import storage
    from app.operator.event_ack import acknowledge
    from app.operator.event_feed import build_snapshot
    from app.operator.event_models import AckRequest
    from app.operator.event_sources import EventSourceAdapter
    from app.operator.models import Actor
    from app.operator.references import MissionReferences
    from app.operator.runtime import OperatorRuntime
    from app.operator.service import OperatorService
    from tests.operator.service_helpers import save_mission, submit, update

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
        saved = submit(
            service,
            update(
                service,
                saved,
                payload={"entry_type": "note", "title": "Old revision chain"},
            ),
        ).saved_records[0]
        conference = create(
            service,
            record_data,
            record_type="conference",
            payload={"entry_type": "conference", "title": "Old conference"},
        )
        create(
            service,
            record_data,
            record_type="call",
            time={"planned_start_at": clock.now() + timedelta(minutes=2)},
            payload={
                "entry_type": "call",
                "title": "Old requirement",
                "conference_id": str(conference.record_id),
            },
        )
        runtime = OperatorRuntime(settings, clock)
        runtime.service = service
        adapter = EventSourceAdapter(service)
        snapshot = build_snapshot(runtime, "demo-mission", adapter)
        event = next(e for e in snapshot.events if e.kind == "call_start")
        acknowledge(
            AckRequest(
                occurrence_id=event.notification.generation,
                severity_generation=event.notification.severity_generation,
                snapshot_token=snapshot.snapshot_token,
            ),
            key=str(uuid4()),
            epoch=str(store.health().api_epoch),
            runtime=runtime,
            adapter=adapter,
        )
        with store.connect(write=True) as db:
            db.execute("UPDATE sqlite_sequence SET seq=10000 WHERE name='revisions'")
        event_tables = [
            "event_occurrences",
            "event_heads",
            "event_transitions",
            "event_acknowledgments",
            "event_tiers",
            "current_links",
        ]
        with store.connect() as db:
            preserved = {
                table: db.execute("SELECT * FROM " + table).fetchall()
                for table in event_tables
            }
            assert len(preserved["event_acknowledgments"]) == 1
            assert len(preserved["current_links"]) == 1
            rows = db.execute("SELECT * FROM revisions").fetchall()
            receipts = db.execute("SELECT * FROM commands").fetchall()
        runtime.close()
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
            assert {
                table: db.execute("SELECT * FROM " + table).fetchall()
                for table in event_tables
            } == preserved
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []
            assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            assert (
                db.execute(
                    "SELECT seq FROM sqlite_sequence WHERE name='revisions'"
                ).fetchone()[0]
                == 10000
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
