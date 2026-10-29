"""Cross-process reservations and private immutable telemetry capture files."""

import hashlib
import os
import re
import shutil
import time
from contextlib import contextmanager
from uuid import uuid4

from .archive_errors import ArchiveCapacityError, ArchiveDeadlineError
from .download_readers import DownloadReaders

MIB = 1024 * 1024
CAPTURE_RESERVATION = 513 * MIB  # 256 MiB index plus ZIP worst-case headroom.
DISK_QUOTA = 768 * MIB
SPOOL_RESERVATION = 200 * MIB


class BudgetFile:
    def __init__(self, stream, owner, *, limit, reserve_base=0):
        self.stream, self.owner = stream, owner
        self.limit, self.reserve_base, self.high_water = limit, reserve_base, 0

    def write(self, data):
        self.owner.check()
        size = max(self.high_water, self.stream.tell() + len(data))
        if size > self.limit:
            raise ArchiveCapacityError("artifact-file", self.limit)
        if self.reserve_base:
            reservation = self.reserve_base + ((size + MIB - 1) // MIB) * MIB
            if reservation > self.owner.reserved:
                self.owner.resize(reservation)
        result = self.stream.write(data)
        self.high_water = size
        return result

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()


class CaptureOwner:
    def __init__(self, store, identity, reserved, check, deadline, kind, job_id):
        self.store, self.id, self.reserved = store, identity, reserved
        self.directory = store.root / identity
        self.callback, self.deadline, self.kind, self.job_id = (
            check,
            deadline,
            kind,
            job_id,
        )
        self.elapsed_deadline = time.monotonic() + 600
        self.retained = False
        self.leg_ids = None

    def check(self):
        if self.callback:
            self.callback()
        if (
            self.store.clock() >= self.deadline
            or time.monotonic() >= self.elapsed_deadline
        ):
            raise ArchiveDeadlineError()

    def resize(self, size):
        self.store.reserve(self.id, size)
        self.reserved = size

    def open_sidecar(self):
        stream = (self.directory / "telemetry.part").open("x+b")
        os.chmod(stream.name, 0o600)
        return BudgetFile(stream, self, limit=257 * MIB)

    def publish(self, metadata):
        self.check()
        temporary, target = (
            self.directory / "telemetry.part",
            self.directory / "telemetry.zip",
        )
        digest = hashlib.sha256()
        with temporary.open("r+b") as source:
            source.flush()
            os.fsync(source.fileno())
            while block := source.read(65536):
                self.check()
                digest.update(block)
        temporary.replace(target)
        self.store.sync_directory(self.directory)
        size = target.stat().st_size
        self.resize(size)
        return {"id": self.id, "sha256": digest.hexdigest(), "size": size, **metadata}

    def attach(self, db, job_id):
        self.check()
        updated = db.execute(
            "UPDATE export_artifact_owners SET job=?,state='attached' WHERE id=? AND job IS NULL AND state='capturing'",
            (job_id, self.id),
        ).rowcount
        if updated != 1:
            raise RuntimeError("Export capture ownership changed")

    def open_download(self):
        stream = (self.directory / "download.part").open("x+b")
        os.chmod(stream.name, 0o600)
        return BudgetFile(stream, self, limit=357 * MIB, reserve_base=SPOOL_RESERVATION)

    def publish_download(self, target, size):
        self.check()
        (self.directory / "download.part").replace(target)
        self.store.sync_directory(target.parent)
        self.resize(size)
        with self.store.cache.connection() as db:
            db.execute(
                "UPDATE export_artifact_owners SET state='published' WHERE id=?",
                (self.id,),
            )
        self.retained = True


class ArchiveFiles:
    def __init__(self, cache, *, clock=time.time):
        self.cache, self.clock = cache, clock
        self.root = cache.path.parent / "export-captures"
        self.downloads = cache.path.parent / "exports"
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        with cache.connection() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS export_artifact_owners (id TEXT PRIMARY KEY, job TEXT, kind TEXT, state TEXT, reserved INTEGER, lease_until REAL)"
            )
        self.readers = DownloadReaders(cache, clock)

    @staticmethod
    def sync_directory(directory):
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def reserve(self, identity, size):
        with self.cache.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            used = db.execute(
                "SELECT coalesce(sum(reserved),0) FROM export_artifact_owners WHERE id!=?",
                (identity,),
            ).fetchone()[0]
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='export_archive_snapshots'"
            ).fetchone():
                used += db.execute(
                    "SELECT coalesce(sum(length(CAST(payload AS BLOB))),0) FROM export_archive_snapshots"
                ).fetchone()[0]
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='export_planning_snapshots'"
            ).fetchone():
                used += db.execute(
                    "SELECT coalesce(sum(length(payload)),0) FROM export_planning_snapshots"
                ).fetchone()[0]
            if used + size > DISK_QUOTA:
                raise ArchiveCapacityError("live-export-storage", DISK_QUOTA)
            db.execute(
                "UPDATE export_artifact_owners SET reserved=? WHERE id=?",
                (size, identity),
            )

    @contextmanager
    def capture(self, *, check=None, deadline=None, kind="capture", job_id=None):
        identity, now = uuid4().hex, self.clock()
        deadline = deadline if deadline is not None else now + 600
        reserved = CAPTURE_RESERVATION if kind == "capture" else SPOOL_RESERVATION
        with self.cache.connection() as db:
            db.execute(
                "INSERT INTO export_artifact_owners VALUES (?,?,?,?,?,?)",
                (identity, job_id, kind, "capturing", 0, deadline + 30),
            )
        owner = CaptureOwner(self, identity, reserved, check, deadline, kind, job_id)
        try:
            self.reserve(identity, reserved)
            owner.directory.mkdir(mode=0o700)
            self.sync_directory(self.root)
            yield owner
        except BaseException:
            self.release(identity)
            raise
        finally:
            with self.cache.connection() as db:
                row = db.execute(
                    "SELECT job FROM export_artifact_owners WHERE id=?", (identity,)
                ).fetchone()
            if row and (row[0] is None or (kind == "assembly" and not owner.retained)):
                self.release(identity)

    def path(self, attachment):
        identity = attachment["id"]
        if not re.fullmatch(r"[0-9a-f]{32}", identity):
            raise ValueError("Invalid export artifact identity")
        return self.root / identity / "telemetry.zip"

    def release(self, identity, *, download=None):
        if not re.fullmatch(r"[0-9a-f]{32}", identity):
            raise ValueError("Invalid export artifact identity")
        with self.cache.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT job,kind FROM export_artifact_owners WHERE id=?", (identity,)
            ).fetchone()
            if row and row[1] == "assembly" and row[0]:
                current = (
                    db.execute(
                        "SELECT json_extract(payload,'$.state') FROM export_jobs WHERE id=?",
                        (row[0],),
                    ).fetchone()
                    if db.execute(
                        "SELECT 1 FROM sqlite_master WHERE name='export_jobs'"
                    ).fetchone()
                    else None
                )
                if current and current[0] == "ready":
                    # A ready-state commit may have succeeded before a later
                    # publication bookkeeping error. Preserve the valid result.
                    return
                if self.readers.active(db, row[0]):
                    return
                download = self.downloads / f"{row[0]}.zip"
            directory = self.root / identity
            if directory.exists():
                shutil.rmtree(directory)
            if download is not None:
                download.unlink(missing_ok=True)
            db.execute("DELETE FROM export_artifact_owners WHERE id=?", (identity,))

    def open_download(self, job):
        return self.readers.open(job, self.downloads / f"{job.id}.zip")

    def expire_download(self, job):
        # Published files no longer have an assembly writer. Serialize expiry
        # with reader registration; live readers keep both pathname and quota.
        with self.cache.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute(
                "SELECT json_extract(payload,'$.state') FROM export_jobs WHERE id=?",
                (job.id,),
            ).fetchone()
            if (
                not current
                or current[0] != "expired"
                or self.readers.active(db, job.id)
            ):
                return
            owners = db.execute(
                "SELECT id FROM export_artifact_owners WHERE job=? AND kind='assembly'",
                (job.id,),
            ).fetchall()
            (self.downloads / f"{job.id}.zip").unlink(missing_ok=True)
            for owner in owners:
                directory = self.root / owner[0]
                if directory.exists():
                    shutil.rmtree(directory)
                db.execute("DELETE FROM export_artifact_owners WHERE id=?", (owner[0],))

    def sweep(self, jobs):
        # Called only by the elected assembly worker under its process file lock.
        # Older inline jobs have ready ZIPs but no reservation row yet. Count
        # their existing bytes without deleting or recapturing those downloads.
        for job in jobs.all():
            download = self.downloads / f"{job.id}.zip"
            if job.state == "ready" and download.exists():
                with self.cache.connection() as db:
                    db.execute(
                        "INSERT INTO export_artifact_owners SELECT ?,?,'assembly','published',?,? WHERE NOT EXISTS (SELECT 1 FROM export_artifact_owners WHERE job=? AND kind='assembly')",
                        (
                            uuid4().hex,
                            job.id,
                            download.stat().st_size,
                            job.expires_at or self.clock(),
                            job.id,
                        ),
                    )
        with self.cache.connection() as db:
            owners = db.execute("SELECT * FROM export_artifact_owners").fetchall()
        by_id = {job.id: job for job in jobs.all()}
        for row in owners:
            identity, job_id, kind, _state, _reserved, lease = row
            job = by_id.get(job_id)
            if job is None:
                if self.clock() >= lease:
                    self.release(identity)
            elif job.state in {"failed", "cancelled", "superseded", "expired"}:
                self.release(
                    identity,
                    download=(
                        self.downloads / f"{job.id}.zip" if kind == "assembly" else None
                    ),
                )
            elif job.state == "ready" and kind == "capture":
                self.release(identity)
