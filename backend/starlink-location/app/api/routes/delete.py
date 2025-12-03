"""Route deletion endpoint."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, status

from app.core.logging import get_logger
from app.services.route_manager import RouteManager
from app.services.poi_manager import POIManager
from app.mission.dependencies import get_route_manager, get_poi_manager

logger = get_logger(__name__)

router = APIRouter()


@router.delete(
    "/{route_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a route"
)
async def delete_route(
    route_id: str,
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> None:
    """Delete a route and its associated POIs.

    Removes the route file from disk, deletes all POIs associated with the route,
    and removes the route from the manager's cache. This is a cascade delete
    operation.

    Args:
        route_id: Unique identifier of the route to delete
        route_manager: Injected RouteManager dependency for route operations
        poi_manager: Injected POIManager dependency for POI cascade deletion

    Raises:
        HTTPException: 404 if route not found, 500 if deletion fails
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

    try:
        # Delete associated POIs (cascade delete)
        if poi_manager:
            deleted_pois = poi_manager.delete_route_pois(route_id)
            logger.info(f"Deleted {deleted_pois} POIs for route {route_id}")

        # Delete KML file
        file_path = Path(parsed_route.metadata.file_path)
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted route file: {file_path} for route {route_id}")

        # Remove from route manager cache
        route_manager._routes.pop(route_id, None)

    except Exception as e:
        logger.error(f"Error deleting route {route_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting route: {str(e)}",
        )
