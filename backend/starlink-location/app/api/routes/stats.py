"""Route statistics endpoint."""

from fastapi import APIRouter, HTTPException, Depends, status

from app.core.logging import get_logger
from app.models.route import RouteStatsResponse
from app.services.route_manager import RouteManager
from app.mission.dependencies import get_route_manager

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/{route_id}/stats",
    response_model=RouteStatsResponse,
    summary="Get route statistics",
)
async def get_route_stats(
    route_id: str,
    route_manager: RouteManager = Depends(get_route_manager),
) -> RouteStatsResponse:
    """Get statistics for a specific route.

    Calculates and returns key statistics including total distance, point count,
    and geographic bounding box for the specified route.

    Args:
        route_id: Unique identifier of the route to analyze
        route_manager: Injected RouteManager dependency for route operations

    Returns:
        RouteStatsResponse with distance metrics, point count, and coordinate bounds

    Raises:
        HTTPException: 404 if route not found, 500 if manager not initialized
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

    distance_m = parsed_route.get_total_distance()
    bounds = parsed_route.get_bounds()

    return RouteStatsResponse(
        distance_meters=distance_m,
        distance_km=distance_m / 1000,
        point_count=parsed_route.metadata.point_count,
        bounds=bounds,
    )
