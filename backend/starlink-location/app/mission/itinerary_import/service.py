"""Server-owned resumable orchestration; ordinary missions are the only output."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from app.mission.planning.deadlines import run_bounded
from app.mission.planning.journal import Journal, atomic_write, json_bytes
from app.mission.planning.satellites import satellite_options
from app.satellites.rules import ConstraintConfig

from .models import ImportIssue
from .store import TERMINAL, ImportStore


class ImportService:
    def __init__(self, mission_root, route_manager, poi_manager):
        self.mission_root = Path(mission_root).resolve()
        self.route_manager = route_manager
        self.poi_manager = poi_manager
        self.store = ImportStore(self.mission_root / ".itinerary-imports")
        self.journal = Journal(
            self.mission_root, route_manager.routes_dir, poi_manager.pois_file
        )
        self.executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="itinerary-import"
        )
        self.events = {}
        self.futures = {}
        self.guard = threading.RLock()
        self.closed = False
        for op in self.store.pending():
            self.submit(op)

    def environment(self):
        return {
            "satellites": [
                s.model_dump(mode="json")
                for s in satellite_options(self.poi_manager)
                if s.transport == "X" and s.eligible
            ],
            "constraints": asdict(ConstraintConfig()),
        }

    def check_environment(self, prepared):
        if prepared["environment"] != self.environment():
            raise ValueError("Satellite configuration changed; retry the import")

    def start(self, pdf, kmls, idempotency_key, mission_id=None):
        with self.guard:
            if self.closed:
                raise RuntimeError("Import service is shutting down")
            retained_pdf = bool(mission_id and not pdf)
            if retained_pdf:
                import hashlib

                from app.mission import storage

                with storage.get_active_leg_lock():
                    current = storage.load_mission_v2(mission_id)
                    if not current:
                        raise ValueError("Mission not found")
                    records = current.metadata.get("itinerary_import", {}).get(
                        "source_records", []
                    )
                    source = next(
                        (s for s in reversed(records) if s["kind"] == "itinerary_pdf"),
                        None,
                    )
                    if source is None:
                        raise ValueError("Upload an itinerary PDF")
                    from app.mission.itinerary_import.provenance import imported_sources

                    reference = next(
                        s for s in imported_sources(current) if s.id == source["id"]
                    )
                    pdf = (
                        self.mission_root / ".planning" / reference.owned_relative_path
                    ).read_bytes()
                    if hashlib.sha256(pdf).hexdigest() != reference.content_hash:
                        raise ValueError("Retained itinerary changed")
            op = self.store.create(pdf, kmls, idempotency_key, mission_id)
            if retained_pdf and current.metadata["itinerary_import"].get(
                "pending_legs"
            ):
                payload = self.store.payload(op.id)
                payload["pending_legs"] = current.metadata["itinerary_import"][
                    "pending_legs"
                ]
                atomic_write(
                    self.store.directory(op.id) / "input.json", json_bytes(payload)
                )
            if op.state in {"queued", "running"}:
                self.submit(op)
            return op

    def submit(self, op):
        with self.guard:
            if op.id in self.futures and not self.futures[op.id].done():
                self.futures[op.id].add_done_callback(lambda _: self.resubmit(op.id))
                return
            self.events[op.id] = threading.Event()
            self.futures[op.id] = self.executor.submit(self.run, op.id)

    def resubmit(self, id):
        with self.guard:
            if not self.closed and self.store.read(id).state == "queued":
                self.submit(self.store.read(id))

    def stage(self, op, stage):
        updated = self.store.update(op.id, op.generation, stage=stage)
        op.generation = updated.generation
        op.stage = stage

    def bounded(self, fn, args, op, limit=None):
        remaining = (op.deadline - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 0:
            raise TimeoutError("Import deadline exceeded")
        return run_bounded(
            fn,
            args,
            min(remaining, limit) if limit else remaining,
            cancel_event=self.events[op.id],
        )

    def commit_revision(self, id, generation, resolutions):
        from .revisions import commit_revision

        return commit_revision(self, id, generation, resolutions)

    def read(self, id):
        return self.store.read(id)

    def run(self, id):
        from .commit import commit_initial
        from .pipeline import prepare

        try:
            op = self.store.read(id)
            if op.state in TERMINAL:
                return
            op = self.store.update(id, op.generation, state="running")
            prepared, issues = prepare(self, op)
            if issues:
                self.store.update(
                    id,
                    op.generation,
                    state="needs_input",
                    issues=issues,
                    details=(
                        json.loads(
                            (self.store.directory(id) / "review.json").read_bytes()
                        )
                        if (self.store.directory(id) / "review.json").exists()
                        else {}
                    ),
                )
                return
            atomic_write(
                self.store.directory(id) / "prepared.json", json_bytes(prepared)
            )
            if op.revision:
                from .revisions import stage_revision

                stage_revision(self, op, prepared)
            else:
                commit_initial(self, op, prepared)
        except Exception as exc:  # noqa: BLE001 - safe persisted operation boundary
            import traceback

            atomic_write(
                self.store.directory(id) / "failure.txt",
                traceback.format_exc().encode(),
            )
            op = self.store.read(id)
            if op.state not in TERMINAL:
                # Source contents and stack traces must never appear in the API.
                code = getattr(exc, "code", "import_failed")
                state = (
                    "failed"
                    if isinstance(exc, TimeoutError) or "deadline" in code
                    else "needs_input"
                )
                self.store.update(
                    id,
                    op.generation,
                    state=state,
                    issues=[
                        ImportIssue(
                            code=code,
                            message="Import could not complete. Correct the source or retry.",
                        )
                    ],
                    error=code,
                )

    def resolve(self, id, generation, choices):
        with self.guard, self.store.lock:
            op = self.store.read(id)
            if op.generation != generation or op.state != "needs_input":
                raise ValueError("Import generation is stale")
            payload = self.store.payload(id)
            payload["choices"] = {**payload.get("choices", {}), **choices}
            atomic_write(self.store.directory(id) / "input.json", json_bytes(payload))
            op = self.store.update(
                id, generation, state="queued", issues=[], error=None
            )
            self.submit(op)
            return op

    def cancel(self, id):
        with self.guard, self.store.lock:
            op = self.store.read(id)
            if op.state in TERMINAL:
                return op
            self.events.setdefault(id, threading.Event()).set()
            return self.store.update(id, op.generation, state="cancelled")

    def close(self):
        with self.guard:
            self.closed = True
            for event in self.events.values():
                event.set()
        self.executor.shutdown(wait=True, cancel_futures=True)
