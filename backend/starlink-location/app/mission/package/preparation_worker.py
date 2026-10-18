"""Elected worker owns export assembly and crash recovery through cleanup."""

import logging
import os
import sqlite3
import time

from filelock import FileLock, Timeout

from app.mission.exporter.export_cancel import ExportCancelled
from app.mission.slide_cache.capture import capture_is_current

from .preparation_store import TERMINAL
from .streams import iter_zip_blocks

logger = logging.getLogger(__name__)


class JobCancel:
    def __init__(self, service, job, raw):
        self.service, self.job, self.raw = service, job, raw
        self.reason = None

    def is_set(self):
        service = self.service
        if (
            service.stop.is_set()
            or service.jobs.read(self.job.mission_id, self.job.id).state == "cancelled"
        ):
            self.reason = "cancelled"
        elif service.clock() >= self.job.deadline:
            self.reason = "deadline"
        elif (
            not capture_is_current(self.raw)
            or self.raw.renderer_revision != service.capture_revision()
        ):
            self.reason = "superseded"
        return self.reason is not None

    def wait(self, seconds):
        until = time.monotonic() + seconds
        while not self.is_set() and time.monotonic() < until:
            self.service.stop.wait(min(0.05, max(0, until - time.monotonic())))
        return self.is_set()


class PreparationWorker:
    def recover(self):
        # The elected worker alone can recover an abandoned assembly.
        for job in self.jobs.all():
            if job.state == "preparing":
                self.finish(job, "failed", "runtime")
                self.path(job.id).unlink(missing_ok=True)
            elif job.state == "ready":
                if not self.path(job.id).exists():
                    self.jobs.discard_archive(job.id)
                    self.jobs.write(
                        job.model_copy(
                            update={
                                "state": "failed",
                                "stage": "failed",
                                "error_code": "runtime",
                            }
                        )
                    )
                else:
                    self.status(job.mission_id, job.id)
            elif job.state in TERMINAL:
                self.jobs.discard_archive(job.id)
        for partial in self.artifacts.glob("*.part"):
            partial.unlink()

    def stage(self, job, stage):
        with self.guard:
            current = self.jobs.read(job.mission_id, job.id)
            if current.state not in TERMINAL and current.stage != stage:
                now = self.clock()
                timings = dict(current.stage_timings)
                timings[current.stage] = max(
                    0, now - (current.stage_started_at or current.started_at or now)
                )
                self.jobs.write_pending(
                    current.model_copy(
                        update={
                            "stage": stage,
                            "stage_started_at": now,
                            "stage_timings": timings,
                        }
                    )
                )

    def work(self, job):
        raw = self.captures[job.id]
        cancel = JobCancel(self, job, raw)
        partial = self.path(job.id).with_suffix(".part")
        try:
            if cancel.is_set():
                raise ExportCancelled("Export preparation cancelled")
            if not self.jobs.write_pending(
                job.model_copy(
                    update={
                        "state": "preparing",
                        "stage": "preparing-slides",
                        "started_at": self.clock(),
                        "stage_started_at": self.clock(),
                        "stage_timings": dict(
                            job.stage_timings,
                            queue=max(
                                0,
                                self.clock()
                                - job.queued_at
                                - job.stage_timings.get("capture", 0),
                            ),
                        ),
                    }
                )
            ):
                return
            enabled = self.enabled() if callable(self.enabled) else self.enabled
            download = self.builder(
                job.mission_id,
                self.route_manager,
                self.poi_manager,
                enabled=enabled,
                cancel=cancel,
                on_stage=lambda stage: self.stage(job, stage),
            )
            archive = self.jobs.archive(job.id)
            if archive is not None:
                from .operations_archive import append_archive

                try:
                    enhanced = append_archive(
                        download.stream,
                        archive,
                        planning_fingerprint=self.fingerprint(raw),
                        cancel=cancel,
                    )
                finally:
                    download.stream.close()
                from .customer_artifacts import MissionPackageDownload

                download = MissionPackageDownload(enhanced, download.briefing)
            with download.stream as source, partial.open("xb") as target:
                for block in iter_zip_blocks(source):
                    if cancel.is_set():
                        raise ExportCancelled("Export preparation cancelled")
                    target.write(block)
                target.flush()
                os.fsync(target.fileno())
            with self.guard:
                if cancel.is_set():
                    raise ExportCancelled("Export preparation cancelled")
                partial.replace(self.path(job.id))
                current = self.jobs.read(job.mission_id, job.id)
                now = self.clock()
                outcome = download.briefing
                published = self.jobs.write_pending(
                    current.model_copy(
                        update={
                            "state": "ready",
                            "stage": "ready",
                            "finished_at": now,
                            "expires_at": now + 1800,
                            "stage_timings": dict(
                                current.stage_timings,
                                **{
                                    current.stage: max(
                                        0, now - (current.stage_started_at or now)
                                    )
                                },
                            ),
                            "briefing_status": outcome.status if outcome else None,
                            "warning_code": outcome.warning_code if outcome else None,
                            "download_url": f"/api/v2/missions/{job.mission_id}/export-preparations/{job.id}/download",
                        }
                    )
                )
                if not published:
                    self.path(job.id).unlink(missing_ok=True)
        except ExportCancelled:
            reason = cancel.reason or "cancelled"
            self.finish(
                job,
                reason if reason in {"cancelled", "superseded"} else "failed",
                "deadline" if reason == "deadline" else None,
            )
        except (OSError, ValueError, RuntimeError, KeyError, TypeError, sqlite3.Error):
            logger.exception("Mission export preparation failed")
            self.finish(job, "failed", "runtime")
        finally:
            partial.unlink(missing_ok=True)
            self.captures.pop(job.id, None)
            if self.jobs.read(job.mission_id, job.id).state != "ready":
                self.jobs.discard_archive(job.id)

    def finish(self, job, state, error=None):
        with self.guard:
            current = self.jobs.read(job.mission_id, job.id)
            if current.state != "cancelled":
                self.jobs.write_pending(
                    current.model_copy(
                        update={
                            "state": state,
                            "stage": state,
                            "error_code": error,
                            "finished_at": self.clock(),
                        }
                    )
                )
            self.jobs.discard_archive(job.id)

    def run(self):
        lock = FileLock(str(self.cache.path.with_suffix(".export-assembly.lock")))
        while not self.stop.is_set():
            try:
                self.sweep_captures()
                with lock.acquire(timeout=0):
                    self.recover()
                    while not self.stop.is_set():
                        self.sweep_captures()
                        pending = [j for j in self.jobs.all() if j.state == "queued"]
                        for ready in self.jobs.all():
                            if (
                                ready.state == "ready"
                                and self.clock() >= ready.expires_at
                            ):
                                self.status(ready.mission_id, ready.id)
                        if pending:
                            job = min(pending, key=lambda j: j.queued_at)
                            with self.guard:
                                self.executing.add(job.id)
                            try:
                                raw = self.captures.get(job.id) or self.capture(
                                    job.mission_id
                                )
                                if (
                                    self.fingerprint(raw, self.jobs.archive(job.id))
                                    != job.fingerprint
                                ):
                                    self.finish(job, "superseded")
                                    continue
                                self.captures[job.id] = raw
                                self.work(job)
                            except (
                                OSError,
                                ValueError,
                                RuntimeError,
                                KeyError,
                                sqlite3.Error,
                            ):
                                self.finish(job, "failed", "runtime")
                            finally:
                                with self.guard:
                                    self.executing.discard(job.id)
                                    self.captures.pop(job.id, None)
                        else:
                            self.wake.wait(0.25)
                            self.wake.clear()
            except Timeout:
                self.stop.wait(0.1)
            except (OSError, ValueError, RuntimeError, sqlite3.Error):
                logger.exception("Mission export preparation will recover")
                self.stop.wait(0.25)
