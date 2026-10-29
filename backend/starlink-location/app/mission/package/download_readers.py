"""Persistent reader references backed by cross-process kernel file locks."""

import json
import sqlite3
from uuid import uuid4

from filelock import FileLock, Timeout


class ReaderStream:
    def __init__(self, stream, registry, identity, lock):
        self.stream, self.registry, self.id, self.lock = (
            stream,
            registry,
            identity,
            lock,
        )

    def close(self):
        if self.stream.closed:
            return
        self.stream.close()
        removed = False
        try:
            with self.registry.cache.connection() as db:
                db.execute("DELETE FROM export_download_readers WHERE id=?", (self.id,))
            removed = True
        finally:
            self.lock.release()
            if removed:
                self.registry.lock_path(self.id).unlink(missing_ok=True)

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        try:
            self.close()
        except (OSError, sqlite3.Error):
            # Closed descriptors release their kernel lock; stale references
            # remain counted until the elected cleanup worker checks the lock.
            pass


class DownloadReaders:
    def __init__(self, cache, clock):
        self.cache, self.clock = cache, clock
        self.root = cache.path.parent / "export-readers"
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        with cache.connection() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS export_download_readers (id TEXT PRIMARY KEY,job TEXT,lease_until REAL)"
            )

    def lock_path(self, identity):
        return self.root / (identity + ".lock")

    def open(self, job, path):
        identity = uuid4().hex
        lock = FileLock(self.lock_path(identity), thread_local=False)
        lock.acquire(timeout=0)
        stream = None
        try:
            with self.cache.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT payload FROM export_jobs WHERE id=? AND mission=?",
                    (job.id, job.mission_id),
                ).fetchone()
                current = json.loads(row[0]) if row else {}
                if current.get("state") != "ready":
                    raise ValueError("Export is not ready")
                if self.clock() >= current["expires_at"]:
                    raise TimeoutError("Export expired")
                db.execute(
                    "INSERT INTO export_download_readers VALUES (?,?,?)",
                    (identity, job.id, self.clock() + 60),
                )
                stream = path.open("rb")
            return ReaderStream(stream, self, identity, lock)
        except BaseException:
            if stream is not None:
                stream.close()
            lock.release()
            self.lock_path(identity).unlink(missing_ok=True)
            raise

    def active(self, db, job_id):
        rows = db.execute(
            "SELECT id,lease_until FROM export_download_readers WHERE job=?", (job_id,)
        ).fetchall()
        for identity, lease_until in rows:
            if self.clock() < lease_until:
                return True
            lock = FileLock(self.lock_path(identity), thread_local=False)
            try:
                lock.acquire(timeout=0)
            except Timeout:
                # A paused/slow process can hold bytes beyond the lease time.
                # The kernel lock, rather than elapsed time, proves closure.
                return True
            try:
                db.execute(
                    "DELETE FROM export_download_readers WHERE id=?", (identity,)
                )
            finally:
                lock.release()
            self.lock_path(identity).unlink(missing_ok=True)
        return False
