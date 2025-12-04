"""Route ETA calculation endpoints."""

# FR-004: File exceeds 300 lines (311 lines) because route ETA API combines
# multiple ETA calculation modes, status filtering, and distance metrics.
# Splitting would fragment related ETA calculation endpoints. Deferred to v0.4.0.

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
    """Calculate estimated time of arrival (ETA) to a specific waypoint.

    Computes the ETA from current position to a specific waypoint on the route
    using route-aware calculations that account for the path along the route.

    Args:
        route_id: Unique identifier of the route
        waypoint_index: Zero-based index of the target waypoint
        current_position_lat: Current latitude in decimal degrees
        current_position_lon: Current longitude in decimal degrees
        route_manager: Injected RouteManager dependency for route operations

    Returns:
        Dictionary containing waypoint details, eta_seconds, distance_meters,
        and route progress information

    Raises:
        HTTPException: 404 if route not found, 400 if waypoint index invalid,
                      500 if calculation fails
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
    """Calculate estimated time of arrival (ETA) to an arbitrary location.

    Computes ETA from current position to any specified coordinate using
    route-aware calculation that projects the location onto the route path.

    Args:
        route_id: Unique identifier of the route
        latitude: Target latitude in decimal degrees
        longitude: Target longitude in decimal degrees
        current_position_lat: Current latitude in decimal degrees
        current_position_lon: Current longitude in decimal degrees
        route_manager: Injected RouteManager dependency for route operations

    Returns:
        Dictionary containing target location details, eta_seconds, distance_meters,
        and projected route information

    Raises:
        HTTPException: 404 if route not found, 500 if calculation fails
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
    """Get route progress metrics including distance traveled and ETA to destination.

    Calculates comprehensive progress information including percentage complete,
    distance traveled, distance remaining, current waypoint, and ETA to final
    destination.

    Args:
        route_id: Unique identifier of the route
        current_position_lat: Current latitude in decimal degrees
        current_position_lon: Current longitude in decimal degrees
        route_manager: Injected RouteManager dependency for route operations

    Returns:
        Dictionary with progress_percent, distance_traveled_meters,
        distance_remaining_meters, current_waypoint_index, and eta_to_destination_seconds

    Raises:
        HTTPException: 404 if route not found, 500 if calculation fails
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
    """Get ETA calculations for the active route in live mode.

    Designed for real-time position updates from Starlink terminal. Provides
    comprehensive route progress, timing profile, and next waypoint ETA
    information for the currently active route.

    Args:
        current_position_lat: Current latitude in decimal degrees
        current_position_lon: Current longitude in decimal degrees
        current_speed_knots: Current speed in knots (default: 500.0)
        route_manager: Injected RouteManager dependency for route operations

    Returns:
        Dictionary with has_active_route flag, route_name, current_position,
        progress metrics, timing_profile, and next_waypoint_eta. Returns
        minimal dict with has_active_route=False if no route is active.

    Raises:
        HTTPException: 500 if calculation fails or manager not initialized
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
