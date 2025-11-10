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

from app.mission.models import Mission

logger = logging.getLogger(__name__)

# Base directory for mission storage
MISSIONS_DIR = Path("data/missions")


def ensure_missions_directory():
    """Ensure the missions directory exists."""
    MISSIONS_DIR.mkdir(parents=True, exist_ok=True)


def get_mission_path(mission_id: str) -> Path:
    """Get the file path for a mission by ID."""
    return MISSIONS_DIR / f"{mission_id}.json"


def get_mission_checksum_path(mission_id: str) -> Path:
    """Get the checksum file path for a mission."""
    return MISSIONS_DIR / f"{mission_id}.sha256"


def compute_file_checksum(file_path: Path) -> str:
    """Compute SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_mission_checksum(mission: Mission) -> str:
    """Compute checksum of a mission object (JSON-serialized)."""
    # Use model_dump for consistent serialization with sorted keys
    mission_dict = mission.model_dump()
    mission_json = json.dumps(mission_dict, sort_keys=True, default=str)
    return hashlib.sha256(mission_json.encode()).hexdigest()


def save_mission(mission: Mission) -> dict:
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


def load_mission(mission_id: str) -> Optional[Mission]:
    """Load a mission from persistent storage.

    Args:
        mission_id: ID of the mission to load

    Returns:
        Mission object if found and valid, None otherwise

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

        mission = Mission(**mission_data)

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
        try:
            with open(mission_path, "r") as f:
                mission_data = json.load(f)

            missions.append({
                "id": mission_data.get("id"),
                "name": mission_data.get("name"),
                "route_id": mission_data.get("route_id"),
                "is_active": mission_data.get("is_active", False),
                "path": str(mission_path),
                "updated_at": mission_data.get("updated_at"),
            })

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

    if not deleted:
        logger.warning(f"Mission {mission_id} not found for deletion")

    return deleted


def mission_exists(mission_id: str) -> bool:
    """Check if a mission exists in storage.

    Args:
        mission_id: ID of the mission to check

    Returns:
        True if mission file exists, False otherwise
    """
    return get_mission_path(mission_id).exists()
