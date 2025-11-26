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
    save_mission_timeline,
)
from app.mission.package_exporter import export_mission_package
from app.mission.timeline_service import build_mission_timeline
from app.services.route_manager import RouteManager
from app.services.poi_manager import POIManager
from app.satellites.coverage import CoverageSampler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/missions", tags=["missions-v2"])

# Global manager instances (set by main.py during startup)
_route_manager: Optional[RouteManager] = None
_poi_manager: Optional[POIManager] = None
_coverage_sampler: Optional[CoverageSampler] = None


def set_route_manager(route_manager: RouteManager) -> None:
    """Set the route manager instance (called by main.py during startup)."""
    global _route_manager
    _route_manager = route_manager


def set_poi_manager(poi_manager: POIManager) -> None:
    """Set the POI manager instance (called by main.py during startup)."""
    global _poi_manager
    _poi_manager = poi_manager


def set_coverage_sampler(coverage_sampler: CoverageSampler) -> None:
    """Set the coverage sampler instance (called by main.py during startup)."""
    global _coverage_sampler
    _coverage_sampler = coverage_sampler


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

        # Generate timeline for the updated leg
        if _route_manager:
            try:
                logger.info(f"Generating timeline for leg {leg_id}")
                timeline, summary = build_mission_timeline(
                    mission=updated_leg,
                    route_manager=_route_manager,
                    poi_manager=_poi_manager,
                    coverage_sampler=_coverage_sampler,
                    parent_mission_id=mission_id,
                )
                save_mission_timeline(leg_id, timeline)
                logger.info(f"Timeline generated and saved for leg {leg_id}")
            except Exception as e:
                logger.error(f"Failed to generate timeline for leg {leg_id}: {e}")
                # Don't fail the save if timeline generation fails

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

        # CASCADE DELETE: Delete associated resources
        # 1. Delete route if exists
        if leg.route_id and _route_manager:
            try:
                parsed_route = _route_manager.get_route(leg.route_id)
                if parsed_route:
                    # Delete associated POIs for this route
                    if _poi_manager:
                        deleted_pois = _poi_manager.delete_route_pois(leg.route_id)
                        logger.info(f"Deleted {deleted_pois} POIs for route {leg.route_id}")

                    # Delete KML file
                    file_path = Path(parsed_route.metadata.file_path)
                    if file_path.exists():
                        file_path.unlink()
                        logger.info(f"Deleted route file: {file_path}")

                    # Remove from route manager cache
                    _route_manager._routes.pop(leg.route_id, None)
                    logger.info(f"Deleted route {leg.route_id} associated with leg {leg_id}")
            except Exception as e:
                logger.error(f"Failed to delete route {leg.route_id}: {e}")
                # Don't fail the entire leg deletion if route deletion fails

        # 2. Delete POIs associated with this leg
        if _poi_manager:
            try:
                deleted_leg_pois = _poi_manager.delete_mission_pois(mission_id)
                logger.info(f"Deleted {deleted_leg_pois} mission POIs for mission {mission_id}")
            except Exception as e:
                logger.error(f"Failed to delete mission POIs: {e}")
                # Don't fail the entire leg deletion if POI deletion fails

        # 3. Remove leg from mission and save
        mission.legs = [l for l in mission.legs if l.id != leg_id]
        save_mission_v2(mission)

        # 4. Delete leg file from disk
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
        active_leg = None
        for leg in mission.legs:
            if leg.id == leg_id:
                leg.is_active = True
                leg_found = True
                active_leg = leg
            else:
                leg.is_active = False

        if not leg_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Leg {leg_id} not found in mission {mission_id}",
            )

        # Save updated mission
        save_mission_v2(mission)

        # Activate the route in RouteManager so dashboard can display it
        if active_leg and active_leg.route_id and _route_manager:
            try:
                logger.info(f"Activating route {active_leg.route_id} for leg {leg_id}")
                _route_manager.activate_route(active_leg.route_id)
                logger.info(f"Route {active_leg.route_id} activated successfully")
            except Exception as e:
                logger.error(f"Failed to activate route {active_leg.route_id}: {e}")
                # Don't fail leg activation if route activation fails

        # Generate timeline for the activated leg
        if active_leg and _route_manager:
            try:
                logger.info(f"Generating timeline for leg {leg_id}")
                timeline, summary = build_mission_timeline(
                    mission=active_leg,
                    route_manager=_route_manager,
                    poi_manager=_poi_manager,
                    coverage_sampler=_coverage_sampler,
                    parent_mission_id=mission_id,
                )
                save_mission_timeline(leg_id, timeline)
                logger.info(f"Timeline generated and saved for leg {leg_id}")
            except Exception as e:
                logger.error(f"Failed to generate timeline for leg {leg_id}: {e}")
                # Don't fail activation if timeline generation fails
                # Return success but note the timeline issue in logs

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


@router.post("/{mission_id}/legs/deactivate", response_model=dict)
async def deactivate_all_legs(mission_id: str) -> dict:
    """Deactivate all legs in the mission.

    Args:
        mission_id: Mission ID

    Returns:
        Success response
    """
    try:
        # Load mission
        mission = load_mission_v2(mission_id)

        if not mission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission {mission_id} not found",
            )

        # Deactivate all legs
        for leg in mission.legs:
            leg.is_active = False

        # Save updated mission
        save_mission_v2(mission)

        # Deactivate all routes associated with this mission's legs
        if _route_manager:
            try:
                for leg in mission.legs:
                    if leg.route_id:
                        logger.info(f"Deactivating route {leg.route_id} for leg {leg.id}")
                        _route_manager.deactivate_route(leg.route_id)
                logger.info(f"Deactivated all routes for mission {mission_id}")
            except Exception as e:
                logger.error(f"Failed to deactivate routes: {e}")
                # Don't fail the overall deactivation if route deactivation fails

        logger.info(f"Deactivated all legs in mission {mission_id}")

        return {"status": "success", "message": "All legs deactivated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deactivate legs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate legs",
        )


@router.get("/{mission_id}/legs/{leg_id}/timeline")
async def get_leg_timeline(mission_id: str, leg_id: str) -> dict:
    """Get the computed timeline for a mission leg.

    Args:
        mission_id: Mission ID
        leg_id: Leg ID

    Returns:
        Timeline object with segments and metadata
    """
    try:
        from app.mission.storage import load_mission_timeline

        # Load mission to verify it exists
        mission = load_mission_v2(mission_id)
        if not mission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission {mission_id} not found",
            )

        # Verify leg exists
        leg = next((l for l in mission.legs if l.id == leg_id), None)
        if not leg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Leg {leg_id} not found in mission {mission_id}",
            )

        # Load timeline for the leg
        timeline = load_mission_timeline(leg_id)
        if not timeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Timeline not found for leg {leg_id}",
            )

        return timeline.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get timeline for leg {leg_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve timeline",
        )
