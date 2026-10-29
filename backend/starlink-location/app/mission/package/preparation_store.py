"""Small persisted export job records; package bytes live in owned private files."""

import json
from typing import Literal

from pydantic import BaseModel, Field

from .json_stream import iter_json

MAX_ARCHIVE_SNAPSHOT_BYTES = 384 * 1024 * 1024
MAX_ARCHIVE_STORAGE_BYTES = 768 * 1024 * 1024

TERMINAL = {"ready", "failed", "cancelled", "superseded", "expired"}


class ExportPreparation(BaseModel):
    id: str
    mission_id: str
    state: Literal[
        "queued", "preparing", "ready", "failed", "cancelled", "superseded", "expired"
    ]
    fingerprint: str
    revision: int | None = None
    snapshot_policy: Literal["legacy", "captured"] = "legacy"
    stage: str = "queued"
    stage_started_at: float | None = None
    stage_timings: dict[str, float] = Field(default_factory=dict)
    leg_states: dict[str, str] = Field(default_factory=dict)
    queued_at: float
    started_at: float | None = None
    finished_at: float | None = None
    deadline: float
    expires_at: float | None = None
    error_code: str | None = None
    warning_code: str | None = None
    briefing_status: str | None = None
    download_url: str | None = None


class PreparationStore:
    def __init__(self, cache):
        self.cache = cache
        with cache.connection() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS export_jobs (id TEXT PRIMARY KEY, mission TEXT, payload TEXT)"
            )

            db.execute(
                "CREATE TABLE IF NOT EXISTS export_archive_snapshots (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS export_planning_snapshots (id TEXT PRIMARY KEY, payload BLOB NOT NULL)"
            )

    def planning(self, job_id):
        from .frozen_planning import FrozenPlanning

        with self.cache.connection() as db:
            row = db.execute(
                "SELECT payload FROM export_planning_snapshots WHERE id=?", (job_id,)
            ).fetchone()
        return FrozenPlanning.decode(row[0]) if row else None

    def discard_planning(self, job_id):
        with self.cache.connection() as db:
            db.execute("DELETE FROM export_planning_snapshots WHERE id=?", (job_id,))

    def archive(self, job_id):
        with self.cache.connection() as db:
            row = db.execute(
                "SELECT payload FROM export_archive_snapshots WHERE id=?", (job_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def discard_archive(self, job_id):
        with self.cache.connection() as db:
            db.execute("DELETE FROM export_archive_snapshots WHERE id=?", (job_id,))
            db.execute("DELETE FROM export_planning_snapshots WHERE id=?", (job_id,))

    def write(self, job, *, archive=None, owner=None, planning=None):
        payload = None
        size = 0
        if archive is not None:
            # Count while encoding, before constructing a potentially huge joined
            # string or starting a DB transaction. Never truncate a snapshot.
            chunks, size = [], 0
            for chunk in iter_json(archive):
                size += len(chunk)  # Escaped JSON is ASCII.
                if size > MAX_ARCHIVE_SNAPSHOT_BYTES:
                    raise RuntimeError("Archive snapshot size limit exceeded")
                chunks.append(chunk)
            payload = "".join(chunks)
        planning_payload = planning.encode() if planning is not None else None
        size += len(planning_payload) if planning_payload is not None else 0
        if size > MAX_ARCHIVE_SNAPSHOT_BYTES:
            raise RuntimeError("Archive snapshot size limit exceeded")
        with self.cache.connection() as db:
            if payload is not None or owner is not None or planning_payload is not None:
                # Reserve capacity and job acknowledgment in one transaction.
                # SQLite's freed pages are reused; quota is for live payloads.
                db.execute("BEGIN IMMEDIATE")
                used = db.execute(
                    "SELECT coalesce(sum(length(CAST(payload AS BLOB))), 0) FROM export_archive_snapshots"
                ).fetchone()[0]
                used += db.execute(
                    "SELECT coalesce(sum(length(payload)),0) FROM export_planning_snapshots"
                ).fetchone()[0]
                if db.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='export_artifact_owners'"
                ).fetchone():
                    used += db.execute(
                        "SELECT coalesce(sum(reserved),0) FROM export_artifact_owners"
                    ).fetchone()[0]
                if used + size > MAX_ARCHIVE_STORAGE_BYTES:
                    raise RuntimeError(
                        "Archive storage size limit exceeded; retry after expiry"
                    )
            db.execute(
                "INSERT OR REPLACE INTO export_jobs VALUES (?,?,?)",
                (job.id, job.mission_id, job.model_dump_json()),
            )
            if archive is not None:
                db.execute(
                    "INSERT INTO export_archive_snapshots VALUES (?,?)",
                    (job.id, payload),
                )
            if owner is not None:
                owner.attach(db, job.id)
            if planning_payload is not None:
                db.execute(
                    "INSERT INTO export_planning_snapshots VALUES (?,?)",
                    (job.id, planning_payload),
                )

    def write_pending(self, job):
        with self.cache.connection() as db:
            return (
                db.execute(
                    "UPDATE export_jobs SET payload=? WHERE id=? AND mission=? AND json_extract(payload, '$.state') IN ('queued','preparing')",
                    (job.model_dump_json(), job.id, job.mission_id),
                ).rowcount
                == 1
            )

    def read(self, mission, job_id):
        with self.cache.connection() as db:
            row = db.execute(
                "SELECT payload FROM export_jobs WHERE mission=? AND id=?",
                (mission, job_id),
            ).fetchone()
        if row is None:
            raise KeyError("Export preparation not found")
        return ExportPreparation.model_validate_json(row[0])

    def all(self):
        with self.cache.connection() as db:
            return [
                ExportPreparation.model_validate(json.loads(r[0]))
                for r in db.execute("SELECT payload FROM export_jobs")
            ]
