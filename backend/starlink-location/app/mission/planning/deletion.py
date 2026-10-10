"""Durable, ownership-checked retry authority for managed mission deletion."""

import hashlib
import json
import sqlite3
import stat
from pathlib import Path
from typing import Literal

from filelock import FileLock
from pydantic import BaseModel, ConfigDict

from app.mission import storage
from app.mission.models import Mission
from app.mission.slide_cache.store import SlideStore

from .errors import PlanningFailure, conflict
from .journal import atomic_write, json_bytes
from .models import PlanningManifest
from .sources import SourceStore, _records, source_closure


class DeletionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    owner: str
    root: str
    routes_root: str
    mission: Mission
    files: dict[str, str]
    directories: list[str]
    pois_path: str
    pois: dict[str, dict]
    cache_path: str
    cache: dict[str, str]


def _io(path, operation):
    """Only transient filesystem failures are retryable; validation stays distinct."""
    try:
        return operation()
    except OSError as exc:
        raise _incomplete([exc.filename or path]) from exc


def _read_bytes(path):
    return _io(path, path.read_bytes)


def _canonical(path):
    path = Path(path)
    if _io(path, path.resolve) != path:
        raise ValueError(f"Owned deletion path contains an alias: {path}")
    return path


def record_path(sources, mission_id):
    if (
        not mission_id
        or mission_id in {".", ".."}
        or any(c in mission_id for c in "/\\\x00")
    ):
        raise ValueError("Invalid deletion owner")
    return _canonical(sources.root / "deletions" / f"{mission_id}.json")


def load_record(sources, mission_id):
    path = record_path(sources, mission_id)
    if not _io(path, path.exists):
        return None
    record = DeletionRecord.model_validate_json(_read_bytes(path))
    if (
        record.owner != mission_id
        or record.mission.id != mission_id
        or record.root != str(sources.root.parent)
        or record.routes_root != str(sources.routes_dir)
    ):
        raise ValueError("Deletion authority does not match its verified owner/root")
    source_closure(
        record.mission,
        PlanningManifest.model_validate(record.mission.metadata["itinerary_planning"]),
    )
    directory = _canonical(sources.root.parent / mission_id)
    for relative in [*record.files, *record.directories]:
        target = directory / relative
        if (
            Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or not target.is_relative_to(directory)
        ):
            raise ValueError("Invalid recorded owned deletion path")
        _canonical(target)
    return record


def ownership_mission(sources, mission_id):
    record = load_record(sources, mission_id)
    return (
        record.mission
        if record
        else _io(
            storage.get_mission_file_path(mission_id),
            lambda: storage.load_mission_v2(mission_id),
        )
    )


def verified_store(route_manager, poi_manager):
    """Reuse only the manager's verified bound context; never a global singleton."""
    from .store import PlanningStore

    sources = getattr(
        getattr(route_manager, "_profile_resolver", None), "__self__", None
    )
    prior = sources._store if isinstance(sources, SourceStore) else None
    if (
        prior is not None
        and prior.route_manager is route_manager
        and prior.poi_manager is poi_manager
        and prior.root == storage.MISSIONS_DIR.resolve()
    ):
        sources.bind_store(prior)
        return prior
    store = PlanningStore(storage.MISSIONS_DIR, route_manager, poi_manager)
    if prior is not None:
        store.planning_constraints_provider = prior.planning_constraints_provider
    return store


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _cache_hash(record):
    return _hash(
        json.dumps(record, sort_keys=True, default=lambda value: value.hex()).encode()
    )


def _owned_pois(mission, records):
    from app.mission.routes_v2 import _endpoint_marker

    manifest = PlanningManifest.model_validate(mission.metadata["itinerary_planning"])
    legs = mission.legs + [
        history.installed_leg
        for history in manifest.leg_history
        if history.installed_leg
    ]
    endpoints = {
        (leg.route_id, _endpoint_marker(leg.id, role))
        for leg in legs
        for role in ("departure", "arrival")
    }
    return {
        key: poi
        for key, poi in records.items()
        if poi.get("mission_id") == mission.id
        and (
            poi.get("generated_source") == "mission-timeline"
            or (poi.get("route_id"), poi.get("description")) in endpoints
        )
    }


def _read_pois(path):
    try:
        with FileLock(str(path) + ".lock"):
            data = path.read_bytes()
    except OSError as exc:
        raise _incomplete([path]) from exc
    return json.loads(data).get("pois", {})


def _tree(directory):
    _canonical(directory)
    files, directories = {}, [""]
    pending = [directory] if _io(directory, directory.exists) else []
    while pending:
        parent = pending.pop()
        # Explicit traversal propagates unreadable directories; rglob can skip them.
        children = _io(parent, lambda parent=parent: list(parent.iterdir()))
        for path in children:
            _canonical(path)
            relative = str(path.relative_to(directory))
            mode = _io(path, path.stat).st_mode
            if stat.S_ISDIR(mode):
                directories.append(relative)
                pending.append(path)
            elif stat.S_ISREG(mode):
                files[relative] = _hash(_read_bytes(path))
            else:
                raise ValueError(f"Unexpected owned deletion file type: {path}")
    return files, directories


def _cache_records(path, owner):
    try:
        return SlideStore(path).records(owner) if path.exists() else {}
    except (OSError, sqlite3.OperationalError) as exc:
        raise _incomplete([path]) from exc


def _subset(current, expected):
    if any(
        key not in expected or expected[key] != value for key, value in current.items()
    ):
        raise conflict(
            "Owned deletion found changed or newly added work; preserve it and reload."
        )


def _incomplete(paths):
    paths = tuple(sorted(set(map(str, paths))))
    error = PlanningFailure(
        503,
        "owned_delete_incomplete",
        "Remaining owned cleanup paths: " + ", ".join(paths),
        action="retry_delete",
        retryable=True,
    )
    error.remaining_paths = paths
    return error


def delete_owned(store, mission_id, run_service=None):
    """Caller holds global then mission gate for the entire attempt."""
    sources = store.sources
    sources.bind_store(store)
    mission = ownership_mission(sources, mission_id)
    if mission is None:
        raise ValueError("Owned deletion authority is unavailable")
    manifest = PlanningManifest.model_validate(mission.metadata["itinerary_planning"])
    references = source_closure(mission, manifest)
    active = store.route_manager.get_active_route_id()
    if any(leg.is_active for leg in mission.legs) or (
        active
        and any(
            item.get("route_id") == active
            or (item.get("kind") == "route_kml" and item.get("id") == active)
            for item in _records(mission.model_dump(mode="json"))
        )
    ):
        raise PlanningFailure(
            409,
            "ACTIVE_ROUTE_DELETION_FORBIDDEN",
            "A retained route is active.",
            action="Deactivate the selected route and mission legs before deleting the mission.",
        )
    sources.validate_release(mission_id, references)
    directory = _canonical(store.root / mission_id)
    files, directories = _tree(directory)
    path = record_path(sources, mission_id)
    pois_path = _canonical(store.poi_manager.pois_file)
    cache_path = _canonical(store.root / ".slide-cache" / "slides.sqlite3")
    pois = _owned_pois(mission, _read_pois(pois_path))
    cache = {
        key: _cache_hash(value)
        for key, value in _cache_records(cache_path, mission_id).items()
    }
    record = load_record(sources, mission_id)
    if record is None:
        record = DeletionRecord(
            owner=mission_id,
            root=str(store.root),
            routes_root=str(sources.routes_dir),
            mission=mission,
            files=files,
            directories=directories,
            pois_path=str(pois_path),
            pois=pois,
            cache_path=str(cache_path),
            cache=cache,
        )
        try:
            atomic_write(path, record.model_dump_json().encode())
        except OSError as exc:
            raise _incomplete([path]) from exc
    else:
        if record.pois_path != str(pois_path) or record.cache_path != str(cache_path):
            raise ValueError("Deletion cleanup scope changed")
        _subset(files, record.files)
        if not set(directories).issubset(record.directories):
            raise conflict("Owned deletion found a newly added directory")
        _subset(pois, record.pois)
        _subset(cache, record.cache)
    # The persisted authority survives every subsequent partial cleanup.
    sources.release_owned(mission_id, references)
    for source in references:
        if (
            source.kind == "route_kml"
            and not (sources.routes_dir / f"{source.id}.kml").exists()
        ):
            store.route_manager._routes.pop(source.id, None)
    remaining = []
    if run_service:
        try:
            run_service.cancel_owned(mission_id, None, "Deleted")
        except (OSError, RuntimeError):
            remaining.append(path)
    try:
        with FileLock(str(pois_path) + ".lock"):
            data = json.loads(pois_path.read_bytes())
            current = _owned_pois(mission, data.get("pois", {}))
            _subset(current, record.pois)
            # Unrelated/manual records, even interleaved writes, are retained.
            data["pois"] = {
                key: value
                for key, value in data.get("pois", {}).items()
                if key not in current
            }
            if current:
                atomic_write(pois_path, json_bytes(data))
        store.poi_manager.reload_pois()
    except (OSError, RuntimeError):
        remaining.append(pois_path)
    try:
        if cache_path.exists():
            cache_store = SlideStore(cache_path)
            with cache_store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                rows = db.execute(
                    "SELECT * FROM slides WHERE mission=?", (mission_id,)
                ).fetchall()
                _subset(
                    {row["leg"]: _cache_hash(dict(row)) for row in rows}, record.cache
                )
                db.execute("DELETE FROM slides WHERE mission=?", (mission_id,))
    except (OSError, sqlite3.Error):
        remaining.append(cache_path)
    for relative in record.files:
        target = directory / relative
        try:
            target.unlink(missing_ok=True)
        except OSError:
            remaining.append(target)
    for relative in sorted(
        record.directories, key=lambda item: len(Path(item).parts), reverse=True
    ):
        target = directory / relative
        try:
            if target.exists() and not any(target.iterdir()):
                target.rmdir()
        except OSError:
            remaining.append(target)
    if remaining:
        raise _incomplete(remaining)
    if directory.exists():
        raise conflict(
            "Owned deletion found new work during cleanup; preserve it and reload."
        )
    try:
        path.unlink()
    except OSError as exc:
        raise _incomplete([path]) from exc
