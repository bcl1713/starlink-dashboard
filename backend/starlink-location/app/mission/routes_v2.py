"""Mission v2 API endpoints for hierarchical mission management."""

# FR-004: File exceeds 300 lines (1150 lines) because mission API combines leg
# CRUD, timeline management, export dispatch, and validation workflows that must
# coordinate across storage, KML parsing, and state machines. Separation would
# create circular imports. Deferred to v0.4.0.

import json
import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Optional
from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    status,
    UploadFile,
    File,
    Depends,
    Request,
)
from fastapi.responses import StreamingResponse
from app.core.limiter import limiter

from app.mission.models import Mission, MissionLeg, MissionUpdate
from app.mission.storage import (
    save_mission_v2,
    load_mission_v2,
    save_mission_timeline,
    get_mission_lock,
    load_mission_metadata_v2,
)
from app.mission.package import export_mission_package
from app.mission.timeline_service import build_mission_timeline
from app.services.route_manager import RouteManager
from app.services.poi_manager import POIManager
from app.mission.dependencies import get_route_manager, get_poi_manager
from app.satellites.coverage import CoverageSampler

logger = logging.getLogger(__name__)

# Constants
DEFAULT_PAGINATION_LIMIT = 10  # Default number of missions to return
MAX_PAGINATION_LIMIT = 100  # Maximum number of missions to return

router = APIRouter(prefix="/api/v2/missions", tags=["missions-v2"])

# Global manager instances (set by main.py during startup)
_coverage_sampler: Optional[CoverageSampler] = None


def set_coverage_sampler(coverage_sampler: CoverageSampler) -> None:
    """Set the coverage sampler instance (called by main.py during startup)."""
    global _coverage_sampler
    _coverage_sampler = coverage_sampler


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Mission)
async def create_mission(
    mission: Mission,
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> Mission:
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

        # Generate timeline for each leg
        if route_manager:
            for leg in mission.legs:
                if leg.route_id:
                    try:
                        logger.info(f"Generating timeline for leg {leg.id}")
                        timeline, summary = build_mission_timeline(
                            mission=leg,
                            route_manager=route_manager,
                            poi_manager=poi_manager,
                            coverage_sampler=_coverage_sampler,
                            parent_mission_id=mission.id,
                        )
                        save_mission_timeline(leg.id, timeline)
                        logger.info(f"Timeline generated and saved for leg {leg.id}")
                    except Exception as e:
                        logger.error(
                            f"Failed to generate timeline for leg {leg.id}: {e}"
                        )
                        # Don't fail creation if timeline generation fails
        return mission
    except Exception as e:
        logger.error(f"Failed to create mission: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create mission: {type(e).__name__}: {str(e)}",
        )


@router.get("", response_model=list[Mission])
async def list_missions(
    limit: int = Query(DEFAULT_PAGINATION_LIMIT, ge=1, le=MAX_PAGINATION_LIMIT),
    offset: int = Query(0, ge=0),
) -> list[Mission]:
    """List all missions (metadata only, without legs).

    Args:
        limit: Maximum number to return
        offset: Number to skip

    Returns:
        List of missions with metadata only (empty legs arrays)
    """
    try:
        from pathlib import Path

        missions_dir = Path("data/missions")

        if not missions_dir.exists():
            return []

        missions = []
        for mission_dir in sorted(missions_dir.iterdir()):
            if mission_dir.is_dir():
                # Use metadata-only loading for efficiency
                mission = load_mission_metadata_v2(mission_dir.name)
                if mission:
                    missions.append(mission)

        return missions[offset : offset + limit]
    except Exception as e:
        logger.error(f"Failed to list missions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list missions: {type(e).__name__}: {str(e)}",
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


@router.patch("/{mission_id}", response_model=Mission)
async def update_mission(mission_id: str, updates: MissionUpdate) -> Mission:
    """Update mission name and/or description.

    Args:
        mission_id: Mission ID to update
        updates: MissionUpdate with optional name and description fields

    Returns:
        Updated mission object

    Raises:
        HTTPException: 404 if mission not found, 422 for validation errors
    """
    try:
        from datetime import datetime, timezone

        logger.info(f"Updating mission {mission_id}")

        with get_mission_lock(mission_id):
            # Load existing mission
            mission = load_mission_v2(mission_id)
            if not mission:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Mission {mission_id} not found",
                )

            # Apply updates
            if updates.name is not None:
                mission.name = updates.name
                logger.info(f"Updated mission {mission_id} name to: {updates.name}")

            if updates.description is not None:
                mission.description = updates.description
                logger.info(f"Updated mission {mission_id} description")

            # Update timestamp
            mission.updated_at = datetime.now(timezone.utc)

            # Save updated mission
            save_mission_v2(mission)
            logger.info(f"Mission {mission_id} updated successfully")

            return mission
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update mission {mission_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update mission: {type(e).__name__}: {str(e)}",
        )


@router.delete("/{mission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mission_endpoint(
    mission_id: str,
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> None:
    """Delete a mission and all associated legs, routes, and POIs.

    Cascade deletes all resources:
    - All legs in the mission
    - All routes associated with legs
    - All POIs associated with routes and mission
    - The entire mission directory

    Args:
        mission_id: Mission ID to delete

    Raises:
        HTTPException: 404 if mission not found, 500 on deletion failure
    """
    try:
        import shutil
        from pathlib import Path

        logger.info(f"Deleting mission {mission_id}")

        with get_mission_lock(mission_id):
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

            # CASCADE DELETE: Process each leg and its associated resources
            deleted_routes_count = 0
            deleted_pois_count = 0

            for leg in mission.legs:
                route_id = leg.route_id or "none"
                logger.info(
                    f"Cascade deletion: processing leg {leg.id} with route {route_id}"
                )

                # Delete route if it exists
                if leg.route_id:
                    try:
                        parsed_route = route_manager.get_route(leg.route_id)
                        if parsed_route:
                            # Delete POIs associated with this route
                            if poi_manager:
                                route_pois_deleted = poi_manager.delete_route_pois(
                                    leg.route_id
                                )
                                deleted_pois_count += route_pois_deleted
                                logger.info(
                                    f"Deleted {route_pois_deleted} POIs for route {leg.route_id}"
                                )

                            # Delete KML file
                            file_path = Path(parsed_route.metadata.file_path)
                            if file_path.exists():
                                try:
                                    file_path.unlink()
                                    logger.info(f"Deleted route file: {file_path}")
                                    deleted_routes_count += 1
                                except OSError as e:
                                    logger.error(
                                        f"Failed to delete route file {file_path}: {e}"
                                    )

                            # Remove from route manager cache
                            route_manager._routes.pop(leg.route_id, None)
                            logger.info(
                                f"Deleted route {leg.route_id} associated with leg {leg.id}"
                            )
                    except Exception as e:
                        logger.error(f"Failed to delete route {leg.route_id}: {e}")
                        # Don't fail entire mission deletion if route deletion fails

                # Delete mission POIs
                if poi_manager:
                    try:
                        mission_pois_deleted = poi_manager.delete_mission_pois(
                            mission_id
                        )
                        deleted_pois_count += mission_pois_deleted
                        logger.info(
                            f"Deleted {mission_pois_deleted} POIs for mission {mission_id}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to delete mission POIs: {e}")
                        # Don't fail entire mission deletion if POI deletion fails

            # Delete entire mission directory
            mission_dir = Path("data/missions") / mission_id
            if mission_dir.exists():
                try:
                    shutil.rmtree(mission_dir)
                    logger.info(f"Deleted mission directory: {mission_dir}")
                except OSError as e:
                    logger.error(
                        f"Failed to delete mission directory {mission_dir}: {e}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to delete mission directory",
                    )

            logger.info(
                f"Mission {mission_id} deleted successfully with {leg_count} leg(s), "
                f"{deleted_routes_count} route(s), {deleted_pois_count} POI(s)"
            )
            return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete mission {mission_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete mission: {type(e).__name__}: {str(e)}",
        )


@router.post("/{mission_id}/export")
@limiter.limit("10/minute")
async def export_mission(
    request: Request,
    mission_id: str,
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> StreamingResponse:
    """Export mission as zip package."""
    try:
        zip_file = export_mission_package(
            mission_id,
            route_manager=route_manager,
            poi_manager=poi_manager,
        )

        return StreamingResponse(
            zip_file,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{mission_id}.zip"'},
        )
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


def safe_extract_path(zip_path: str, base_path: Path) -> Path:
    """Validate that a zip extraction path is safe (prevents directory traversal attacks).

    Args:
        zip_path: Path from zip file
        base_path: Base directory for extraction

    Returns:
        Validated absolute path

    Raises:
        HTTPException: If path attempts directory traversal
    """
    # Resolve the absolute path
    absolute_path = (base_path / zip_path).resolve()

    # Ensure the path is within the base directory
    if not str(absolute_path).startswith(str(base_path.resolve())):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid path in zip: {zip_path} (directory traversal attempt)",
        )

    return absolute_path


def _import_routes_from_zip(
    zf: zipfile.ZipFile,
    route_manager: RouteManager,
    tmppath: Path,
) -> tuple[int, list[str]]:
    """Import route KML files from zip archive.

    Args:
        zf: ZipFile to read from
        route_manager: RouteManager instance
        tmppath: Temporary directory path

    Returns:
        Tuple of (routes_imported, warnings)
    """
    routes_imported = 0
    warnings = []

    route_files = [
        f for f in zf.namelist() if f.startswith("routes/") and f.endswith(".kml")
    ]
    for route_file in route_files:
        try:
            # Validate path safety
            safe_extract_path(route_file, tmppath)

            route_id = Path(route_file).stem
            kml_content = zf.read(route_file)

            # Save route KML to routes directory
            routes_dir = Path(route_manager.routes_dir)
            kml_path = routes_dir / f"{route_id}.kml"
            with open(kml_path, "wb") as f:
                f.write(kml_content)

            routes_imported += 1
            logger.info(f"Imported route: {route_id}")
        except Exception as e:
            logger.error(f"Failed to import route {route_file}: {e}")
            warnings.append(f"Route {route_file}: {str(e)}")

    return routes_imported, warnings


def _import_satellite_pois(
    zf: zipfile.ZipFile,
    poi_manager: POIManager,
) -> tuple[int, int, list[str]]:
    """Import and deduplicate satellite POIs from zip archive.

    Args:
        zf: ZipFile to read from
        poi_manager: POIManager instance

    Returns:
        Tuple of (satellites_imported, satellites_updated, warnings)
    """
    from app.models.poi import POI

    satellites_imported = 0
    satellites_updated = 0
    warnings = []

    satellite_file = "pois/satellites.json"
    if satellite_file not in zf.namelist():
        return satellites_imported, satellites_updated, warnings

    try:
        satellite_data = json.loads(zf.read(satellite_file))
        for poi_dict in satellite_data.get("pois", []):
            try:
                poi = POI(**poi_dict)

                # Check if satellite already exists by name
                existing_pois = poi_manager.list_pois()
                existing_satellite = next(
                    (
                        p
                        for p in existing_pois
                        if p.name == poi.name and p.category == "satellite"
                    ),
                    None,
                )

                if existing_satellite:
                    # Update if orbital position (longitude) is different
                    if existing_satellite.longitude != poi.longitude:
                        poi_manager.update_poi(existing_satellite.id, poi)
                        satellites_updated += 1
                        logger.info(
                            f"Updated satellite POI: {poi.name} (orbital position changed)"
                        )
                    else:
                        logger.info(
                            f"Satellite POI already exists with same position: {poi.name}"
                        )
                else:
                    # Create new satellite POI
                    poi_manager.create_poi(poi)
                    satellites_imported += 1
                    logger.info(f"Imported satellite POI: {poi.name}")
            except Exception as e:
                logger.error(f"Failed to import satellite POI: {e}")
                warnings.append(f"Satellite POI: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to process satellite POIs: {e}")
        warnings.append(f"Satellites file: {str(e)}")

    return satellites_imported, satellites_updated, warnings


def _import_leg_pois(
    zf: zipfile.ZipFile,
    poi_manager: POIManager,
    poi_files: list[str],
    satellite_file: str,
    tmppath: Path,
) -> tuple[int, list[str]]:
    """Import leg-specific POIs from zip archive.

    Args:
        zf: ZipFile to read from
        poi_manager: POIManager instance
        poi_files: List of POI file paths in zip
        satellite_file: Path to satellite POI file (to skip)
        tmppath: Temporary directory path

    Returns:
        Tuple of (pois_imported, warnings)
    """
    from app.models.poi import POI

    pois_imported = 0
    warnings = []

    # Process leg-specific POI files
    leg_poi_files = [f for f in poi_files if f != satellite_file]
    for poi_file in leg_poi_files:
        try:
            # Validate path safety
            safe_extract_path(poi_file, tmppath)

            poi_data = json.loads(zf.read(poi_file))
            for poi_dict in poi_data.get("pois", []):
                try:
                    # Skip if this is a satellite POI (already processed)
                    if poi_dict.get("category") == "satellite":
                        continue

                    poi = POI(**poi_dict)
                    poi_manager.create_poi(poi)
                    pois_imported += 1
                    logger.info(f"Imported POI: {poi.name}")
                except Exception as e:
                    logger.error(f"Failed to import POI from {poi_file}: {e}")
                    warnings.append(f"POI in {poi_file}: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to process POI file {poi_file}: {e}")
            warnings.append(f"POI file {poi_file}: {str(e)}")

    return pois_imported, warnings


def _generate_timelines_for_imported_legs(
    mission: Mission,
    route_manager: RouteManager,
    poi_manager: POIManager,
    coverage_sampler,
) -> list[str]:
    """Generate timelines for all imported legs.

    Args:
        mission: Imported mission
        route_manager: RouteManager instance
        poi_manager: POIManager instance
        coverage_sampler: CoverageSampler instance

    Returns:
        List of warnings
    """
    warnings = []

    for leg in mission.legs:
        if leg.route_id:
            try:
                logger.info(f"Generating timeline for imported leg {leg.id}")
                timeline, summary = build_mission_timeline(
                    mission=leg,
                    route_manager=route_manager,
                    poi_manager=poi_manager,
                    coverage_sampler=coverage_sampler,
                    parent_mission_id=mission.id,
                )
                save_mission_timeline(leg.id, timeline)
                logger.info(f"Timeline generated and saved for imported leg {leg.id}")
            except Exception as e:
                logger.error(
                    f"Failed to generate timeline for imported leg {leg.id}: {e}"
                )
                warnings.append(
                    f"Timeline generation failed for leg {leg.id}: {str(e)}"
                )

    return warnings


@router.post("/import")
@limiter.limit("5/minute")
async def import_mission(
    request: Request,
    file: UploadFile = File(...),
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> dict:
    """Import mission from zip package.

    Args:
        file: Uploaded zip file containing mission package

    Returns:
        Import result with success status and mission ID
    """
    try:
        warnings = []
        routes_imported = 0
        pois_imported = 0
        satellites_imported = 0
        satellites_updated = 0

        # Create temp directory for extraction
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            zip_path = tmppath / "upload.zip"

            # Save uploaded file
            contents = await file.read()

            MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB
            if len(contents) > MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="File too large",
                )

            with open(zip_path, "wb") as f:
                f.write(contents)

            # Extract and validate
            with zipfile.ZipFile(zip_path, "r") as zf:
                # Check for required files
                if "mission.json" not in zf.namelist():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid package: missing mission.json",
                    )

                # Extract mission.json
                mission_data = json.loads(zf.read("mission.json"))

                # Create Mission object
                mission = Mission(**mission_data)

                # Save mission
                save_mission_v2(mission)
                logger.info(f"Mission {mission.id} imported successfully")

                # Import route KML files from routes/ folder
                if route_manager:
                    routes_imported, route_warnings = _import_routes_from_zip(
                        zf, route_manager, tmppath
                    )
                    warnings.extend(route_warnings)
                else:
                    warnings.append("Route manager not available, routes not imported")

                # Import POIs from pois/ folder
                if poi_manager:
                    poi_files = [
                        f
                        for f in zf.namelist()
                        if f.startswith("pois/") and f.endswith(".json")
                    ]
                    satellite_file = "pois/satellites.json"

                    # Process satellite POIs first (for deduplication)
                    satellites_imported, satellites_updated, sat_warnings = (
                        _import_satellite_pois(zf, poi_manager)
                    )
                    warnings.extend(sat_warnings)

                    # Process leg-specific POI files
                    pois_imported, poi_warnings = _import_leg_pois(
                        zf, poi_manager, poi_files, satellite_file, tmppath
                    )
                    warnings.extend(poi_warnings)
                else:
                    warnings.append("POI manager not available, POIs not imported")

                result = {
                    "success": True,
                    "mission_id": mission.id,
                    "mission_name": mission.name,
                    "leg_count": len(mission.legs),
                    "routes_imported": routes_imported,
                    "pois_imported": pois_imported,
                    "satellites_imported": satellites_imported,
                    "satellites_updated": satellites_updated,
                    "warnings": warnings,
                }

                # Generate timelines for all imported legs to ensure derived data (like Ka transitions) is present
                if route_manager:
                    timeline_warnings = _generate_timelines_for_imported_legs(
                        mission, route_manager, poi_manager, _coverage_sampler
                    )
                    warnings.extend(timeline_warnings)

                if warnings:
                    logger.warning(f"Import completed with {len(warnings)} warnings")

                return result

    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid zip file"
        )
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}",
        )


@router.post(
    "/{mission_id}/legs", status_code=status.HTTP_201_CREATED, response_model=MissionLeg
)
async def add_leg_to_mission(
    mission_id: str,
    leg: MissionLeg,
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> MissionLeg:
    """Add a new leg to an existing mission.

    Args:
        mission_id: Mission ID to add leg to
        leg: MissionLeg object to add

    Returns:
        Created leg with 201 status
    """
    try:
        with get_mission_lock(mission_id):
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

            # Generate timeline for the new leg
            if route_manager:
                try:
                    logger.info(f"Generating timeline for new leg {leg.id}")
                    timeline, summary = build_mission_timeline(
                        mission=leg,
                        route_manager=route_manager,
                        poi_manager=poi_manager,
                        coverage_sampler=_coverage_sampler,
                        parent_mission_id=mission_id,
                    )
                    save_mission_timeline(leg.id, timeline)
                    logger.info(f"Timeline generated and saved for new leg {leg.id}")
                except Exception as e:
                    logger.error(
                        f"Failed to generate timeline for new leg {leg.id}: {e}"
                    )
                    # Don't fail the save if timeline generation fails

            logger.info(f"Added leg {leg.id} to mission {mission_id}")
            return leg
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add leg to mission: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add leg to mission: {type(e).__name__}: {str(e)}",
        )


@router.put("/{mission_id}/legs/{leg_id}", response_model=MissionLeg)
async def update_leg(
    mission_id: str,
    leg_id: str,
    updated_leg: MissionLeg,
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> MissionLeg:
    """Update an existing leg in a mission.

    Args:
        mission_id: Mission ID
        leg_id: Leg ID to update
        updated_leg: Updated MissionLeg object

    Returns:
        Updated leg
    """
    try:
        with get_mission_lock(mission_id):
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
            if route_manager:
                try:
                    logger.info(f"Generating timeline for leg {leg_id}")
                    timeline, summary = build_mission_timeline(
                        mission=updated_leg,
                        route_manager=route_manager,
                        poi_manager=poi_manager,
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
        logger.error(f"Failed to update leg: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update leg: {type(e).__name__}: {str(e)}",
        )


@router.delete("/{mission_id}/legs/{leg_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_leg(
    mission_id: str,
    leg_id: str,
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
):
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

        with get_mission_lock(mission_id):
            # Load mission
            mission = load_mission_v2(mission_id)
            if not mission:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Mission {mission_id} not found",
                )

            # Find leg to get its route and POI info
            leg = next((m for m in mission.legs if m.id == leg_id), None)
            if not leg:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Leg {leg_id} not found in mission",
                )

            # Log cascade deletion info
            route_id = leg.route_id or "none"
            logger.info(f"Cascade deletion: leg {leg_id} with route {route_id}")

            # CASCADE DELETE: Delete associated resources
            # 1. Delete route if exists
            if leg.route_id and route_manager:
                try:
                    parsed_route = route_manager.get_route(leg.route_id)
                    if parsed_route:
                        # Delete associated POIs for this route
                        if poi_manager:
                            deleted_pois = poi_manager.delete_route_pois(leg.route_id)
                            logger.info(
                                f"Deleted {deleted_pois} POIs for route {leg.route_id}"
                            )

                        # Delete KML file
                        file_path = Path(parsed_route.metadata.file_path)
                        if file_path.exists():
                            file_path.unlink()
                            logger.info(f"Deleted route file: {file_path}")

                        # Remove from route manager cache
                        route_manager._routes.pop(leg.route_id, None)
                        logger.info(
                            f"Deleted route {leg.route_id} associated with leg {leg_id}"
                        )
                except Exception as e:
                    logger.error(f"Failed to delete route {leg.route_id}: {e}")
                    # Don't fail the entire leg deletion if route deletion fails

            # 2. Delete POIs associated with this leg
            if poi_manager:
                try:
                    if leg.route_id:
                        deleted_leg_pois = poi_manager.delete_leg_pois(
                            route_id=leg.route_id, mission_id=mission_id
                        )
                        logger.info(
                            f"Deleted {deleted_leg_pois} POIs for leg {leg_id} (route {leg.route_id})"
                        )
                    else:
                        logger.info(
                            f"No route associated with leg {leg_id}, skipping POI deletion"
                        )
                except Exception as e:
                    logger.error(f"Failed to delete leg POIs: {e}")
                    # Don't fail the entire leg deletion if POI deletion fails

            # 3. Remove leg from mission and save
            mission.legs = [m for m in mission.legs if m.id != leg_id]
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
        logger.error(f"Failed to delete leg {leg_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete leg: {type(e).__name__}: {str(e)}",
        )


@router.post("/{mission_id}/legs/{leg_id}/activate", response_model=dict)
async def activate_leg(
    mission_id: str,
    leg_id: str,
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> dict:
    """Activate a specific leg (deactivates all others in the mission).

    Args:
        mission_id: Mission ID
        leg_id: Leg ID to activate

    Returns:
        Success response with active leg ID
    """
    try:
        with get_mission_lock(mission_id):
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
            if active_leg and active_leg.route_id and route_manager:
                try:
                    logger.info(
                        f"Activating route {active_leg.route_id} for leg {leg_id}"
                    )
                    route_manager.activate_route(active_leg.route_id)
                    logger.info(f"Route {active_leg.route_id} activated successfully")
                except Exception as e:
                    logger.error(f"Failed to activate route {active_leg.route_id}: {e}")
                    # Don't fail leg activation if route activation fails

            # Generate timeline for the activated leg
            if active_leg and route_manager:
                try:
                    logger.info(f"Generating timeline for leg {leg_id}")
                    timeline, summary = build_mission_timeline(
                        mission=active_leg,
                        route_manager=route_manager,
                        poi_manager=poi_manager,
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
        logger.error(f"Failed to activate leg: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate leg: {type(e).__name__}: {str(e)}",
        )


@router.post("/{mission_id}/legs/deactivate", response_model=dict)
async def deactivate_all_legs(
    mission_id: str,
    route_manager: RouteManager = Depends(get_route_manager),
) -> dict:
    """Deactivate all legs in the mission.

    Args:
        mission_id: Mission ID

    Returns:
        Success response
    """
    try:
        with get_mission_lock(mission_id):
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
            if route_manager:
                try:
                    for leg in mission.legs:
                        if leg.route_id:
                            logger.info(
                                f"Deactivating route {leg.route_id} for leg {leg.id}"
                            )
                            route_manager.deactivate_route(leg.route_id)
                    logger.info(f"Deactivated all routes for mission {mission_id}")
                except Exception as e:
                    logger.error(f"Failed to deactivate routes: {e}")
                    # Don't fail the overall deactivation if route deactivation fails

            logger.info(f"Deactivated all legs in mission {mission_id}")

            return {"status": "success", "message": "All legs deactivated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deactivate legs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate legs: {type(e).__name__}: {str(e)}",
        )


def _validate_aar_windows_against_route(
    aar_windows: list,
    parsed_route,
) -> tuple[list, list[str]]:
    """Validate AAR windows against route waypoint names.

    Args:
        aar_windows: List of AARWindow objects to validate
        parsed_route: ParsedRoute instance with waypoint data

    Returns:
        Tuple of (valid_aar_windows, removed_waypoint_names)
    """
    if not aar_windows:
        return [], []

    # Extract waypoint names from parsed route
    waypoint_names = {wp.name for wp in parsed_route.waypoints if wp.name}

    valid_windows = []
    removed_waypoints = []

    for window in aar_windows:
        start_exists = window.start_waypoint_name in waypoint_names
        end_exists = window.end_waypoint_name in waypoint_names

        if start_exists and end_exists:
            valid_windows.append(window)
        else:
            # Track which waypoints are missing
            if not start_exists:
                removed_waypoints.append(window.start_waypoint_name)
            if not end_exists:
                removed_waypoints.append(window.end_waypoint_name)

            logger.warning(
                f"Removing AAR window {window.id}: waypoints "
                f"'{window.start_waypoint_name}' -> '{window.end_waypoint_name}' "
                f"not found in new route"
            )

    return valid_windows, removed_waypoints


def _import_waypoints_as_pois(
    route_id: str,
    parsed_route,
    poi_manager: POIManager,
) -> tuple[int, int]:
    """Import waypoints from route as POIs.

    Args:
        route_id: Route identifier
        parsed_route: ParsedRoute instance
        poi_manager: POIManager instance

    Returns:
        Tuple of (created_count, skipped_count)
    """
    from app.api.routes.upload import _import_waypoints_as_pois as upload_import_pois

    return upload_import_pois(route_id, parsed_route, poi_manager)


@router.put("/{mission_id}/legs/{leg_id}/route")
@limiter.limit("10/minute")
async def update_leg_route(
    request: Request,
    mission_id: str,
    leg_id: str,
    file: UploadFile = File(...),
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> dict:
    """Update a leg's route via KML file upload.

    Preserves satellite transitions, outages, and transport configurations.
    Validates AAR windows against new route waypoints and removes invalid ones.
    Regenerates timeline with new route while maintaining satellite planning.

    Args:
        request: FastAPI request (for rate limiting)
        mission_id: Mission ID
        leg_id: Leg ID to update route for
        file: Uploaded KML file
        route_manager: RouteManager instance
        poi_manager: POIManager instance

    Returns:
        Updated leg with warnings array if AAR windows were removed

    Raises:
        HTTPException: 400 for invalid file, 404 for mission/leg not found
    """
    try:
        from app.services.kml_parser import KMLParseError

        # Validate file extension
        if not file.filename or not file.filename.endswith(".kml"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must have .kml extension",
            )

        with get_mission_lock(mission_id):
            # Load mission and leg
            mission = load_mission_v2(mission_id)
            if not mission:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Mission {mission_id} not found",
                )

            # Find leg
            leg_index = None
            leg = None
            for i, current_leg in enumerate(mission.legs):
                if current_leg.id == leg_id:
                    leg_index = i
                    leg = current_leg
                    break

            if leg is None or leg_index is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Leg {leg_id} not found in mission {mission_id}",
                )

            old_route_id = leg.route_id

            # Generate unique filename for new route
            routes_dir = Path(route_manager.routes_dir)
            base_name = Path(file.filename).stem
            new_route_path = routes_dir / f"{base_name}.kml"

            # Handle filename conflicts
            counter = 1
            while new_route_path.exists():
                new_route_path = routes_dir / f"{base_name}_{counter}.kml"
                counter += 1

            new_route_id = new_route_path.stem

            # Save new KML file to disk
            try:
                contents = await file.read()
                with open(new_route_path, "wb") as f:
                    f.write(contents)
                logger.info(f"Saved new route file: {new_route_path}")
            except Exception as e:
                logger.error(f"Failed to save route file: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to save route file",
                )

            # Parse uploaded KML file using route manager
            try:
                route_manager._load_route_file(new_route_path)
                parsed_route = route_manager.get_route(new_route_id)

                if not parsed_route:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Failed to parse uploaded KML file",
                    )
            except KMLParseError as e:
                # Clean up file on parse failure
                if new_route_path.exists():
                    new_route_path.unlink()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid KML file: {str(e)}",
                )
            except Exception as e:
                # Clean up file on parse failure
                if new_route_path.exists():
                    new_route_path.unlink()
                logger.error(f"Failed to parse KML file: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to parse KML file",
                )

            # Delete old route file if it exists
            if old_route_id:
                try:
                    old_parsed_route = route_manager.get_route(old_route_id)
                    if old_parsed_route:
                        old_file_path = Path(old_parsed_route.metadata.file_path)
                        if old_file_path.exists():
                            old_file_path.unlink()
                            logger.info(f"Deleted old route file: {old_file_path}")

                        # Remove from route manager cache
                        route_manager._routes.pop(old_route_id, None)
                except Exception as e:
                    logger.warning(f"Failed to delete old route file: {e}")
                    # Don't fail the update if old file deletion fails

            # Update leg's route_id
            leg.route_id = new_route_id

            # Validate AAR windows against new route
            warnings = []
            if leg.transports.aar_windows:
                valid_windows, removed_waypoints = _validate_aar_windows_against_route(
                    leg.transports.aar_windows, parsed_route
                )

                if removed_waypoints:
                    unique_removed = list(set(removed_waypoints))
                    warnings.append(
                        f"Removed AAR windows due to missing waypoints: {', '.join(unique_removed)}"
                    )
                    leg.transports.aar_windows = valid_windows
                    logger.info(
                        f"Removed {len(leg.transports.aar_windows) - len(valid_windows)} "
                        f"AAR windows for leg {leg_id}"
                    )

            # Delete old POIs
            if poi_manager and old_route_id:
                try:
                    deleted_pois = poi_manager.delete_route_pois(old_route_id)
                    logger.info(
                        f"Deleted {deleted_pois} POIs for old route {old_route_id}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to delete old POIs: {e}")

            # Import new POIs from KML waypoints
            if poi_manager:
                try:
                    created, skipped = _import_waypoints_as_pois(
                        new_route_id, parsed_route, poi_manager
                    )
                    logger.info(
                        f"Imported {created} POIs from new route (skipped {skipped})"
                    )
                except Exception as e:
                    logger.warning(f"Failed to import POIs from new route: {e}")

            # Update leg in mission
            mission.legs[leg_index] = leg

            # Save updated mission
            try:
                save_mission_v2(mission)
                logger.info(f"Saved updated mission {mission_id}")
            except Exception as e:
                logger.error(f"Failed to save mission: {e}")
                # Clean up new route file on failure
                if new_route_path.exists():
                    new_route_path.unlink()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to save mission",
                )

            # Regenerate timeline
            if route_manager:
                try:
                    logger.info(f"Regenerating timeline for leg {leg_id}")
                    timeline, summary = build_mission_timeline(
                        mission=leg,
                        route_manager=route_manager,
                        poi_manager=poi_manager,
                        coverage_sampler=_coverage_sampler,
                        parent_mission_id=mission_id,
                    )
                    save_mission_timeline(leg_id, timeline)
                    logger.info(
                        f"Timeline regenerated and saved for leg {leg_id} with new route"
                    )
                except Exception as e:
                    logger.error(f"Failed to regenerate timeline for leg {leg_id}: {e}")
                    warnings.append(f"Timeline regeneration failed: {str(e)}")

            return {
                "leg": leg.model_dump(),
                "warnings": warnings if warnings else None,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update route for leg {leg_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update route: {type(e).__name__}: {str(e)}",
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
        leg = next((m for m in mission.legs if m.id == leg_id), None)
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
        logger.error(f"Failed to get timeline for leg {leg_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve timeline: {type(e).__name__}: {str(e)}",
        )
