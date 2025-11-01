"""Routes API endpoints for KML route management."""

import asyncio
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.core.logging import get_logger
from app.models.route import (
    RouteDetailResponse,
    RouteListResponse,
    RouteResponse,
    RouteStatsResponse,
)
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager

logger = get_logger(__name__)

# Global route manager instance (set by main.py)
_route_manager: Optional[RouteManager] = None
_poi_manager = POIManager()

# Create API router
router = APIRouter(prefix="/api/routes", tags=["routes"])


def set_route_manager(route_manager: RouteManager) -> None:
    """Set the route manager instance (called by main.py during startup)."""
    global _route_manager
    _route_manager = route_manager


@router.get("", response_model=RouteListResponse, summary="List all routes")
async def list_routes(
    active: Optional[bool] = Query(None, description="Filter by active status"),
) -> RouteListResponse:
    """
    List all available KML routes.

    Query Parameters:
    - active: Filter by active status (true/false, or omit for all)

    Returns:
    - List of routes with metadata
    """
    if not _route_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route manager not initialized",
        )

    routes_dict = _route_manager.list_routes()
    active_route_id = _route_manager._active_route_id

    routes_list = []
    for route_id, route_info in routes_dict.items():
        is_active = route_info["is_active"]

        # Filter by active status if requested
        if active is not None and is_active != active:
            continue

        from datetime import datetime
        imported_at = datetime.fromisoformat(route_info["imported_at"])

        route_response = RouteResponse(
            id=route_id,
            name=route_info["name"],
            description=route_info["description"],
            point_count=route_info["point_count"],
            is_active=is_active,
            imported_at=imported_at,
        )
        routes_list.append(route_response)

    return RouteListResponse(routes=routes_list, total=len(routes_list))


@router.get("/{route_id}", response_model=RouteDetailResponse, summary="Get route details")
async def get_route_detail(route_id: str) -> RouteDetailResponse:
    """
    Get detailed information about a specific route.

    Path Parameters:
    - route_id: Route identifier (filename without .kml extension)

    Returns:
    - Full route details including all points and statistics
    """
    if not _route_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route manager not initialized",
        )

    parsed_route = _route_manager.get_route(route_id)
    if not parsed_route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route not found: {route_id}",
        )

    active_route_id = _route_manager._active_route_id
    is_active = route_id == active_route_id

    distance_m = parsed_route.get_total_distance()
    bounds = parsed_route.get_bounds()

    return RouteDetailResponse(
        id=route_id,
        name=parsed_route.metadata.name,
        description=parsed_route.metadata.description,
        point_count=parsed_route.metadata.point_count,
        is_active=is_active,
        imported_at=parsed_route.metadata.imported_at,
        file_path=parsed_route.metadata.file_path,
        points=parsed_route.points,
        statistics={
            "distance_meters": distance_m,
            "distance_km": distance_m / 1000,
            "bounds": bounds,
        },
    )


@router.post("/{route_id}/activate", response_model=RouteResponse, summary="Activate a route")
async def activate_route(route_id: str) -> RouteResponse:
    """
    Activate a route for tracking and visualization.

    Path Parameters:
    - route_id: Route identifier

    Returns:
    - Updated route information
    """
    if not _route_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route manager not initialized",
        )

    parsed_route = _route_manager.get_route(route_id)
    if not parsed_route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route not found: {route_id}",
        )

    _route_manager.activate_route(route_id)

    return RouteResponse(
        id=route_id,
        name=parsed_route.metadata.name,
        description=parsed_route.metadata.description,
        point_count=parsed_route.metadata.point_count,
        is_active=True,
        imported_at=parsed_route.metadata.imported_at,
    )


@router.post("/deactivate", response_model=dict, summary="Deactivate active route")
async def deactivate_route() -> dict:
    """
    Deactivate the currently active route.

    Returns:
    - Status message
    """
    if not _route_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route manager not initialized",
        )

    _route_manager.deactivate_route()

    return {"message": "Route deactivated successfully"}


@router.get("/{route_id}/stats", response_model=RouteStatsResponse, summary="Get route statistics")
async def get_route_stats(route_id: str) -> RouteStatsResponse:
    """
    Get statistics for a specific route.

    Path Parameters:
    - route_id: Route identifier

    Returns:
    - Route statistics (distance, point count, bounds)
    """
    if not _route_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route manager not initialized",
        )

    parsed_route = _route_manager.get_route(route_id)
    if not parsed_route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route not found: {route_id}",
        )

    distance_m = parsed_route.get_total_distance()
    bounds = parsed_route.get_bounds()

    return RouteStatsResponse(
        distance_meters=distance_m,
        distance_km=distance_m / 1000,
        point_count=parsed_route.metadata.point_count,
        bounds=bounds,
    )


@router.post("/upload", response_model=RouteResponse, status_code=status.HTTP_201_CREATED, summary="Upload KML route")
async def upload_route(file: UploadFile = File(...)) -> RouteResponse:
    """
    Upload a new KML route file.

    Form Data:
    - file: KML file (multipart/form-data)

    Returns:
    - Route information for uploaded file
    """
    if not _route_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route manager not initialized",
        )

    # Validate file extension
    if not file.filename or not file.filename.endswith(".kml"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .kml files are allowed",
        )

    try:
        # Ensure directory exists
        routes_dir = Path("/data/routes")
        routes_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename (handle conflicts)
        file_path = routes_dir / file.filename
        counter = 1
        base_path = file_path

        while file_path.exists():
            stem = base_path.stem
            file_path = routes_dir / f"{stem}-{counter}.kml"
            counter += 1

        # Write file to disk
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(
            f"KML file uploaded: {file.filename} (size: {len(content)} bytes)"
        )

        # Give watchdog time to detect and parse the file
        await asyncio.sleep(0.2)

        # Get parsed route
        route_id = file_path.stem
        parsed_route = _route_manager.get_route(route_id)

        if not parsed_route:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse KML file: {file.filename}",
            )

        return RouteResponse(
            id=route_id,
            name=parsed_route.metadata.name,
            description=parsed_route.metadata.description,
            point_count=parsed_route.metadata.point_count,
            is_active=False,
            imported_at=parsed_route.metadata.imported_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading route {file.filename}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading route: {str(e)}",
        )


@router.get("/{route_id}/download", summary="Download KML route")
async def download_route(route_id: str):
    """
    Download a KML route file.

    Path Parameters:
    - route_id: Route identifier

    Returns:
    - KML file content
    """
    if not _route_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route manager not initialized",
        )

    parsed_route = _route_manager.get_route(route_id)
    if not parsed_route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route not found: {route_id}",
        )

    file_path = Path(parsed_route.metadata.file_path)

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route file not found: {file_path}",
        )

    return FileResponse(
        path=file_path,
        media_type="application/vnd.google-earth.kml+xml",
        filename=file_path.name,
    )


@router.delete("/{route_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a route")
async def delete_route(route_id: str):
    """
    Delete a route and its associated POIs.

    Path Parameters:
    - route_id: Route identifier

    Returns:
    - No content (204)
    """
    if not _route_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route manager not initialized",
        )

    parsed_route = _route_manager.get_route(route_id)
    if not parsed_route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route not found: {route_id}",
        )

    try:
        # Delete associated POIs (cascade delete)
        deleted_pois = _poi_manager.delete_route_pois(route_id)
        logger.info(f"Deleted {deleted_pois} POIs for route {route_id}")

        # Delete KML file
        file_path = Path(parsed_route.metadata.file_path)
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted route file: {file_path} for route {route_id}")

        # Remove from route manager cache
        _route_manager._routes.pop(route_id, None)

    except Exception as e:
        logger.error(f"Error deleting route {route_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting route: {str(e)}",
        )
