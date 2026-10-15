"""One elected coordinator, latest-input-wins jobs, and application lifecycle."""

import logging
import sqlite3
import sys
import threading
import time

from filelock import FileLock, Timeout

from app.mission import storage
from app.mission.exporter.customer_limits import SLIDE_WALL_SECONDS
from app.mission.exporter.customer_runtime import (
    RendererFailure,
    _private_staging,
    run_owned_renderer,
)
from app.mission.exporter.export_cancel import ExportCancelled

from .identity import effective, renderer_revision
from .store import default_store

logger = logging.getLogger(__name__)
_runtime = None


def saved_mission(previous, mission):
    """Cancel changed legs promptly; a committed mission is the durable queue."""
    before = previous.model_dump(mode="json") if previous else {"legs": []}
    after = mission.model_dump(mode="json")
    old = {leg["id"]: effective(leg) for leg in before["legs"]}
    parent_changed = effective(
        {k: v for k, v in before.items() if k != "legs"}
    ) != effective({k: v for k, v in after.items() if k != "legs"})
    composition_changed = list(old) != [leg["id"] for leg in after["legs"]]
    changed = [
        leg["id"]
        for leg in after["legs"]
        if parent_changed or composition_changed or old.get(leg["id"]) != effective(leg)
    ]
    try:
        cache = default_store()
        cache.invalidate(mission.id, changed)
        cache.remove_except(mission.id, [leg["id"] for leg in after["legs"]])
    except (OSError, sqlite3.Error):
        # Data persistence has succeeded. Reconciliation repairs optional cache
        # failures instead of reporting an unsuccessful save to the customer.
        logger.exception("Slide invalidation deferred to reconciliation")
    if _runtime:
        _runtime.wake.set()


def reconcile(
    mission_id, route_manager, poi_manager, cache, revision, *, retry=False, memo=None
):
    from app.mission.exporter.snapshot_inputs import SnapshotCaptureError

    from .capture import capture_is_current, capture_raw, normalize_capture
    from .persisted_pois import persisted_pois

    poi_manager = persisted_pois(poi_manager)
    for attempt in range(2):
        raw = capture_raw(mission_id, route_manager, poi_manager, revision)
        normalized_now = False
        normalized_at = time.monotonic()
        try:
            cached = memo.get(mission_id) if memo is not None else None
            if (
                cached
                and cached[0].dependency_token == raw.dependency_token
                and cached[0].renderer_revision == revision
                and time.monotonic() - cached[1] < 30
            ):
                metadata, sources, warnings, normalized = cached[2]
            else:
                normalized_now = True
                metadata, sources, warnings, normalized = normalize_capture(raw)
                if memo is not None:
                    memo[mission_id] = (
                        raw,
                        time.monotonic(),
                        (metadata, sources, warnings, normalized),
                    )
        except SnapshotCaptureError:
            if not attempt:
                continue
            raise
        normalized_seconds = time.monotonic() - normalized_at
        queued_at = time.monotonic()
        with storage.get_active_leg_lock():
            if not capture_is_current(raw):
                continue
            tokens = {
                leg: cache.reserve(mission_id, leg, fingerprint, retry=retry)
                for leg, (fingerprint, _) in normalized.items()
            }
            cache.remove_except(mission_id, list(normalized))
        for leg, (_, inputs) in normalized.items():
            cache.attach_inputs(mission_id, leg, tokens[leg], inputs)
        if normalized_now:
            logger.info(
                "Customer preparation stages",
                extra={
                    "extra_fields": {
                        "mission_id": mission_id,
                        "stage_timings": dict(
                            raw.stage_timings,
                            normalization=normalized_seconds,
                            queue=time.monotonic() - queued_at,
                        ),
                    }
                },
            )
        return (
            metadata,
            sources,
            warnings,
            {leg: value[0] for leg, value in normalized.items()},
        )
    raise SnapshotCaptureError("Source inputs changed during queue publication")


class JobCancellation:
    def __init__(self, coordinator, job):
        self.coordinator, self.job = coordinator, job

    def is_set(self):
        owner, job = self.coordinator, self.job
        if owner.stop.is_set():
            return True
        return not owner.cache.current(job["mission"], job["leg"], job["token"])

    def wait(self, seconds):
        self.coordinator.stop.wait(seconds)
        return self.is_set()


class SlideCoordinator:
    def __init__(self, route_manager, poi_manager, *, cache=None):
        self.route_manager, self.poi_manager = route_manager, poi_manager
        self.cache = cache or default_store()
        self._captures = {}
        self.revision = renderer_revision()
        self.stop, self.wake = threading.Event(), threading.Event()
        self.thread = threading.Thread(
            target=self.run, name="customer-pdf-coordinator", daemon=True
        )

    def start(self):
        self.thread.start()

    def close(self):
        self.stop.set()
        self.wake.set()
        self.thread.join(timeout=25)
        if self.thread.is_alive():
            raise RuntimeError("Customer PDF coordinator did not stop")
        global _runtime
        if _runtime is self:
            _runtime = None

    def reconcile_all(self):
        self.revision = renderer_revision()
        missions = {p.parent.name for p in storage.MISSIONS_DIR.glob("*/mission.json")}
        for mission in set(self.cache.missions()) - missions:
            self.cache.remove_except(mission, [])
        for mission in sorted(missions):
            if self.stop.is_set():
                break
            try:
                reconcile(
                    mission,
                    self.route_manager,
                    self.poi_manager,
                    self.cache,
                    self.revision,
                    memo=self._captures,
                )
            except (OSError, ValueError, RuntimeError, sqlite3.Error):
                logger.exception("Customer PDF reconciliation deferred for %s", mission)
                # Never deliver a ready artifact whose inputs could not be checked.
                self.cache.invalidate(mission, list(self.cache.status_records(mission)))

    def run_job(self, job):
        cancel = JobCancellation(self, job)
        snapshot = None
        try:
            with _private_staging() as root:
                # Record and supervise Python and all Node/browser descendants.
                (root / "inputs.json").write_bytes(job["inputs"])
                render_started = time.monotonic()
                try:
                    code = run_owned_renderer(
                        [
                            sys.executable,
                            "-m",
                            "app.mission.slide_cache.worker",
                            str(root),
                            job["fingerprint"],
                            str(self.cache.path.with_suffix(".worker.lock")),
                        ],
                        root,
                        cancel=cancel,
                        wall_seconds=SLIDE_WALL_SECONDS,
                        kill_grace_seconds=5,
                    )
                finally:
                    logger.info(
                        "Customer renderer stages",
                        extra={
                            "extra_fields": {
                                "mission_id": job["mission"],
                                "leg_id": job["leg"],
                                "stage_timings": {
                                    "render": time.monotonic() - render_started
                                },
                            }
                        },
                    )
                    if (root / "snapshot.json").exists():
                        snapshot = (root / "snapshot.json").read_bytes()
                if code:
                    raise RendererFailure("runtime")
                import json

                result = json.loads((root / "result.json").read_text())
                snapshot = (root / "snapshot.json").read_bytes()
                pdf = (root / "pages.pdf").read_bytes() if result["included"] else None
                evidence = (
                    (root / "evidence.json").read_bytes()
                    if result["included"]
                    else None
                )
                # Full reconciliation happens once before publication, never in polling.
                self.reconcile_all()
                if cancel.is_set():
                    raise ExportCancelled("Superseded slide generation")
                self.cache.publish(
                    job["mission"],
                    job["leg"],
                    job["token"],
                    snapshot,
                    pdf,
                    evidence,
                    result["warning"],
                )
        except ExportCancelled:
            # Shutdown work must remain recoverable; superseded work has a new token.
            return
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            warning = exc.code if isinstance(exc, RendererFailure) else "runtime"
            self.cache.publish(
                job["mission"], job["leg"], job["token"], snapshot, None, None, warning
            )
            logger.exception(
                "Customer PDF preparation failed for %s/%s", job["mission"], job["leg"]
            )

    def run(self):
        lock = FileLock(str(self.cache.path.with_suffix(".coordinator.lock")))
        while not self.stop.is_set():
            try:
                with lock.acquire(timeout=0):
                    # A surviving worker owns a second lock through its cleanup.
                    # Do not recover/dispatch replacement work before it exits.
                    worker_lock = FileLock(
                        str(self.cache.path.with_suffix(".worker.lock"))
                    )
                    while not self.stop.is_set():
                        try:
                            with worker_lock.acquire(timeout=0):
                                break
                        except Timeout:
                            self.stop.wait(0.1)
                    if self.stop.is_set():
                        break
                    self.cache.recover()
                    while not self.stop.is_set():
                        self.reconcile_all()
                        if self.stop.is_set():
                            break
                        job = self.cache.claim()
                        if job:
                            self.run_job(job)
                        else:
                            self.wake.wait(1)
                            self.wake.clear()
            except Timeout:
                self.stop.wait(1)
            except (OSError, ValueError, RuntimeError, sqlite3.Error):
                logger.exception("Customer PDF coordinator will recover")
                self.stop.wait(1)


def start_runtime(route_manager, poi_manager):
    global _runtime
    _runtime = None
    runtime = SlideCoordinator(route_manager, poi_manager)
    runtime.start()
    _runtime = runtime
    return _runtime
