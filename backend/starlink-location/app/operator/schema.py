"""Transactional numbered migrations and read-only startup integrity checks."""

import hashlib
import sqlite3
from pathlib import Path

from .clock import Clock
from .errors import OperatorError
from .time_models import utc_timestamp

MIGRATION = Path(__file__).with_name("migrations") / "001_initial.sql"


def timestamp(clock: Clock) -> str:
    return (
        utc_timestamp(clock.now())
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def apply_migrations(connection: sqlite3.Connection, *, clock: Clock) -> None:
    """Apply the initial migration once, rejecting unknown or altered history."""
    sql = MIGRATION.read_text()
    checksum = hashlib.sha256(sql.encode()).hexdigest()
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchone()
    if exists:
        rows = connection.execute(
            "SELECT version, checksum FROM schema_migrations ORDER BY version"
        ).fetchall()
        if any(row[0] != 1 for row in rows):
            raise OperatorError("unsupported_schema")
        if len(rows) != 1 or rows[0][1] != checksum:
            raise OperatorError("migration_checksum_mismatch")
        return
    if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table'").fetchone():
        raise OperatorError("unsupported_schema")
    connection.execute("SAVEPOINT operator_migration")
    try:
        statement = ""
        for line in sql.splitlines(keepends=True):
            statement += line
            if sqlite3.complete_statement(statement):
                connection.execute(statement)
                statement = ""
        connection.execute(
            "INSERT INTO schema_migrations VALUES (1, ?, ?)",
            (checksum, timestamp(clock)),
        )
        connection.execute("RELEASE operator_migration")
    except BaseException:
        connection.execute("ROLLBACK TO operator_migration")
        connection.execute("RELEASE operator_migration")
        raise


def validate_integrity(connection: sqlite3.Connection) -> None:
    if connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
        raise OperatorError("store_corrupt")
    if connection.execute("PRAGMA foreign_key_check").fetchall():
        raise OperatorError("store_corrupt")
    mismatch = connection.execute("""
        SELECT 1 FROM revisions v LEFT JOIN records r ON r.record_id = v.record_id
        WHERE r.record_id IS NULL OR r.current_version < v.version LIMIT 1
    """).fetchone()
    invalid_json = connection.execute("""
        SELECT 1 FROM revisions WHERE NOT json_valid(author_json)
        OR NOT json_valid(time_json) OR NOT json_valid(provenance_json)
        OR NOT json_valid(payload_json) LIMIT 1
    """).fetchone()
    if mismatch or invalid_json:
        raise OperatorError("store_corrupt")
