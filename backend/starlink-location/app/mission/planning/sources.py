"""Immutable upload staging, durable ownership inventory and strict profiles."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from app.mission.storage import planning_read_gate
from app.services.kml_parser import KMLParseError

from .errors import PlanningFailure
from .journal import atomic_write, json_bytes
from .models import SourceRevision


class SourceStore:
    def __init__(self, root: Path, routes_dir: Path):
        self.root = Path(root).resolve() / ".planning"
        self.routes_dir = Path(routes_dir).resolve()
        self._cleanup_candidates = None

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
        path = (self.root / source.owned_relative_path).resolve()
        if not path.is_relative_to(self.root):
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
