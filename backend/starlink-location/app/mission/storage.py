"""Mission storage utilities for persisting mission plans to portable flat files.

Missions are stored as JSON files under data/missions/ with optional assets.
This design allows mission plans to be portable across instances and systems.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.mission.models import Mission, MissionLeg, MissionLegTimeline
from filelock import FileLock

logger = logging.getLogger(__name__)

# Base directory for mission storage
MISSIONS_DIR = Path("data/missions")
TIMELINE_SUFFIX = ".timeline.json"


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


def get_mission_path(mission_id: str) -> Path:
    """Get the file path for a mission by ID."""
    return MISSIONS_DIR / f"{mission_id}.json"


def get_mission_checksum_path(mission_id: str) -> Path:
    """Get the checksum file path for a mission."""
    return MISSIONS_DIR / f"{mission_id}.sha256"


def get_mission_timeline_path(mission_id: str) -> Path:
    """Get the file path for a mission's cached timeline."""
    return MISSIONS_DIR / f"{mission_id}{TIMELINE_SUFFIX}"


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


def compute_file_checksum(file_path: Path) -> str:
    """Compute SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_mission_checksum(mission) -> str:
    """Compute checksum of a mission object (JSON-serialized)."""
    # Use model_dump for consistent serialization with sorted keys
    mission_dict = mission.model_dump()
    mission_json = json.dumps(mission_dict, sort_keys=True, default=str)
    return hashlib.sha256(mission_json.encode()).hexdigest()


def save_mission(mission: MissionLeg) -> dict:
    """Save a mission to persistent storage.

    Args:
        mission: Mission object to save

    Returns:
        Dictionary with save metadata (path, checksum, timestamp)

    Raises:
        IOError: If file write fails
    """
    ensure_missions_directory()

    mission_path = get_mission_path(mission.id)
    checksum_path = get_mission_checksum_path(mission.id)

    try:
        # Update timestamp
        mission.updated_at = datetime.now(timezone.utc)

        # Write mission JSON
        with open(mission_path, "w") as f:
            json.dump(mission.model_dump(), f, indent=2, default=str)

        # Compute and save checksum
        checksum = compute_mission_checksum(mission)
        with open(checksum_path, "w") as f:
            f.write(checksum)

        logger.info(f"Mission {mission.id} saved to {mission_path}")

        return {
            "mission_id": mission.id,
            "path": str(mission_path),
            "checksum": checksum,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }

    except IOError as e:
        logger.error(f"Failed to save mission {mission.id}: {e}")
        raise


def save_mission_v2(mission: Mission) -> dict:
    """Save a hierarchical mission with nested legs.

    Args:
        mission: Mission object with legs

    Returns:
        Dictionary with save metadata
    """
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

    logger.info(f"Mission {mission.id} saved with {len(mission.legs)} legs")

    return {
        "mission_id": mission.id,
        "path": str(mission_dir),
        "leg_count": len(mission.legs),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }


def load_mission_v2(mission_id: str) -> Optional[Mission]:
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
        for leg_file in sorted(legs_dir.glob("*.json")):
            with open(leg_file, "r") as f:
                leg_data = json.load(f)
                legs.append(MissionLeg(**leg_data))

    mission_data["legs"] = legs
    mission = Mission(**mission_data)

    logger.info(f"Mission {mission_id} loaded with {len(legs)} legs")
    return mission


def load_mission_metadata_v2(mission_id: str) -> Optional[Mission]:
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

        # Count leg files and create stub leg objects with only IDs
        legs_dir = get_mission_legs_dir(mission_id)
        leg_stubs = []

        if legs_dir.exists():
            for leg_file in sorted(legs_dir.glob("*.json")):
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
    except Exception as e:
        logger.error(f"Failed to load mission metadata {mission_id}: {e}")
        return None


def load_mission(mission_id: str) -> Optional[MissionLeg]:
    """Load a mission leg from persistent storage.

    Args:
        mission_id: ID of the mission to load

    Returns:
        MissionLeg object if found and valid, None otherwise

    Raises:
        ValueError: If loaded data doesn't match integrity check
    """
    mission_path = get_mission_path(mission_id)
    checksum_path = get_mission_checksum_path(mission_id)

    if not mission_path.exists():
        logger.warning(f"Mission {mission_id} not found at {mission_path}")
        return None

    try:
        # Load mission JSON
        with open(mission_path, "r") as f:
            mission_data = json.load(f)

        mission = MissionLeg(**mission_data)

        # Verify checksum if it exists
        if checksum_path.exists():
            with open(checksum_path, "r") as f:
                stored_checksum = f.read().strip()

            computed_checksum = compute_mission_checksum(mission)

            if stored_checksum != computed_checksum:
                logger.warning(
                    f"Mission {mission_id} checksum mismatch: "
                    f"stored={stored_checksum}, computed={computed_checksum}"
                )
                # Log but don't fail; data might have been updated manually

        logger.info(f"Mission {mission_id} loaded from {mission_path}")
        return mission

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse mission {mission_id}: {e}")
        raise ValueError(f"Invalid JSON in mission file: {e}")
    except Exception as e:
        logger.error(f"Failed to load mission {mission_id}: {e}")
        raise


def list_missions() -> list[dict]:
    """List all saved missions.

    Returns:
        List of mission metadata dictionaries (id, name, path, updated_at)
    """
    ensure_missions_directory()

    missions = []
    for mission_path in sorted(MISSIONS_DIR.glob("*.json")):
        if mission_path.name.endswith(TIMELINE_SUFFIX):
            continue
        try:
            with open(mission_path, "r") as f:
                mission_data = json.load(f)

            mission_id = mission_data.get("id") or mission_path.stem

            missions.append(
                {
                    "id": mission_id,
                    "name": mission_data.get("name"),
                    "route_id": mission_data.get("route_id"),
                    "is_active": mission_data.get("is_active", False),
                    "path": str(mission_path),
                    "updated_at": mission_data.get("updated_at"),
                }
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Skipping invalid mission file {mission_path}: {e}")
            continue

    return missions


def delete_mission(mission_id: str) -> bool:
    """Delete a mission from persistent storage.

    Args:
        mission_id: ID of the mission to delete

    Returns:
        True if deletion succeeded, False if mission not found
    """
    mission_path = get_mission_path(mission_id)
    checksum_path = get_mission_checksum_path(mission_id)
    timeline_path = get_mission_timeline_path(mission_id)

    deleted = False

    if mission_path.exists():
        try:
            mission_path.unlink()
            logger.info(f"Deleted mission file {mission_path}")
            deleted = True
        except OSError as e:
            logger.error(f"Failed to delete mission file {mission_path}: {e}")
            raise

    if checksum_path.exists():
        try:
            checksum_path.unlink()
            logger.info(f"Deleted checksum file {checksum_path}")
        except OSError as e:
            logger.error(f"Failed to delete checksum file {checksum_path}: {e}")
            raise

    if timeline_path.exists():
        try:
            timeline_path.unlink()
            logger.info(f"Deleted timeline file {timeline_path}")
        except OSError as e:
            logger.error(f"Failed to delete timeline file {timeline_path}: {e}")
            raise

    if not deleted:
        logger.warning(f"Mission {mission_id} not found for deletion")

    return deleted


def save_mission_timeline(mission_id: str, timeline: MissionLegTimeline) -> Path:
    """Persist a mission timeline to disk."""
    ensure_missions_directory()
    timeline_path = get_mission_timeline_path(mission_id)
    with open(timeline_path, "w") as handle:
        json.dump(timeline.model_dump(), handle, indent=2, default=str)
    logger.info("Saved mission timeline for %s", mission_id)
    return timeline_path


def load_mission_timeline(mission_id: str) -> MissionLegTimeline | None:
    """Load a previously computed mission timeline."""
    timeline_path = get_mission_timeline_path(mission_id)
    if not timeline_path.exists():
        return None
    with open(timeline_path, "r") as handle:
        data = json.load(handle)
    return MissionLegTimeline(**data)


def delete_mission_timeline(mission_id: str) -> None:
    """Remove cached mission timeline without touching mission data."""
    timeline_path = get_mission_timeline_path(mission_id)
    if timeline_path.exists():
        try:
            timeline_path.unlink()
        except OSError as exc:
            logger.warning("Failed to delete mission timeline %s: %s", mission_id, exc)


def mission_exists(mission_id: str) -> bool:
    """Check if a mission exists in storage.

    Args:
        mission_id: ID of the mission to check

    Returns:
        True if mission file exists, False otherwise
    """
    return get_mission_path(mission_id).exists()
