"""Immutable upload staging, durable ownership inventory and strict profiles."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from app.mission.models import Mission
from app.mission.storage import planning_read_gate
from app.services.kml_parser import KMLParseError

from .errors import PlanningFailure
from .journal import atomic_write, json_bytes
from .models import PlanningManifest, SourceRevision


def source_closure(
    mission: Mission, manifest: PlanningManifest | None
) -> tuple[SourceRevision, ...]:
    """All accepted revisions remain live provenance, including retired history."""
    if manifest is None:
        return ()
    sources = {}
    for source in manifest.source_revisions:
        if source.owner != mission.id or source.expires_at is not None:
            raise ValueError("Accepted source ownership is inconsistent")
        suffix = "pdf" if source.kind == "itinerary_pdf" else "kml"
        if source.owned_relative_path != f"sources/{source.id}.{suffix}":
            raise ValueError("Invalid accepted source path")
        if source.id in sources and sources[source.id] != source:
            raise ValueError("Conflicting source revisions")
        sources[source.id] = source
    for record in _records(manifest.storage_record()):
        if "source_id" in record and "content_hash" in record:
            source = sources.get(record["source_id"])
            if source is None or source.content_hash != record["content_hash"]:
                raise ValueError("Planning graph references a missing source revision")
        for source_id in record.get("source_ids", []):
            if source_id not in sources:
                raise ValueError("History references a missing source revision")
    return tuple(sources.values())


def _records(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _records(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _records(child)


def route_references(route_id, *, excluding_mission=None):
    """Call under the global gate; inventory includes every retained graph node."""
    from app.mission import storage

    result = []
    for parent in storage.list_mission_metadata_v2():
        if parent.id == excluding_mission:
            continue
        mission = storage.load_mission_v2(parent.id)
        if any(
            record.get("route_id") == route_id
            or (record.get("kind") == "route_kml" and record.get("id") == route_id)
            for record in _records(mission.model_dump(mode="json"))
        ):
            result.append(parent.id)
    return tuple(result)


def guard_route_delete(route_id, routes_dir):
    from fastapi import HTTPException

    from app.mission import storage

    owners = route_references(route_id)
    inventory = (
        SourceStore(storage.MISSIONS_DIR, routes_dir).root
        / "inventory"
        / f"{route_id}.json"
    )
    if owners or inventory.exists():
        raise HTTPException(
            409,
            detail={
                "code": "mission_route_retained",
                "message": "Route is retained by a mission",
                "mission_ids": list(owners),
                "action": "Delete the owning mission to release retained route sources.",
            },
        )


class SourceStore:
    def __init__(self, root: Path, routes_dir: Path):
        self.root = Path(root).resolve() / ".planning"
        self.routes_dir = Path(routes_dir).resolve()
        self._cleanup_candidates = None
        self._store = None

    def bind_store(self, store):
        if (
            store.sources is not self
            or store.root != self.root.parent
            or Path(store.route_manager.routes_dir).resolve() != self.routes_dir
        ):
            raise ValueError("Invalid source commit context")
        if self._store is not None and self._store is not store:
            raise ValueError("Source store already has a commit context")
        self._store = store

    @planning_read_gate
    def stage(
        self, data: bytes, kind: str, owner: str | None, filename: str
    ) -> SourceRevision:
        if kind not in {"pdf", "kml"}:
            raise ValueError("Unsupported source kind")
        if kind == "pdf" and len(data) > 10 * 1024 * 1024:
            raise PlanningFailure(422, "upload_too_large", "Upload exceeds 10 MiB")
        self.cleanup_expired(limit=100)
        source_id = str(uuid4())
        source = SourceRevision(
            id=source_id,
            owner=owner or source_id,
            kind="itinerary_pdf" if kind == "pdf" else "route_kml",
            filename=Path(filename).name,
            content_hash=hashlib.sha256(data).hexdigest(),
            owned_relative_path=f"staging/{source_id}.{kind}",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        atomic_write(self.path(source), data)
        atomic_write(
            self.root / "staging" / f"{source.id}.source.json",
            json_bytes(source.storage_record()),
        )
        return source

    def path(self, source):
        path = self.root / source.owned_relative_path
        if path.resolve() != path or not path.is_relative_to(self.root):
            raise ValueError("Invalid owned source path")
        return path

    def preview_path(self, preview_id):
        # Public resource selectors never become arbitrary filesystem paths.
        try:
            from uuid import UUID

            UUID(preview_id)
        except (ValueError, TypeError):
            raise PlanningFailure(404, "preview_not_found", "Preview not found")
        return self.root / "staging" / f"{preview_id}.preview.json"

    @planning_read_gate
    def save_preview(self, preview_id, record):
        atomic_write(self.preview_path(preview_id), json_bytes(record))

    @planning_read_gate
    def get_preview(self, preview_id):
        path = self.preview_path(preview_id)
        if not path.exists():
            if not any(
                (self.root / "sources" / f"{preview_id}.{suffix}").exists()
                for suffix in ("pdf", "kml")
            ):
                raise PlanningFailure(404, "preview_not_found", "Preview not found")
            raise PlanningFailure(
                409,
                "preview_expired",
                "Preview unavailable or already accepted",
                action="reupload",
            )
        record = json.loads(path.read_bytes())
        if record.get("expired") is True:
            raise PlanningFailure(
                409, "preview_expired", "Preview expired", action="reupload"
            )
        source = SourceRevision.model_validate(record["source"])
        if source.expires_at is None or source.expires_at <= datetime.now(timezone.utc):
            self.expire(source)
            raise PlanningFailure(
                409, "preview_expired", "Preview expired", action="reupload"
            )
        return record, source

    @planning_read_gate
    def expire(self, source):
        # Retain only resource status, never expired source or parsed content.
        self.save_preview(source.id, {"expired": True})
        for path in (
            self.path(source),
            self.root / "staging" / f"{source.id}.source.json",
        ):
            path.unlink(missing_ok=True)

    @planning_read_gate
    def discard(self, source):
        if source.owned_relative_path.startswith("staging/"):
            for path in (
                self.path(source),
                self.root / "staging" / f"{source.id}.source.json",
                self.preview_path(source.id),
            ):
                path.unlink(missing_ok=True)

    @planning_read_gate
    def cleanup_expired(self, *, limit=None):
        # Retain the iterator between bounded batches so fresh descriptors at the
        # front cannot indefinitely hide abandoned sources later in the sweep.
        if limit is None or self._cleanup_candidates is None:
            self._cleanup_candidates = (self.root / "staging").glob("*.source.json")
        count = 0
        while limit is None or count < limit:
            path = next(self._cleanup_candidates, None)
            if path is None:
                self._cleanup_candidates = None
                break
            count += 1
            if not path.exists():
                continue  # Accepted or discarded since this batch was enumerated.
            source = SourceRevision.model_validate_json(path.read_bytes())
            if source.expires_at and source.expires_at <= datetime.now(timezone.utc):
                self.expire(source)

    @planning_read_gate
    def acceptance_snapshot(self, preview_id):
        """Capture immutable input before another acceptance can consume staging."""
        record, source = self.get_preview(preview_id)
        return record, source, self.path(source).read_bytes()

    def descriptor_path(self, route_id):
        return self.routes_dir / f"{route_id}.profile.json"

    def resolve_profile(self, route_id):
        from app.mission.storage import get_active_leg_lock

        with get_active_leg_lock():
            if any((self.root / "journals").glob("*.json")):
                raise KMLParseError("Owned route recovery must finish before loading")
            inventory = self.root / "inventory" / f"{route_id}.json"
            if not inventory.exists():
                return "legacy"
            try:
                owned = json.loads(inventory.read_bytes())
                descriptor = json.loads(self.descriptor_path(route_id).read_bytes())
                expected = {
                    "version": 1,
                    "route_id": route_id,
                    "source_hash": owned["content_hash"],
                    "owner": owned["owner"],
                    "ingestion_profile": "planning_v1",
                }
                if descriptor != expected or owned["id"] != route_id:
                    raise ValueError("Invalid descriptor")
                data = (self.routes_dir / f"{route_id}.kml").read_bytes()
                if hashlib.sha256(data).hexdigest() != owned["content_hash"]:
                    raise ValueError("Owned source content changed")
                return "planning_v1"
            except (OSError, ValueError, KeyError, TypeError) as exc:
                raise KMLParseError(
                    "Invalid owned route profile; explicit recovery required"
                ) from exc

    def acceptance_files(self, source, owner, data):
        suffix = "pdf" if source.kind == "itinerary_pdf" else "kml"
        accepted = source.model_copy(
            update={
                "owner": owner,
                "expires_at": None,
                "owned_relative_path": f"sources/{source.id}.{suffix}",
            }
        )
        if hashlib.sha256(data).hexdigest() != source.content_hash:
            raise PlanningFailure(
                422, "source_changed", "Staged source failed integrity validation"
            )
        files = {self.path(accepted): data}
        if suffix == "kml":
            descriptor = {
                "version": 1,
                "route_id": source.id,
                "source_hash": source.content_hash,
                "owner": owner,
                "ingestion_profile": "planning_v1",
            }
            # Inventory precedes descriptor and route; watcher profile resolution
            # waits on the repository gate until the complete transaction exists.
            files[self.root / "inventory" / f"{source.id}.json"] = json_bytes(
                accepted.storage_record()
            )
            files[self.descriptor_path(source.id)] = json_bytes(descriptor)
            files[self.routes_dir / f"{source.id}.kml"] = data
        files.update(
            {
                self.path(source): None,
                self.root / "staging" / f"{source.id}.source.json": None,
                self.preview_path(source.id): None,
            }
        )
        return accepted, files

    @planning_read_gate
    def release_owned(
        self, mission_id: str, references: tuple[SourceRevision, ...]
    ) -> None:
        """Release verified, unreferenced bytes; retain exact failed paths for retry."""
        from app.mission import storage

        from .models import PlanningManifest

        mission = storage.load_mission_v2(mission_id)
        if mission is None or "itinerary_planning" not in mission.metadata:
            raise ValueError("Owned source release requires its persisted mission")
        accepted = source_closure(
            mission,
            PlanningManifest.model_validate(mission.metadata["itinerary_planning"]),
        )
        if any(source not in accepted for source in references):
            raise ValueError(
                "Source ownership is not established by the owning mission"
            )
        candidates = []
        for source in references:
            if source.owner != mission_id:
                raise ValueError("Cannot release another mission's source")
            suffix = "pdf" if source.kind == "itinerary_pdf" else "kml"
            if source.owned_relative_path != f"sources/{source.id}.{suffix}":
                raise ValueError("Invalid owned source path")
            if source.kind == "route_kml" and route_references(
                source.id, excluding_mission=mission_id
            ):
                continue
            paths = [self.path(source)]
            if source.kind == "route_kml":
                paths.extend(
                    [
                        self.routes_dir / f"{source.id}.kml",
                        self.descriptor_path(source.id),
                        self.root / "inventory" / f"{source.id}.json",
                    ]
                )
            for path in paths:
                if not path.exists():
                    continue
                if path.is_symlink():
                    raise ValueError("Owned source path cannot be a symlink")
                data = path.read_bytes()
                if path.suffix in {".pdf", ".kml"}:
                    if hashlib.sha256(data).hexdigest() != source.content_hash:
                        raise ValueError(f"Owned source changed: {path}")
                elif path == self.descriptor_path(source.id):
                    if json.loads(data) != {
                        "version": 1,
                        "route_id": source.id,
                        "source_hash": source.content_hash,
                        "owner": mission_id,
                        "ingestion_profile": "planning_v1",
                    }:
                        raise ValueError(f"Owned profile changed: {path}")
                elif SourceRevision.model_validate_json(data) != source:
                    raise ValueError(f"Owned inventory changed: {path}")
            candidates.extend(paths)
        remaining = []
        for path in candidates:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                remaining.append(str(path))
        if remaining:
            failure = PlanningFailure(
                503,
                "owned_delete_incomplete",
                "Remaining owned paths: " + ", ".join(remaining),
                action="retry_delete",
                retryable=True,
            )
            failure.remaining_paths = tuple(remaining)
            raise failure
