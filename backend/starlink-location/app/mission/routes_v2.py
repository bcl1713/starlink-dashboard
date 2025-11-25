"""Mission v2 API endpoints for hierarchical mission management."""

import io
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.mission.models import Mission, MissionLeg
from app.mission.storage import (
    save_mission_v2,
    load_mission_v2,
    delete_mission,
    mission_exists,
)
from app.mission.package_exporter import export_mission_package

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/missions", tags=["missions-v2"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Mission)
async def create_mission(mission: Mission) -> Mission:
    """Create a new hierarchical mission with legs.

    Args:
        mission: Mission object to create

    Returns:
        Created mission with 201 status
    """
    try:
        logger.info(f"Creating mission {mission.id}")
        save_mission_v2(mission)
        logger.info(f"Mission {mission.id} created successfully")
        return mission
    except Exception as e:
        logger.error(f"Failed to create mission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create mission",
        )


@router.get("", response_model=list[Mission])
async def list_missions(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[Mission]:
    """List all missions.

    Args:
        limit: Maximum number to return
        offset: Number to skip

    Returns:
        List of missions
    """
    try:
        from pathlib import Path
        missions_dir = Path("data/missions")

        if not missions_dir.exists():
            return []

        missions = []
        for mission_dir in sorted(missions_dir.iterdir()):
            if mission_dir.is_dir():
                mission = load_mission_v2(mission_dir.name)
                if mission:
                    missions.append(mission)

        return missions[offset : offset + limit]
    except Exception as e:
        logger.error(f"Failed to list missions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list missions",
        )


@router.get("/{mission_id}", response_model=Mission)
async def get_mission(mission_id: str) -> Mission:
    """Get a specific mission by ID.

    Args:
        mission_id: Mission ID to retrieve

    Returns:
        Mission object with all legs
    """
    mission = load_mission_v2(mission_id)

    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission {mission_id} not found",
        )

    return mission


@router.delete("/{mission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mission_endpoint(mission_id: str) -> None:
    """Delete a mission and all associated legs, routes, and POIs.

    Args:
        mission_id: Mission ID to delete

    Raises:
        HTTPException: 404 if mission not found, 500 on deletion failure
    """
    try:
        import shutil
        from pathlib import Path

        logger.info(f"Deleting mission {mission_id}")

        # Check mission exists
        mission = load_mission_v2(mission_id)
        if not mission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission {mission_id} not found",
            )

        # Log cascade deletion info
        leg_count = len(mission.legs)
        logger.info(
            f"Cascade deletion: mission {mission_id} with {leg_count} leg(s)"
        )

        # Delete mission directory (includes all legs, routes, and POIs)
        mission_dir = Path("data/missions") / mission_id
        if mission_dir.exists():
            shutil.rmtree(mission_dir)
            logger.info(f"Deleted mission directory: {mission_dir}")

        logger.info(
            f"Mission {mission_id} deleted successfully with {leg_count} leg(s)"
        )
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete mission {mission_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete mission",
        )


@router.post("/{mission_id}/export")
async def export_mission(mission_id: str) -> StreamingResponse:
    """Export mission as zip package."""
    try:
        zip_bytes = export_mission_package(mission_id)

        return StreamingResponse(
            io.BytesIO(zip_bytes),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{mission_id}.zip"'
            },
        )
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/import")
async def import_mission(file: UploadFile = File(...)) -> dict:
    """Import mission from zip package.

    Args:
        file: Uploaded zip file containing mission package

    Returns:
        Import result with success status and mission ID
    """
    try:
        import zipfile
        import tempfile
        import json
        from pathlib import Path

        # Create temp directory for extraction
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            zip_path = tmppath / "upload.zip"

            # Save uploaded file
            contents = await file.read()
            with open(zip_path, "wb") as f:
                f.write(contents)

            # Extract and validate
            with zipfile.ZipFile(zip_path, "r") as zf:
                # Check for required files
                if "mission.json" not in zf.namelist():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid package: missing mission.json"
                    )

                # Extract mission.json
                mission_data = json.loads(zf.read("mission.json"))

                # Create Mission object
                mission = Mission(**mission_data)

                # Save mission
                save_mission_v2(mission)

                logger.info(f"Mission {mission.id} imported successfully")

                return {
                    "success": True,
                    "mission_id": mission.id,
                    "warnings": []
                }

    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid zip file"
        )
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}"
        )


@router.post("/{mission_id}/legs", status_code=status.HTTP_201_CREATED, response_model=MissionLeg)
async def add_leg_to_mission(mission_id: str, leg: MissionLeg) -> MissionLeg:
    """Add a new leg to an existing mission.

    Args:
        mission_id: Mission ID to add leg to
        leg: MissionLeg object to add

    Returns:
        Created leg with 201 status
    """
    try:
        # Load mission
        mission = load_mission_v2(mission_id)
        if not mission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission {mission_id} not found",
            )

        # Check if leg ID already exists
        if any(existing_leg.id == leg.id for existing_leg in mission.legs):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Leg {leg.id} already exists in mission",
            )

        # Add leg to mission
        mission.legs.append(leg)

        # Save updated mission
        save_mission_v2(mission)

        logger.info(f"Added leg {leg.id} to mission {mission_id}")
        return leg
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add leg to mission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add leg to mission",
        )


@router.put("/{mission_id}/legs/{leg_id}", response_model=MissionLeg)
async def update_leg(mission_id: str, leg_id: str, updated_leg: MissionLeg) -> MissionLeg:
    """Update an existing leg in a mission.

    Args:
        mission_id: Mission ID
        leg_id: Leg ID to update
        updated_leg: Updated MissionLeg object

    Returns:
        Updated leg
    """
    try:
        # Load mission
        mission = load_mission_v2(mission_id)
        if not mission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission {mission_id} not found",
            )

        # Find leg index
        leg_index = None
        for i, leg in enumerate(mission.legs):
            if leg.id == leg_id:
                leg_index = i
                break

        if leg_index is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Leg {leg_id} not found in mission",
            )

        # Ensure updated leg has correct ID
        if updated_leg.id != leg_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Leg ID in path must match leg ID in body",
            )

        # Update leg
        mission.legs[leg_index] = updated_leg

        # Save updated mission
        save_mission_v2(mission)

        logger.info(f"Updated leg {leg_id} in mission {mission_id}")
        return updated_leg
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update leg: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update leg",
        )


@router.delete("/{mission_id}/legs/{leg_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_leg(mission_id: str, leg_id: str):
    """Delete a leg from a mission (cascade deletes route and POIs).

    Args:
        mission_id: Mission ID
        leg_id: Leg ID to delete

    Returns:
        204 No Content on success

    Raises:
        HTTPException: 404 if mission/leg not found, 500 on deletion failure
    """
    try:
        from pathlib import Path

        # Load mission
        mission = load_mission_v2(mission_id)
        if not mission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission {mission_id} not found",
            )

        # Find leg to get its route and POI info
        leg = next((l for l in mission.legs if l.id == leg_id), None)
        if not leg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Leg {leg_id} not found in mission",
            )

        # Log cascade deletion info
        route_id = leg.route_id or "none"
        logger.info(
            f"Cascade deletion: leg {leg_id} with route {route_id}"
        )

        # Remove leg from mission
        mission.legs = [l for l in mission.legs if l.id != leg_id]
        save_mission_v2(mission)

        # Delete leg file from disk
        legs_dir = Path("data/missions") / mission_id / "legs"
        leg_file = legs_dir / f"{leg_id}.json"
        if leg_file.exists():
            try:
                leg_file.unlink()
                logger.info(f"Deleted leg file: {leg_file}")
            except OSError as e:
                logger.error(f"Failed to delete leg file {leg_file}: {e}")
                raise

        logger.info(
            f"Deleted leg {leg_id} from mission {mission_id} with route {route_id}"
        )
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete leg {leg_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete leg",
        )


@router.post("/{mission_id}/legs/{leg_id}/activate", response_model=dict)
async def activate_leg(mission_id: str, leg_id: str) -> dict:
    """Activate a specific leg (deactivates all others in the mission).

    Args:
        mission_id: Mission ID
        leg_id: Leg ID to activate

    Returns:
        Success response with active leg ID
    """
    try:
        # Load mission
        mission = load_mission_v2(mission_id)

        if not mission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission {mission_id} not found",
            )

        # Find the target leg
        leg_found = False
        for leg in mission.legs:
            if leg.id == leg_id:
                leg.is_active = True
                leg_found = True
            else:
                leg.is_active = False

        if not leg_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Leg {leg_id} not found in mission {mission_id}",
            )

        # Save updated mission
        save_mission_v2(mission)

        logger.info(f"Activated leg {leg_id} in mission {mission_id}")

        return {"status": "success", "active_leg_id": leg_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to activate leg: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate leg",
        )
