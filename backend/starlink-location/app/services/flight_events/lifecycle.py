"""Application-owned live recording lifecycle and sanitized recovery status."""

import errno
import logging
import os
import sqlite3
import time
from pathlib import Path
from threading import RLock

from app.services.flight_events.live_adapter import FlightEventRuntime

logger = logging.getLogger(__name__)
RECOVERABLE = (OSError, sqlite3.Error, ValueError)
MESSAGES = {
    "storage_permissions": "Check flight archive directory and database permissions for the application user.",
    "storage_path": "Check FLIGHT_ARCHIVE_ROOT is a writable directory on the persistent archive mount.",
    "database": "Check flight archive database health and available storage; preserve existing files.",
    "invalid_policy": "Check FLIGHT_DETECTION_POLICY contains valid detection settings.",
    "storage": "Check flight archive storage availability and free space.",
}


def failure_category(error):
    if isinstance(error, PermissionError) or getattr(error, "errno", None) in (
        errno.EACCES,
        errno.EPERM,
    ):
        return "storage_permissions"
    if isinstance(error, (FileExistsError, NotADirectoryError, FileNotFoundError)):
        return "storage_path"
    if isinstance(error, sqlite3.Error):
        return "database"
    if isinstance(error, ValueError):
        return "invalid_policy"
    return "storage"


class FlightEventLifecycle:
    def __init__(self, state, root=None, *, clock=time.monotonic):
        self.state = state
        self.root = Path(
            root
            if root is not None
            else os.getenv("FLIGHT_ARCHIVE_ROOT", "data/flight-events")
        )
        self.clock = clock
        self.lock = RLock()
        self.mode = "simulation"
        self.closed = False
        self.next_attempt = 0.0
        self.delay = 5.0
        self.failures = {}
        self.state.flight_event_runtime = None

    def reconcile(self, mode):
        with self.lock:
            if self.closed:
                return None
            previous_mode, self.mode = self.mode, mode
            runtime = self.state.flight_event_runtime
            if previous_mode != mode and runtime is not None:
                self._run("detection", runtime.events.break_continuity)
            if mode != "live":
                return None
            if runtime is None and self.clock() >= self.next_attempt:
                try:
                    runtime = FlightEventRuntime(self.root)
                except RECOVERABLE as error:
                    self._failed("initialization", error)
                    self.next_attempt = self.clock() + self.delay
                    self.delay = min(60.0, self.delay * 2)
                else:
                    self.state.flight_event_runtime = runtime
                    self.failures.clear()
                    self.next_attempt = 0.0
                    self.delay = 5.0
            return runtime

    def _failed(self, stage, error):
        category = failure_category(error)
        changed = self.failures.get(stage) != category
        self.failures[stage] = category
        if changed:
            # Never log exception text: validation errors can contain raw env
            # input. Preserve actionable cause, stage and safe SQLite detail.
            logger.warning(
                (
                    "Live recording unavailable"
                    if stage == "initialization"
                    else "Live recording pending recovery"
                ),
                extra={
                    "extra_fields": {
                        "stage": stage,
                        "cause": category,
                        "error": type(error).__name__,
                        "sqlite_error": getattr(error, "sqlite_errorname", None),
                        "errno": getattr(error, "errno", None),
                        "action": MESSAGES[category],
                    }
                },
            )

    def _run(self, stage, action):
        try:
            completed = action()
        except RECOVERABLE as error:
            self._failed(stage, error)
            return False
        if completed is not False:
            self.failures.pop(stage, None)
        return True

    def report_failure(self, stage, error):
        """Read-side storage failures share the same sanitized stage health."""
        with self.lock:
            self._failed(stage, error)

    def tick(self):
        with self.lock:
            self.reconcile(self.mode)
            runtime = self.state.flight_event_runtime if not self.closed else None
            if runtime is not None:
                self._run("maintenance", runtime.tick)

    def process_live(self, telemetry, context, manager, still_current):
        with self.lock:
            runtime = self.state.flight_event_runtime
            if (
                self.closed
                or self.mode != "live"
                or runtime is None
                or not still_current()
            ):
                return
            self._run("samples", lambda: runtime.record_live(telemetry))
            if context is None or not still_current():
                return
            if (
                self._run(
                    "detection",
                    lambda: runtime.observe_live(
                        telemetry, context, recover_capture=False
                    ),
                )
                and still_current()
            ):
                self._run(
                    "detection",
                    lambda: runtime.sync_legacy_phase(
                        manager, context.parent_mission_id, context.leg.id
                    ),
                )

    def status(self):
        with self.lock:
            initialized = self.state.flight_event_runtime is not None
            active = self.mode == "live" and not self.closed
            failures = dict(self.failures)
            cause = next(iter(failures.values()), None)
            state = (
                "closed"
                if self.closed
                else (
                    "inactive"
                    if not active
                    else (
                        "retrying"
                        if not initialized
                        else "degraded" if failures else "ready"
                    )
                )
            )
            return {
                "state": state,
                "mode": self.mode,
                "detection_available": active
                and initialized
                and "detection" not in failures,
                "recording_available": active
                and initialized
                and not any(k in failures for k in ("samples", "maintenance")),
                "history_available": initialized and not self.closed,
                "cause": cause,
                "failures": failures,
                "message": MESSAGES.get(cause) if cause else None,
                "retry_in_seconds": (
                    max(0.0, self.next_attempt - self.clock())
                    if state == "retrying"
                    else None
                ),
            }

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            runtime = self.state.flight_event_runtime
            self.state.flight_event_runtime = None
            if runtime is not None:
                runtime.close()
