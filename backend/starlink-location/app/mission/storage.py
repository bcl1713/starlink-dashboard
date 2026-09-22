"""Scoped v2 mission storage utilities."""

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock

from app.mission.models import Mission, MissionLeg, MissionLegTimeline

logger = logging.getLogger(__name__)

# Base directory for mission storage
MISSIONS_DIR = Path("data/missions")
TIMELINE_SUFFIX = ".timeline.json"
_active_leg_locks: dict[str, FileLock] = {}
_active_leg_locks_guard = threading.Lock()


def ensure_missions_directory():
    """Ensure the missions directory exists."""
    MISSIONS_DIR.mkdir(parents=True, exist_ok=True)


def get_mission_lock(mission_id: str) -> FileLock:
    """Get a file lock for a mission to prevent concurrent modifications.

    Args:
        mission_id: ID of the mission to lock

    Returns:
        FileLock object
    """
    ensure_missions_directory()
    lock_path = MISSIONS_DIR / f"{mission_id}.lock"
    return FileLock(str(lock_path))


def get_active_leg_lock() -> FileLock:
    """Get the canonical repository-wide v2 active-leg read/write lock.

    FileLock 3.12.0 re-enters only when the same instance is acquired again in
    a thread. Cache the lock by its canonical path rather than relying on the
    newer ``is_singleton`` constructor option.
    """
    ensure_missions_directory()
    lock_path = str(MISSIONS_DIR / ".active-leg.lock")
    with _active_leg_locks_guard:
        lock = _active_leg_locks.get(lock_path)
        if lock is None:
            lock = FileLock(lock_path)
            _active_leg_locks[lock_path] = lock
        return lock


def get_leg_timeline_path(leg_id: str, parent_mission_id: str) -> Path:
    """Get the scoped file path for a leg's cached timeline."""
    return get_mission_legs_dir(parent_mission_id) / f"{leg_id}{TIMELINE_SUFFIX}"


def get_mission_directory(mission_id: str) -> Path:
    """Get the directory path for a mission (for hierarchical v2 storage)."""
    return MISSIONS_DIR / mission_id


def get_mission_file_path(mission_id: str) -> Path:
    """Get the file path for mission metadata."""
    return get_mission_directory(mission_id) / "mission.json"


def get_mission_legs_dir(mission_id: str) -> Path:
    """Get the legs directory for a mission."""
    return get_mission_directory(mission_id) / "legs"


def get_mission_leg_file_path(mission_id: str, leg_id: str) -> Path:
    """Get the file path for a specific leg."""
    return get_mission_legs_dir(mission_id) / f"{leg_id}.json"


def _iter_mission_leg_files(legs_dir: Path):
    """Yield persisted mission leg JSON files, excluding cached timelines."""
    for leg_file in sorted(legs_dir.glob("*.json")):
        if leg_file.name.endswith(TIMELINE_SUFFIX):
            continue
        yield leg_file


def save_mission_v2(mission: Mission) -> dict:
    """Save a hierarchical mission with nested legs.

    Args:
        mission: Mission object with legs

    Returns:
        Dictionary with save metadata
    """
    # This lock deliberately covers every v2 mission write because each write
    # can add, remove, or change a persisted active leg.  Keep the unlocked
    # implementation private so callers cannot accidentally take this lock
    # twice while coordinating a broader v2 operation.
    with get_active_leg_lock():
        return _save_mission_v2_unlocked(mission)


def _save_mission_v2_unlocked(mission: Mission) -> dict:
    """Write a v2 mission while the active-leg repository lock is held."""
    mission_dir = get_mission_directory(mission.id)
    mission_dir.mkdir(parents=True, exist_ok=True)

    legs_dir = get_mission_legs_dir(mission.id)
    legs_dir.mkdir(parents=True, exist_ok=True)

    # Save mission metadata (without legs to avoid duplication)
    mission_meta = mission.model_copy(update={"legs": []})
    mission_file = get_mission_file_path(mission.id)

    with open(mission_file, "w") as f:
        json.dump(mission_meta.model_dump(), f, indent=2, default=str)

    # Save each leg separately
    for leg in mission.legs:
        leg_file = get_mission_leg_file_path(mission.id, leg.id)
        with open(leg_file, "w") as f:
            json.dump(leg.model_dump(), f, indent=2, default=str)

    persisted_leg_ids = {leg.id for leg in mission.legs}
    for leg_file in _iter_mission_leg_files(legs_dir):
        if leg_file.stem not in persisted_leg_ids:
            leg_file.unlink()

    logger.info(f"Mission {mission.id} saved with {len(mission.legs)} legs")

    return {
        "mission_id": mission.id,
        "path": str(mission_dir),
        "leg_count": len(mission.legs),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }


def load_mission_v2(mission_id: str) -> Mission | None:
    """Load a hierarchical mission with all legs.

    Args:
        mission_id: ID of mission to load

    Returns:
        Mission object with legs loaded, or None if not found
    """
    mission_file = get_mission_file_path(mission_id)

    if not mission_file.exists():
        logger.warning(f"Mission {mission_id} not found at {mission_file}")
        return None

    # Load mission metadata
    with open(mission_file, "r") as f:
        mission_data = json.load(f)

    # Load all legs
    legs_dir = get_mission_legs_dir(mission_id)
    legs = []

    if legs_dir.exists():
        for leg_file in _iter_mission_leg_files(legs_dir):
            with open(leg_file, "r") as f:
                leg_data = json.load(f)
                legs.append(MissionLeg(**leg_data))

    mission_data["legs"] = legs
    mission = Mission(**mission_data)

    logger.info(f"Mission {mission_id} loaded with {len(legs)} legs")
    return mission


def load_mission_metadata_v2(mission_id: str) -> Mission | None:
    """Load mission metadata with leg count but without full leg data.

    This is optimized for listing operations where full leg data is not needed.
    Returns a Mission object with stub leg objects containing only IDs, allowing
    the frontend to display accurate leg counts via legs.length.

    Args:
        mission_id: ID of mission to load

    Returns:
        Mission object with metadata and leg stubs (ID only), or None if not found
    """
    mission_file = get_mission_file_path(mission_id)

    if not mission_file.exists():
        logger.warning(f"Mission {mission_id} not found at {mission_file}")
        return None

    try:
        # Load mission metadata only
        with open(mission_file, "r") as f:
            mission_data = json.load(f)

        # Legacy mission files can predate timestamp persistence or contain an
        # invalid timestamp. Drop those values so Pydantic can safely apply its
        # defaults; list ordering uses the original persisted values separately.
        for timestamp_field in ("created_at", "updated_at"):
            if (
                timestamp_field in mission_data
                and _parse_persisted_timestamp(mission_data[timestamp_field]) is None
            ):
                mission_data.pop(timestamp_field)

        # Count leg files and create stub leg objects with only IDs
        legs_dir = get_mission_legs_dir(mission_id)
        leg_stubs = []

        if legs_dir.exists():
            for leg_file in _iter_mission_leg_files(legs_dir):
                # Extract leg ID from filename (e.g., "leg-1.json" -> "leg-1")
                leg_id = leg_file.stem
                # Create minimal leg stub with only required fields
                leg_stubs.append(
                    {
                        "id": leg_id,
                        "name": leg_id,  # Use ID as placeholder name
                        "route_id": "",  # Empty placeholder
                        "transports": {
                            "initial_x_satellite_id": ""
                        },  # Minimal placeholder
                    }
                )

        mission_data["legs"] = [MissionLeg(**stub) for stub in leg_stubs]
        mission = Mission(**mission_data)

        logger.debug(
            f"Mission {mission_id} metadata loaded with {len(leg_stubs)} leg stubs"
        )
        return mission

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse mission {mission_id}: {e}")
        return None
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        LookupError,
        ConnectionError,
        TimeoutError,
        ImportError,
        EOFError,
    ) as e:
        logger.error(f"Failed to load mission metadata {mission_id}: {e}")
        return None


def _parse_persisted_timestamp(value: object) -> datetime | None:
    """Return a timezone-aware persisted timestamp, or None for legacy values."""
    if not isinstance(value, str):
        return None

    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

    if timestamp.tzinfo is None:
        return None
    return timestamp.astimezone(timezone.utc)


def list_mission_metadata_v2() -> list[Mission]:
    """List hierarchical mission metadata newest-first with stable legacy fallback."""
    ensure_missions_directory()
    missions: list[tuple[datetime | None, str, Mission]] = []

    for mission_dir in sorted(MISSIONS_DIR.iterdir(), key=lambda path: path.name):
        if not mission_dir.is_dir():
            continue

        try:
            with open(mission_dir / "mission.json", "r") as f:
                raw_metadata = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        mission = load_mission_metadata_v2(mission_dir.name)
        if not mission:
            continue

        timestamp = _parse_persisted_timestamp(raw_metadata.get("updated_at"))
        if timestamp is None:
            timestamp = _parse_persisted_timestamp(raw_metadata.get("created_at"))
        missions.append((timestamp, mission.id, mission))

    return [
        mission
        for _, _, mission in sorted(
            missions,
            key=lambda item: (
                item[0] is None,
                -item[0].timestamp() if item[0] else 0,
                item[1],
            ),
        )
    ]


def save_mission_timeline(
    leg_id: str,
    timeline: MissionLegTimeline,
    parent_mission_id: str,
) -> Path:
    """Persist a leg timeline to disk."""
    ensure_missions_directory()
    timeline_path = get_leg_timeline_path(leg_id, parent_mission_id)
    timeline_path.parent.mkdir(parents=True, exist_ok=True)
    with open(timeline_path, "w") as handle:
        json.dump(timeline.model_dump(), handle, indent=2, default=str)
    logger.info("Saved leg timeline for %s", leg_id)
    return timeline_path


def load_mission_timeline(
    leg_id: str,
    parent_mission_id: str,
) -> MissionLegTimeline | None:
    """Load a cached timeline from its parent mission's scoped storage."""
    timeline_path = get_leg_timeline_path(leg_id, parent_mission_id)
    if not timeline_path.exists():
        return None
    with open(timeline_path, "r") as handle:
        return MissionLegTimeline(**json.load(handle))


def delete_mission_timeline(
    leg_id: str,
    parent_mission_id: str,
) -> None:
    """Remove a scoped cached leg timeline without touching mission data."""
    timeline_path = get_leg_timeline_path(leg_id, parent_mission_id)
    if timeline_path.exists():
        try:
            timeline_path.unlink()
        except OSError as exc:
            logger.warning("Failed to delete timeline %s: %s", timeline_path, exc)
