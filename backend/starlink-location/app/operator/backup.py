"""Validated online SQLite snapshots with durable manifest publication."""

import fcntl
import hashlib
import json
import os
import sqlite3
from contextlib import closing, contextmanager, nullcontext
from pathlib import Path
from uuid import uuid4

from .errors import OperatorError
from .maintenance import admission, bounded, storage_error
from .recovery import validate_connection
from .schema import timestamp
from .store import _private_directory, _sync_directory


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def publication_lock(directory):
    descriptor = os.open(directory / ".publication.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise OperatorError("store_busy", retryable=True) from error
        yield
    finally:
        os.close(descriptor)


def snapshot_metadata(path, *, clock):
    with closing(
        sqlite3.connect(
            path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True, timeout=2
        )
    ) as connection:
        with bounded(connection):
            if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise OperatorError("store_corrupt")
        validate_connection(connection, clock=clock, allow_legacy=True)
        store_id, mode, run = connection.execute(
            "SELECT store_id, source_mode, simulation_run_id FROM store_metadata"
        ).fetchone()
        return {
            "store_id": store_id,
            "source_mode": mode,
            "simulation_run_id": run,
            "schema_version": connection.execute(
                "SELECT max(version) FROM schema_migrations"
            ).fetchone()[0],
            "H": connection.execute(
                "SELECT coalesce(max(journal_seq), 0) FROM revisions"
            ).fetchone()[0],
        }


def validated_backup(manifest, *, clock):
    manifest = Path(manifest)
    try:
        info = json.loads(manifest.read_text())
        name = info["database"]
        if Path(name).name != name or not name.endswith(".sqlite3"):
            raise ValueError("Invalid backup filename")
        database = manifest.parent / name
        if checksum(database) != info["checksum"]:
            raise OperatorError("backup_checksum_mismatch")
        metadata = snapshot_metadata(database, clock=clock)
        if any(info[key] != value for key, value in metadata.items()):
            raise OperatorError("store_corrupt")
        return info, database
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as error:
        raise OperatorError("store_corrupt") from error


def backup_store(store, *, directory: Path, admitted: bool = False) -> Path:
    directory = Path(directory)
    token = (
        "backup-"
        + timestamp(store.clock).replace(":", "").replace(".", "")
        + "-"
        + str(uuid4())
    )
    temporary = directory / (token + ".pending")
    database = directory / (token + ".sqlite3")
    manifest = directory / (token + ".json")
    pending_manifest = directory / (token + ".json.pending")
    published = False
    try:
        _private_directory(directory)
        with nullcontext() if admitted else admission(store.settings):
            store._check_identity()
            with closing(store._connection()) as source, closing(
                sqlite3.connect(temporary, timeout=2)
            ) as destination:
                os.chmod(temporary, 0o600)
                with bounded(source) as check:
                    source.backup(destination, pages=64, progress=check, sleep=0.05)
        info = snapshot_metadata(temporary, clock=store.clock)
        info.update(
            database=database.name,
            checksum=checksum(temporary),
            created_at=timestamp(store.clock),
        )
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        with publication_lock(directory):
            valid = _published(directory, store)
            info["publication_sequence"] = (
                max((item[0] for item in valid), default=0) + 1
            )
            os.replace(temporary, database)
            with pending_manifest.open("x") as handle:
                os.chmod(pending_manifest, 0o600)
                json.dump(info, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(pending_manifest, manifest)
            _sync_directory(directory)
            published = True
            valid.append((info["publication_sequence"], manifest, database))
            for _, old_manifest, old_database in sorted(valid)[
                : -store.settings.backup_count
            ]:
                old_manifest.unlink(missing_ok=True)
                old_database.unlink(missing_ok=True)
            _sync_directory(directory)
        return manifest
    except (OSError, sqlite3.Error) as error:
        raise storage_error(error) from error
    finally:
        for path in (temporary, pending_manifest):
            path.unlink(missing_ok=True)
        if not published:
            manifest.unlink(missing_ok=True)
            database.unlink(missing_ok=True)


def _published(directory, store):
    valid = []
    for manifest in directory.glob("backup-*.json"):
        try:
            info, database = validated_backup(manifest, clock=store.clock)
        except OperatorError:
            continue
        if info["store_id"] == str(store.health().store_id):
            valid.append((info.get("publication_sequence", 0), manifest, database))
    return valid
