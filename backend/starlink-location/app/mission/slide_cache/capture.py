"""Copy committed bytes under the gate; validate and encode after releasing it."""

import time
from dataclasses import asdict, dataclass
from pathlib import Path

from app.mission import storage
from app.mission.exporter.snapshot_inputs import SnapshotCaptureError, canonical_json
from app.mission.models import Mission


def dependency_token(mission_id, route_manager, poi_manager):
    roots = [
        storage.get_mission_directory(mission_id),
        storage.MISSIONS_DIR / ".planning/sources",
        storage.MISSIONS_DIR / ".planning/inventory",
        Path("data/satellites"),
        Path("data/sat_coverage"),
        Path(__file__).resolve().parents[2] / "satellites/assets",
    ]
    if route_manager is not None:
        roots.append(Path(route_manager.routes_dir))
    paths = {p for root in roots for p in root.rglob("*") if p.is_file()}
    if poi_manager is not None and hasattr(poi_manager, "path"):
        paths.add(poi_manager.path)
    elif poi_manager is not None and hasattr(poi_manager, "pois_file"):
        paths.add(Path(poi_manager.pois_file))
    tokens = []
    for path in sorted(paths):
        if path.suffix in {".lock", ".sqlite3"}:
            continue
        stat = path.stat()
        tokens.append(
            (
                str(path),
                stat.st_dev,
                stat.st_ino,
                stat.st_size,
                stat.st_mtime_ns,
                stat.st_ctime_ns,
            )
        )
    from app.satellites.rules import ConstraintConfig
    from app.services.ground_entry_point import get_cached_ground_entry_point

    ground = get_cached_ground_entry_point()
    return tuple(tokens), canonical_json(
        [asdict(ConstraintConfig()), asdict(ground) if ground else None]
    )


@dataclass(frozen=True)
class RawCapture:
    mission_id: str
    metadata: bytes
    legs: tuple[bytes, ...]
    dependency_token: tuple
    route_manager: object
    poi_manager: object
    renderer_revision: str
    stage_timings: tuple[tuple[str, float], ...] = ()


def capture_raw(mission_id, route_manager, poi_manager, revision=""):
    started = time.monotonic()
    with storage.get_active_leg_lock(), storage.get_mission_lock(mission_id):
        captured_at = time.monotonic()
        journals = storage.MISSIONS_DIR / ".planning/journals"
        if journals.exists() and any(journals.glob("*.json")):
            raise SnapshotCaptureError("Planning recovery required before capture")
        path = storage.get_mission_file_path(mission_id)
        if not path.exists():
            raise SnapshotCaptureError(f"Mission {mission_id} not found")
        metadata = path.read_bytes()
        legs = tuple(
            p.read_bytes()
            for p in storage._iter_mission_leg_files(
                storage.get_mission_legs_dir(mission_id)
            )
        )
        token = dependency_token(mission_id, route_manager, poi_manager)
    return RawCapture(
        mission_id,
        metadata,
        legs,
        token,
        route_manager,
        poi_manager,
        revision,
        (
            ("lock_wait", captured_at - started),
            ("raw_capture", time.monotonic() - captured_at),
        ),
    )


def capture_is_current(raw):
    return raw.dependency_token == dependency_token(
        raw.mission_id, raw.route_manager, raw.poi_manager
    )


def normalize_capture(raw, *, persisted=True, fingerprints=True):
    import json

    from app.mission.exporter.snapshot_inputs import _read_dependencies

    from .identity import leg_inputs

    metadata = json.loads(raw.metadata)
    metadata["legs"] = [json.loads(leg) for leg in raw.legs]
    mission = storage._ordered_mission(Mission.model_validate(metadata))
    metadata = canonical_json(mission.model_dump(mode="json"))
    options = {"persisted": True} if persisted else {}
    first = _read_dependencies(mission, raw.route_manager, raw.poi_manager, **options)
    second = _read_dependencies(mission, raw.route_manager, raw.poi_manager, **options)
    if first != second or not capture_is_current(raw):
        raise SnapshotCaptureError("Source inputs changed during capture")
    normalized = (
        {
            leg.id: leg_inputs(metadata, first, leg.id, raw.renderer_revision)
            for leg in mission.legs
        }
        if fingerprints
        else {}
    )
    return metadata, first, (), normalized
