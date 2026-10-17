"""Real SQLite tests for audit and projection integrity."""

import sqlite3

import pytest

from app.operator.settings import OperatorSettings
from app.operator.store import OperatorStore


def insert_revision(
    db,
    *,
    version=1,
    previous=None,
    operation="create",
    reason=None,
    origin=None,
    scope="mission",
    leg_id=None,
):
    db.execute(
        """INSERT INTO revisions
        (record_id, version, previous_version, command_id, operation, reason,
         reason_origin, schema_version, record_type, mission_id, leg_id, scope,
         deleted, recorded_at, author_json, time_json, provenance_json, payload_json)
        VALUES ('record', ?, ?, 'command', ?, ?, ?, 1, 'journal_entry', 'mission',
                ?, ?, 0, '2026-10-17T16:00:00.000000Z', '{}', '{}', '{}', '{}')""",
        (version, previous, operation, reason, origin, leg_id, scope),
    )


def insert_receipt(db):
    db.execute("""INSERT INTO commands VALUES
        ('command', 'key', 'hash', 1, '2026-10-17T16:00:00.000000Z', 201, '{}')""")


def test_revision_and_receipt_immutability(tmp_path, clock):
    store = OperatorStore.open(
        OperatorSettings(enabled=True, root=tmp_path), initialize=True, clock=clock
    )
    try:
        with store.connect() as db:
            insert_revision(db)
            db.execute("INSERT INTO records VALUES ('record', 1)")
            insert_receipt(db)  # Deferred FK permits receipt after its revision.
        for table in ("revisions", "commands", "records"):
            for sql in (
                f"DELETE FROM {table}",
                (
                    f"UPDATE {table} SET record_id='x'"
                    if table != "commands"
                    else "UPDATE commands SET request_hash='x'"
                ),
            ):
                with pytest.raises(sqlite3.IntegrityError):
                    with store.connect() as db:
                        db.execute(sql)
        with store.connect() as db:
            with pytest.raises(sqlite3.IntegrityError):
                insert_revision(
                    db,
                    version=3,
                    previous=1,
                    operation="update",
                    reason="Operator correction",
                    origin="automatic",
                )
            insert_revision(
                db,
                version=2,
                previous=1,
                operation="update",
                reason="Operator correction",
                origin="automatic",
            )
            with pytest.raises(sqlite3.IntegrityError):
                db.execute("UPDATE records SET current_version=3")
            db.execute("UPDATE records SET current_version=2")
            assert db.execute("SELECT version FROM current_records").fetchone()[0] == 2
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        store.close()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"version": 2, "previous": 1, "operation": "update"},
        {"version": 1, "previous": 1},
        {"scope": "leg"},
        {"leg_id": "leg"},
        {"reason": "reason"},
        {"reason": " " * 3, "origin": "operator"},
        {"reason": "x" * 1001, "origin": "operator"},
        {"reason": " " + "x" * 1000, "origin": "operator"},
    ],
)
def test_invalid_revision_is_rejected(tmp_path, clock, kwargs):
    store = OperatorStore.open(
        OperatorSettings(enabled=True, root=tmp_path), initialize=True, clock=clock
    )
    try:
        with pytest.raises(sqlite3.IntegrityError):
            with store.connect() as db:
                insert_receipt(db)
                insert_revision(db, **kwargs)
    finally:
        store.close()
