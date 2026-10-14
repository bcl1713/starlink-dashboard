"""Small persisted export job records; package bytes live in owned private files."""

import json
from typing import Literal

from pydantic import BaseModel, Field

TERMINAL = {"ready", "failed", "cancelled", "superseded", "expired"}


class ExportPreparation(BaseModel):
    id: str
    mission_id: str
    state: Literal[
        "queued", "preparing", "ready", "failed", "cancelled", "superseded", "expired"
    ]
    fingerprint: str
    revision: int | None = None
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

    def write(self, job):
        with self.cache.connection() as db:
            db.execute(
                "INSERT OR REPLACE INTO export_jobs VALUES (?,?,?)",
                (job.id, job.mission_id, job.model_dump_json()),
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
