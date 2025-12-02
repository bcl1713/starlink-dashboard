"""Route ETA calculation endpoints."""

from fastapi import APIRouter, HTTPException, Query, Depends, status

from app.core.logging import get_logger
from app.services.route_manager import RouteManager
from app.services.route_eta_calculator import RouteETACalculator
from app.mission.dependencies import get_route_manager

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/{route_id}/eta/waypoint/{waypoint_index}",
    summary="Calculate ETA to waypoint",
)
async def calculate_eta_to_waypoint(
    route_id: str,
    waypoint_index: int,
    current_position_lat: float = Query(
        ..., description="Current latitude in decimal degrees"
    ),
    current_position_lon: float = Query(
        ..., description="Current longitude in decimal degrees"
    ),
    route_manager: RouteManager = Depends(get_route_manager),
) -> dict:
    """
    Calculate estimated time of arrival (ETA) to a specific waypoint.

    Path Parameters:
    - route_id: Route identifier
    - waypoint_index: Index of the waypoint in the route

    Query Parameters:
    - current_position_lat: Current latitude
    - current_position_lon: Current longitude

    Returns:
    - Dictionary with waypoint info and ETA details
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

    if waypoint_index >= len(parsed_route.waypoints):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Waypoint index {waypoint_index} out of range "
                f"(route has {len(parsed_route.waypoints)} waypoints)"
            ),
        )

    try:
        calculator = RouteETACalculator(parsed_route)
        eta_data = calculator.calculate_eta_to_waypoint(
            waypoint_index,
            current_position_lat,
            current_position_lon,
        )
        return eta_data
    except Exception as e:
        logger.error(f"Error calculating ETA for route {route_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating ETA: {str(e)}",
        )


@router.get("/{route_id}/eta/location", summary="Calculate ETA to arbitrary location")
async def calculate_eta_to_location(
    route_id: str,
    latitude: float = Query(..., description="Target latitude in decimal degrees"),
    longitude: float = Query(..., description="Target longitude in decimal degrees"),
    current_position_lat: float = Query(
        ..., description="Current latitude in decimal degrees"
    ),
    current_position_lon: float = Query(
        ..., description="Current longitude in decimal degrees"
    ),
    route_manager: RouteManager = Depends(get_route_manager),
) -> dict:
    """
    Calculate estimated time of arrival (ETA) to an arbitrary location.

    Path Parameters:
    - route_id: Route identifier

    Query Parameters:
    - latitude: Target latitude
    - longitude: Target longitude
    - current_position_lat: Current latitude
    - current_position_lon: Current longitude

    Returns:
    - Dictionary with location info and ETA details
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
        calculator = RouteETACalculator(parsed_route)
        eta_data = calculator.calculate_eta_to_location(
            latitude,
            longitude,
            current_position_lat,
            current_position_lon,
        )
        return eta_data
    except Exception as e:
        logger.error(f"Error calculating ETA for route {route_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating ETA: {str(e)}",
        )


@router.get("/{route_id}/progress", summary="Get route progress metrics")
async def get_route_progress(
    route_id: str,
    current_position_lat: float = Query(
        ..., description="Current latitude in decimal degrees"
    ),
    current_position_lon: float = Query(
        ..., description="Current longitude in decimal degrees"
    ),
    route_manager: RouteManager = Depends(get_route_manager),
) -> dict:
    """
    Get route progress metrics including distance traveled and ETA to destination.

    Path Parameters:
    - route_id: Route identifier

    Query Parameters:
    - current_position_lat: Current latitude
    - current_position_lon: Current longitude

    Returns:
    - Dictionary with progress metrics
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
        calculator = RouteETACalculator(parsed_route)
        progress_data = calculator.get_route_progress(
            current_position_lat,
            current_position_lon,
        )
        return progress_data
    except Exception as e:
        logger.error(f"Error calculating route progress for {route_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating progress: {str(e)}",
        )


@router.get("/live-mode/active-route-eta", summary="Get active route ETA for live mode")
async def get_live_mode_active_route_eta(
    current_position_lat: float = Query(..., description="Current latitude"),
    current_position_lon: float = Query(..., description="Current longitude"),
    current_speed_knots: float = Query(
        default=500.0, description="Current speed in knots"
    ),
    route_manager: RouteManager = Depends(get_route_manager),
) -> dict:
    """
    Get ETA calculations for the active route in live mode.

    Useful for real-time position updates from Starlink terminal.

    Query Parameters:
    - current_position_lat: Current latitude
    - current_position_lon: Current longitude
    - current_speed_knots: Current speed in knots (default: 500)

    Returns:
    - Dictionary with ETA to next waypoint, remaining distance, and timing info
    """
    if not route_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route manager not initialized",
        )

    parsed_route = route_manager.get_active_route()
    if not parsed_route:
        return {"has_active_route": False, "message": "No active route"}

    try:
        calculator = RouteETACalculator(parsed_route)

        # Get progress metrics
        progress = calculator.get_route_progress(
            current_position_lat, current_position_lon
        )

        # Get timing profile
        timing_info = {}
        if parsed_route.timing_profile:
            timing_info = {
                "has_timing_data": parsed_route.timing_profile.has_timing_data,
                "departure_time": (
                    parsed_route.timing_profile.departure_time.isoformat()
                    if parsed_route.timing_profile.departure_time
                    else None
                ),
                "arrival_time": (
                    parsed_route.timing_profile.arrival_time.isoformat()
                    if parsed_route.timing_profile.arrival_time
                    else None
                ),
                "total_duration_seconds": (
                    parsed_route.timing_profile.total_expected_duration_seconds
                ),
            }

        # Find next waypoint and calculate ETA
        nearest_idx, _ = calculator.find_nearest_point(
            current_position_lat, current_position_lon
        )
        next_waypoint_idx = (
            nearest_idx + 1
            if nearest_idx < len(parsed_route.waypoints) - 1
            else nearest_idx
        )

        next_eta = None
        if next_waypoint_idx < len(parsed_route.waypoints):
            next_eta = calculator.calculate_eta_to_waypoint(
                next_waypoint_idx,
                current_position_lat,
                current_position_lon,
            )

        return {
            "has_active_route": True,
            "route_name": parsed_route.metadata.name or "Unknown",
            "current_position": {
                "latitude": current_position_lat,
                "longitude": current_position_lon,
                "speed_knots": current_speed_knots,
            },
            "progress": progress,
            "timing_profile": timing_info,
            "next_waypoint_eta": next_eta,
        }
    except Exception as e:
        logger.error(f"Error calculating live mode ETA: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating ETA: {str(e)}",
        )
