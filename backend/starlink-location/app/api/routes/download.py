"""Route download endpoint."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.responses import FileResponse
from app.core.limiter import limiter

from app.core.logging import get_logger
from app.services.route_manager import RouteManager
from app.mission.dependencies import get_route_manager

logger = get_logger(__name__)

router = APIRouter()


@router.get("/{route_id}/download", summary="Download KML route")
@limiter.limit("20/minute")
async def download_route(
    request: Request,
    route_id: str,
    route_manager: RouteManager = Depends(get_route_manager),
) -> FileResponse:
    """Download a KML route file.

    Retrieves the KML file for a specific route and returns it as a
    downloadable file with the appropriate MIME type.

    Args:
        request: FastAPI request object (required for rate limiting)
        route_id: Unique identifier of the route to download
        route_manager: Injected RouteManager dependency for route operations

    Returns:
        FileResponse containing the KML file with proper headers and MIME type

    Raises:
        HTTPException: 404 if route or file not found, 500 if manager not initialized
    """
    if not route_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route manager not initialized",
        )

    parsed_route = route_manager.get_route(route_id)
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
