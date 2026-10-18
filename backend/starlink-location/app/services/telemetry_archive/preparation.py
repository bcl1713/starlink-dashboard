"""Explicit, bounded telemetry preparation; source archives never expire here."""

import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.mission.package.customer_artifacts import MissionPackageDownload
from app.mission.package.preparation_store import ExportPreparation
from app.services.telemetry_archive.package import build_telemetry_package
from app.services.telemetry_archive.store import ArchiveStore


class TelemetryPreparationService:
    def __init__(
        self, root: Path, archive: ArchiveStore, load_mission, *, clock=time.time
    ):
        self.archive, self.load_mission, self.clock = archive, load_mission, clock
        self.directory = root / "downloads"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.pool = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="telemetry-export"
        )
        with archive.ledger.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS telemetry_jobs (id TEXT PRIMARY KEY, mission TEXT, payload TEXT, snapshot TEXT)"
            )
            pending = db.execute(
                "SELECT id FROM telemetry_jobs WHERE json_extract(payload, '$.state') IN ('queued','preparing')"
            ).fetchall()
        for row in pending:
            self.pool.submit(self._build, row[0])

    def _read(self, mission_id, job_id):
        with self.archive.ledger.connect() as db:
            row = db.execute(
                "SELECT payload FROM telemetry_jobs WHERE id=? AND mission=?",
                (job_id, mission_id),
            ).fetchone()
        if not row:
            raise KeyError("Telemetry preparation not found")
        return ExportPreparation.model_validate_json(row[0])

    def _write(self, job):
        with self.archive.ledger.connect() as db:
            db.execute(
                "UPDATE telemetry_jobs SET payload=? WHERE id=? AND mission=?",
                (job.model_dump_json(), job.id, job.mission_id),
            )

    def capture_snapshot(
        self, mission_id: str, allow_partial: bool = False, *, allow_empty: bool = False
    ):
        mission = self.load_mission(mission_id)
        if mission is None:
            raise KeyError("Mission not found")
        captures = []
        for leg in mission.legs:
            capture = self.archive.capture(mission_id, leg.id)
            if capture is None:
                capture = {
                    "schema_version": 1,
                    "mission_id": mission_id,
                    "leg_id": leg.id,
                    "revision": "unavailable",
                    "source_mode": "live",
                    "start": None,
                    "end": None,
                    "state": "unavailable",
                    "complete": False,
                    "events": [],
                    "samples": [],
                    "gaps": [{"reason": "leg_not_recorded"}],
                }
            elif capture["state"] != "sealed":
                capture = capture | {
                    "samples": self.archive.samples(
                        datetime.fromisoformat(capture["start"]),
                        datetime.fromisoformat(capture["available_until"]),
                    )
                }
            captures.append(capture)
        if (not captures and not allow_empty) or (
            not allow_partial
            and any(not capture.get("complete") for capture in captures)
        ):
            raise ValueError(
                "Mission telemetry is incomplete; request a labeled partial package"
            )
        return {
            "mission_id": mission_id,
            "captures": captures,
            "allow_partial": allow_partial,
        }

    def start(self, mission_id: str, allow_partial: bool = False):
        snapshot = json.dumps(
            self.capture_snapshot(mission_id, allow_partial), sort_keys=True
        )
        captures = json.loads(snapshot)["captures"]
        fingerprint = hashlib.sha256(snapshot.encode()).hexdigest()
        now = self.clock()
        job = ExportPreparation(
            id="telemetry-" + str(uuid4()),
            mission_id=mission_id,
            state="queued",
            fingerprint=fingerprint,
            queued_at=now,
            deadline=now + 600,
            warning_code=(
                "partial_telemetry"
                if any(not capture.get("complete") for capture in captures)
                else None
            ),
        )
        with self.archive.ledger.connect() as db:
            db.execute(
                "INSERT INTO telemetry_jobs VALUES (?, ?, ?, ?)",
                (job.id, mission_id, job.model_dump_json(), snapshot),
            )
        self.pool.submit(self._build, job.id)
        return job

    def _build(self, job_id):
        with self.archive.ledger.connect() as db:
            row = db.execute(
                "SELECT mission, snapshot FROM telemetry_jobs WHERE id=?", (job_id,)
            ).fetchone()
        if not row:
            return
        mission_id, snapshot = row
        job = self._read(mission_id, job_id)
        if job.state not in ("queued", "preparing"):
            return
        job.state, job.started_at = "preparing", self.clock()
        self._write(job)
        temporary = self.directory / (job.id + ".tmp")
        try:
            data = json.loads(snapshot)
            payload = build_telemetry_package(
                mission_id, data["captures"], allow_partial=data["allow_partial"]
            )
            with temporary.open("wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            with self.archive.ledger.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                current = ExportPreparation.model_validate_json(
                    db.execute(
                        "SELECT payload FROM telemetry_jobs WHERE id=?", (job.id,)
                    ).fetchone()[0]
                )
                if current.state == "cancelled" or self.clock() >= job.deadline:
                    job.state = (
                        "cancelled" if current.state == "cancelled" else "failed"
                    )
                    job.error_code = (
                        "cancelled" if current.state == "cancelled" else "deadline"
                    )
                else:
                    temporary.replace(self.directory / (job.id + ".zip"))
                    job.state, job.finished_at, job.expires_at = (
                        "ready",
                        self.clock(),
                        self.clock() + 1800,
                    )
                    job.download_url = f"/api/v2/missions/{mission_id}/export-preparations/{job.id}/download"
                db.execute(
                    "UPDATE telemetry_jobs SET payload=? WHERE id=?",
                    (job.model_dump_json(), job.id),
                )
        except (ValueError, OSError) as error:
            job.state, job.error_code = "failed", type(error).__name__
            self._write(job)
        finally:
            temporary.unlink(missing_ok=True)

    def status(self, mission_id, job_id):
        job = self._read(mission_id, job_id)
        if job.state == "ready" and self.clock() >= job.expires_at:
            job.state = "expired"
            job.download_url = None
            self._write(job)
            (self.directory / (job.id + ".zip")).unlink(missing_ok=True)
        return job

    def cancel(self, mission_id, job_id):
        job = self.status(mission_id, job_id)
        if job.state in ("queued", "preparing"):
            job.state = "cancelled"
            self._write(job)
        return job

    def open_download(self, mission_id, job_id):
        job = self.status(mission_id, job_id)
        if job.state == "expired":
            raise TimeoutError("Telemetry download expired")
        if job.state != "ready":
            raise ValueError("Telemetry preparation is not ready")
        return MissionPackageDownload(
            (self.directory / (job.id + ".zip")).open("rb"), None
        )

    def close(self):
        self.pool.shutdown(wait=True, cancel_futures=True)
