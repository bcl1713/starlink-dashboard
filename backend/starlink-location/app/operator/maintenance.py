"""Cross-process maintenance admission, capacity accounting and bounded checks."""

import fcntl
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from .errors import OperatorError


@contextmanager
def admission(settings, *, exclusive=False):
    descriptor = os.open(
        settings.database_path.parent / "operations.lock", os.O_RDWR | os.O_CREAT, 0o600
    )
    try:
        try:
            fcntl.flock(
                descriptor,
                (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB,
            )
        except BlockingIOError as error:
            raise OperatorError("store_busy", retryable=True) from error
        yield
    finally:
        os.close(descriptor)


def storage_error(error):
    code = getattr(error, "sqlite_errorcode", 0) & 0xFF
    if code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
        return OperatorError("store_busy", retryable=True)
    if code in (sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB):
        return OperatorError("store_corrupt")
    if code == sqlite3.SQLITE_INTERRUPT:
        return OperatorError("maintenance_timeout", retryable=True)
    return OperatorError("store_unavailable")


def capacity_status(store):
    used = sum(
        path.stat().st_size
        for path in (
            store.settings.database_path,
            Path(str(store.settings.database_path) + "-wal"),
        )
        if path.exists()
    )
    limit = store.settings.capacity_bytes
    return {
        "used_bytes": used,
        "limit_bytes": limit,
        "advisory": used * 5 >= limit * 4,
        "exceeded": used >= limit,
    }


@contextmanager
def bounded(connection, *, seconds=2.0):
    # Real monotonic time bounds resource ownership even under an injected clock.
    deadline = time.monotonic() + seconds

    def check(*_):
        if time.monotonic() >= deadline:
            raise OperatorError("maintenance_timeout", retryable=True)

    connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
    try:
        yield check
        check()
    finally:
        connection.set_progress_handler(None, 0)


def passive_checkpoint(store):
    """Never truncate a WAL pinned by a reader; return SQLite checkpoint counts."""
    with admission(store.settings):
        store._check_identity()
        connection = store._connection()
        try:
            with bounded(connection):
                return connection.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
        except sqlite3.Error as error:
            raise storage_error(error) from error
        finally:
            connection.close()
