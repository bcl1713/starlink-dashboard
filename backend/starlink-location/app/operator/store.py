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
from .maintenance import admission, storage_error
from .provenance import StoreHealth
from .schema import apply_migrations, timestamp
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
        self._error_code = "store_unavailable"
        self._identity: dict = {}
        self._latest_recorded_at: str | None = None

    @classmethod
    def open(
        cls,
        settings: OperatorSettings,
        *,
        initialize: bool,
        clock: Clock,
        allow_legacy: bool = False
    ) -> "OperatorStore":
        store = cls(settings, clock)
        store._allow_legacy = allow_legacy
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
                os.chmod(
                    settings.root
                    / (
                        "simulation-missions"
                        if settings.mission_journal
                        else "simulation"
                    ),
                    0o700,
                )
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
            connection.execute("PRAGMA foreign_keys=OFF")
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
            connection.execute("PRAGMA foreign_keys=ON")
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
        from .wal import validate_wal

        validate_wal(self.settings.database_path)
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
            apply_migrations(
                connection,
                clock=self.clock,
                allow_legacy=getattr(self, "_allow_legacy", False),
            )
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
            from .recovery import validate_connection

            validate_connection(
                connection,
                clock=self.clock,
                allow_legacy=getattr(self, "_allow_legacy", False),
            )
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
        connection = None
        try:
            with admission(self.settings):
                self._check_identity()
                connection = self._connection()
                commit_pending = False
                try:
                    connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
                    yield connection
                    latest = connection.execute(
                        "SELECT max(recorded_at) FROM revisions"
                    ).fetchone()[0]
                    commit_pending = write
                    connection.commit()
                    commit_pending = False
                    if latest and (
                        self._latest_recorded_at is None
                        or latest > self._latest_recorded_at
                    ):
                        self._latest_recorded_at = latest
                except BaseException as error:
                    try:
                        connection.rollback()
                    except (sqlite3.Error, OSError) as rollback_error:
                        if commit_pending:
                            self._commit_uncertain(rollback_error)
                        raise
                    if (
                        commit_pending
                        and isinstance(error, (sqlite3.Error, OSError))
                        and not isinstance(error, sqlite3.IntegrityError)
                        and storage_error(error).code != "store_busy"
                    ):
                        self._commit_uncertain(error)
                    raise
                finally:
                    connection.close()
        except sqlite3.IntegrityError:
            # Constraint rejection is a rolled-back invalid mutation, not media
            # failure; do not disable a healthy store for a rejected statement.
            raise
        except (sqlite3.Error, OSError) as error:
            mapped = storage_error(error)
            if not mapped.retryable:
                self._ready = False
                self._error_code = mapped.code
            raise mapped from error

    def _commit_uncertain(self, error):
        # A driver may report I/O failure after SQLite durably committed. A
        # successful rollback is not proof that this command was never saved.
        self._ready = False
        self._error_code = "commit_outcome_unknown"
        raise OperatorError(self._error_code, retryable=True) from error

    def _check_identity(self):
        if not self._ready or self._closed:
            raise OperatorError(
                self._error_code, retryable=self._error_code == "commit_outcome_unknown"
            )
        try:
            identity = json.loads(self.settings.identity_path.read_text())
            if identity != self._identity:
                self._ready = False
                self._error_code = "store_epoch_changed"
                raise OperatorError(self._error_code)
        except (ValueError, OSError) as error:
            self._ready = False
            self._error_code = "store_recovery_required"
            raise OperatorError(self._error_code) from error

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
            replay_run_id=self.settings.replay_run_id,
            mission_journal=self.settings.mission_journal,
            clock_regression=regression,
            error_code=(None if self._ready and not self._closed else self._error_code),
        )

    def close(self) -> None:
        """Stop admitting new contexts; each existing context owns its cleanup."""
        self._closed = True
        self._ready = False
