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
