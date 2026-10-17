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
                with pytest.raises(sqlite3.IntegrityError), store.connect() as db:
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
        with pytest.raises(sqlite3.IntegrityError), store.connect() as db:
            insert_receipt(db)
            insert_revision(db, **kwargs)
    finally:
        store.close()


@pytest.mark.parametrize(
    "table, conflict",
    [
        ("commands", "primary-key"),
        ("commands", "unique-key"),
        ("revisions", "primary-key"),
        ("revisions", "unique-key"),
        ("records", "primary-key"),
    ],
)
def test_replace_cannot_overwrite_history_receipts_or_pointers(
    tmp_path, clock, table, conflict
):
    store = OperatorStore.open(
        OperatorSettings(enabled=True, root=tmp_path), initialize=True, clock=clock
    )
    try:
        with store.connect(write=True) as db:
            insert_receipt(db)
            # No references to this receipt: a unique-key replacement must fail
            # because of immutability, independently of deferred FK checks.
            db.execute("""INSERT INTO commands VALUES
                ('unused', 'unused-key', 'unused-hash', 1, 'now', 201, '{}')""")
            insert_revision(db)
            db.execute("INSERT INTO records VALUES ('record', 1)")
            insert_revision(
                db,
                version=2,
                previous=1,
                operation="update",
                reason="Operator correction",
                origin="automatic",
            )
            db.execute("UPDATE records SET current_version=2")
            originals = {
                name: db.execute(f"SELECT * FROM {name}").fetchall()
                for name in ("commands", "revisions", "records")
            }
            where = (
                " WHERE command_id='unused'"
                if table == "commands" and conflict == "unique-key"
                else ""
            )
            if table == "revisions":
                where = " WHERE version=1"
            selected = db.execute(f"SELECT * FROM {table}{where}")
            replacement = dict(
                zip([column[0] for column in selected.description], selected.fetchone())
            )
        if table == "commands":
            replacement["request_hash"] = "changed-hash"
            if conflict == "unique-key":
                replacement["command_id"] = "replacement-command"
            else:
                replacement["idempotency_key"] = "changed-key"
        elif table == "revisions":
            replacement["payload_json"] = '{"changed":true}'
            if conflict == "unique-key":
                replacement["journal_seq"] = 1000
        else:
            replacement["current_version"] = 1
        columns = ", ".join(replacement)
        parameters = ", ".join("?" for _ in replacement)
        with pytest.raises(sqlite3.IntegrityError), store.connect(write=True) as db:
            db.execute(
                f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({parameters})",
                tuple(replacement.values()),
            )
        with store.connect() as db:
            for name, original in originals.items():
                assert db.execute(f"SELECT * FROM {name}").fetchall() == original
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        store.close()
