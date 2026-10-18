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


MIGRATIONS = (MIGRATION, MIGRATION.with_name("002_event_notifications.sql"))


def migration_sql(version: int) -> str:
    return MIGRATIONS[version - 1].read_text()


def apply_migrations(
    connection: sqlite3.Connection,
    *,
    clock: Clock,
    upgrade: bool = False,
    allow_legacy: bool = False
) -> None:
    """Validate history; only fresh initialization or explicit upgrade writes."""
    expected = [
        (i, hashlib.sha256(migration_sql(i).encode()).hexdigest())
        for i in range(1, len(MIGRATIONS) + 1)
    ]
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchone()
    rows = (
        connection.execute(
            "SELECT version, checksum FROM schema_migrations ORDER BY version"
        ).fetchall()
        if exists
        else []
    )
    if exists:
        if (
            not rows
            or [r[0] for r in rows] != list(range(1, len(rows) + 1))
            or len(rows) > len(expected)
        ):
            raise OperatorError("unsupported_schema")
        if rows != expected[: len(rows)]:
            raise OperatorError("migration_checksum_mismatch")
        if len(rows) < len(expected) and not upgrade:
            if allow_legacy:
                return
            raise OperatorError("schema_upgrade_required")
    elif connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table'"
    ).fetchone():
        raise OperatorError("unsupported_schema")
    if len(rows) == len(expected):
        return
    connection.execute("SAVEPOINT operator_migration")
    try:
        for version, checksum in expected[len(rows) :]:
            statement = ""
            for line in migration_sql(version).splitlines(keepends=True):
                statement += line
                if sqlite3.complete_statement(statement):
                    connection.execute(statement)
                    statement = ""
            if statement.strip():
                raise OperatorError("unsupported_schema")
            connection.execute(
                "INSERT INTO schema_migrations VALUES (?, ?, ?)",
                (version, checksum, timestamp(clock)),
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
