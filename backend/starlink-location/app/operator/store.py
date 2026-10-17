"""Private durable SQLite identity and short, connection-owned transactions."""

import fcntl
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

from .clock import Clock
from .errors import OperatorError
from .provenance import StoreHealth
from .schema import apply_migrations, timestamp, validate_integrity
from .settings import OperatorSettings
from .time_models import utc_timestamp


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _private_directory(path: Path) -> None:
    if not path.exists():
        _private_directory(path.parent)
        path.mkdir(mode=0o700)
        _sync_directory(path.parent)


def _write_marker(path: Path, identity: dict, *, first: bool) -> None:
    target = path if first else path.with_suffix(".pending")
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w") as output:
            json.dump(identity, output, sort_keys=True)
            output.flush()
            os.fsync(output.fileno())
        if not first:
            os.replace(target, path)
        _sync_directory(path.parent)
    except BaseException:
        # Preserve the initializing marker. Its presence forbids runtime reset.
        if not first and target.exists():
            target.unlink()
        raise


class OperatorStore:
    def __init__(self, settings: OperatorSettings, clock: Clock):
        self.settings = settings
        self.clock = clock
        self._ready = False
        self._closed = False
        self._identity: dict = {}
        self._latest_recorded_at: str | None = None

    @classmethod
    def open(
        cls, settings: OperatorSettings, *, initialize: bool, clock: Clock
    ) -> "OperatorStore":
        store = cls(settings, clock)
        if not settings.enabled:
            return store
        database, marker = settings.database_path, settings.identity_path
        directory = database.parent
        if not directory.exists() and not initialize:
            raise OperatorError("store_unavailable")
        try:
            _private_directory(directory)
            os.chmod(settings.root, 0o700)
            os.chmod(directory, 0o700)
            if settings.source_mode == "simulation":
                os.chmod(settings.root / "simulation", 0o700)
            lock_fd = os.open(
                directory / "operations.lock", os.O_RDWR | os.O_CREAT, 0o600
            )
            try:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as error:
                    raise OperatorError("store_busy", retryable=True) from error
                if not database.exists() and not marker.exists() and initialize:
                    store._initialize()
                elif not database.is_file() or not marker.is_file():
                    raise OperatorError("store_recovery_required")
                store._verify()
            finally:
                os.close(lock_fd)
        except OperatorError:
            raise
        except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as error:
            raise OperatorError("store_unavailable") from error
        store._ready = True
        return store

    def _connection(self) -> sqlite3.Connection:
        # mode=rw never creates an empty replacement after a file disappears.
        uri = self.settings.database_path.resolve().as_uri() + "?mode=rw"
        connection = sqlite3.connect(uri, uri=True, timeout=2.0)
        try:
            connection.execute("PRAGMA busy_timeout=2000")
            connection.execute("PRAGMA foreign_keys=ON")
            # REPLACE's implicit deletes must run the immutable-history guards.
            connection.execute("PRAGMA recursive_triggers=ON")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA wal_autocheckpoint=1000")
            if connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] != "wal":
                raise OperatorError("store_unavailable")
            for suffix in ("", "-wal", "-shm"):
                path = Path(str(self.settings.database_path) + suffix)
                if path.exists():
                    os.chmod(path, 0o600)
            return connection
        except BaseException:
            connection.close()
            raise

    def _initialize(self) -> None:
        identity = {
            "store_id": str(uuid4()),
            "api_epoch": str(uuid4()),
            "source_mode": self.settings.source_mode,
            "simulation_run_id": self.settings.simulation_run_id,
            "status": "initializing",
        }
        _write_marker(self.settings.identity_path, identity, first=True)
        descriptor = os.open(
            self.settings.database_path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600
        )
        os.close(descriptor)
        connection = self._connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            apply_migrations(connection, clock=self.clock)
            connection.execute(
                "INSERT INTO store_metadata VALUES (1, ?, ?, ?, ?)",
                (
                    identity["store_id"],
                    self.settings.source_mode,
                    self.settings.simulation_run_id,
                    timestamp(self.clock),
                ),
            )
            connection.commit()
            connection.execute("PRAGMA wal_checkpoint(FULL)")
        finally:
            connection.close()
        descriptor = os.open(self.settings.database_path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        _sync_directory(self.settings.database_path.parent)
        identity["status"] = "ready"
        _write_marker(self.settings.identity_path, identity, first=False)

    def _verify(self) -> None:
        identity = json.loads(self.settings.identity_path.read_text())
        if identity["status"] != "ready":
            raise OperatorError("store_recovery_required")
        for name in ("store_id", "api_epoch"):
            if str(UUID(identity[name])) != identity[name]:
                raise OperatorError("store_recovery_required")
        if (identity["source_mode"], identity["simulation_run_id"]) != (
            self.settings.source_mode,
            self.settings.simulation_run_id,
        ):
            raise OperatorError("store_mode_mismatch")
        with self.settings.database_path.open("rb") as database:
            if database.read(16) != b"SQLite format 3\x00":
                raise OperatorError("store_corrupt")
        connection = self._connection()
        try:
            if not connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            ).fetchone():
                raise OperatorError("unsupported_schema")
            apply_migrations(connection, clock=self.clock)
            rows = connection.execute(
                "SELECT store_id, source_mode, simulation_run_id FROM store_metadata"
            ).fetchall()
            if rows != [
                (
                    identity["store_id"],
                    identity["source_mode"],
                    identity["simulation_run_id"],
                )
            ]:
                raise OperatorError("store_identity_mismatch")
            validate_integrity(connection)
            self._latest_recorded_at = connection.execute(
                "SELECT max(recorded_at) FROM revisions"
            ).fetchone()[0]
        finally:
            connection.close()
        self._identity = identity

    @contextmanager
    def connect(self, *, write: bool = False):
        """Commit on success, roll back on every failure, always close locally.

        Readers pin a snapshot; writers acquire admission before version checks.
        Callers keep work short; SQLite bounds lock admission to two seconds.
        Connections are never shared between threads or request contexts.
        """
        if not self._ready or self._closed:
            raise OperatorError("store_unavailable")
        connection = self._connection()
        try:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            latest = connection.execute(
                "SELECT max(recorded_at) FROM revisions"
            ).fetchone()[0]
            connection.commit()
            if latest and (
                self._latest_recorded_at is None or latest > self._latest_recorded_at
            ):
                self._latest_recorded_at = latest
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def health(self) -> StoreHealth:
        regression = self._latest_recorded_at is not None and (
            utc_timestamp(self.clock.now()) < utc_timestamp(self._latest_recorded_at)
        )
        return StoreHealth(
            ready=self._ready and not self._closed,
            store_id=self._identity.get("store_id"),
            api_epoch=self._identity.get("api_epoch"),
            source_mode=self.settings.source_mode,
            simulation_run_id=self.settings.simulation_run_id,
            clock_regression=regression,
            error_code=(
                None if self._ready and not self._closed else "store_unavailable"
            ),
        )

    def close(self) -> None:
        """Stop admitting new contexts; each existing context owns its cleanup."""
        self._closed = True
        self._ready = False
