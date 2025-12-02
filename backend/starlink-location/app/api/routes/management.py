"""Route management endpoints (list, get, activate, deactivate)."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends, status

from app.core.logging import get_logger
from app.models.route import RouteListResponse, RouteDetailResponse, RouteResponse
from app.services.route_manager import RouteManager
from app.services.poi_manager import POIManager
from app.mission.dependencies import get_route_manager, get_poi_manager

logger = get_logger(__name__)

# Router for core management endpoints
router = APIRouter()


@router.get("/", response_model=RouteListResponse, summary="List all routes")
async def list_routes(
    active: Optional[bool] = Query(None, description="Filter by active status"),
    route_manager: RouteManager = Depends(get_route_manager),
) -> RouteListResponse:
    """
    List all available KML routes.

    Query Parameters:
    - active: Filter by active status (true/false, or omit for all)

    Returns:
    - List of routes with metadata including `flight_phase`, `eta_mode`,
      `has_timing_data`, and active route context

    Example:
        ```bash
        curl http://localhost:8000/api/routes | jq '.routes[0]'
        ```
    """
    if not route_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route manager not initialized",
        )

    routes_dict = route_manager.list_routes()

    flight_status_snapshot = None
    try:
        from app.services.flight_state_manager import get_flight_state_manager

        flight_status_snapshot = get_flight_state_manager().get_status()
    except Exception as state_error:  # pragma: no cover - defensive guard
        logger.debug("Flight state unavailable while listing routes: %s", state_error)

    routes_list = []
    for route_id, route_info in routes_dict.items():
        is_active = route_info["is_active"]

        # Filter by active status if requested
        if active is not None and is_active != active:
            continue

        imported_at = datetime.fromisoformat(route_info["imported_at"])

        # Get parsed route to check for timing data
        parsed_route = route_manager.get_route(route_id)
        has_timing_data = False
        timing_profile = None
        flight_phase = None
        if parsed_route and parsed_route.timing_profile:
            timing_profile = parsed_route.timing_profile
            has_timing_data = timing_profile.has_timing_data
            flight_phase = timing_profile.flight_status

        eta_mode = None
        if is_active and flight_status_snapshot:
            flight_phase = flight_status_snapshot.phase.value
            eta_mode = flight_status_snapshot.eta_mode.value

        route_response = RouteResponse(
            id=route_id,
            name=route_info["name"],
            description=route_info["description"],
            point_count=route_info["point_count"],
            is_active=is_active,
            imported_at=imported_at,
            has_timing_data=has_timing_data,
            timing_profile=timing_profile,
            flight_phase=flight_phase,
            eta_mode=eta_mode,
        )
        routes_list.append(route_response)

    return RouteListResponse(routes=routes_list, total=len(routes_list))


@router.get(
    "/{route_id}", response_model=RouteDetailResponse, summary="Get route details"
)
async def get_route_detail(
    route_id: str,
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> RouteDetailResponse:
    """Get detailed information about a specific route with timing/flight metadata."""
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

    active_route_id = route_manager._active_route_id
    is_active = route_id == active_route_id

    distance_m = parsed_route.get_total_distance()
    bounds = parsed_route.get_bounds()
    poi_count = 0
    if poi_manager:
        poi_count = poi_manager.count_pois(route_id=route_id)

    timing_profile = parsed_route.timing_profile
    has_timing_data = bool(timing_profile and timing_profile.has_timing_data)
    flight_phase = timing_profile.flight_status if timing_profile else None
    eta_mode = None

    if is_active:
        try:
            from app.services.flight_state_manager import get_flight_state_manager

            status_snapshot = get_flight_state_manager().get_status()
            flight_phase = status_snapshot.phase.value
            eta_mode = status_snapshot.eta_mode.value
        except Exception as state_error:  # pragma: no cover - defensive guard
            logger.debug("Flight state unavailable for route detail: %s", state_error)

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
        poi_count=poi_count,
        waypoints=parsed_route.waypoints,
        timing_profile=timing_profile,
        has_timing_data=has_timing_data,
        flight_phase=flight_phase,
        eta_mode=eta_mode,
    )


@router.post(
    "/{route_id}/activate", response_model=RouteResponse, summary="Activate a route"
)
async def activate_route(
    route_id: str,
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> RouteResponse:
    """
    Activate a route for tracking and visualization.

    Path Parameters:
    - route_id: Route identifier

    Returns:
    - Updated route information including live `flight_phase`, `eta_mode`,
      and timing profile context

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/routes/{route_id}/activate | \
          jq '.eta_mode'
        ```
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

    route_manager.activate_route(route_id)

    # Calculate POI projections for the newly activated route
    if poi_manager:
        try:
            projected_count = poi_manager.calculate_poi_projections(parsed_route)
            logger.info(
                f"Calculated projections for {projected_count} POIs on route "
                f"activation"
            )
            # Reload POIs to ensure in-memory cache has the projection data
            poi_manager.reload_pois()
        except Exception as e:
            logger.error(f"Failed to calculate POI projections: {e}")

    has_timing_data = False
    flight_phase = None
    eta_mode = None
    if parsed_route.timing_profile:
        has_timing_data = parsed_route.timing_profile.has_timing_data
        flight_phase = parsed_route.timing_profile.flight_status

    try:
        from app.services.flight_state_manager import get_flight_state_manager
        from app.models.route import RouteTimingProfile

        status_snapshot = get_flight_state_manager().get_status()
        flight_phase = status_snapshot.phase.value
        eta_mode = status_snapshot.eta_mode.value

        timing_profile = parsed_route.timing_profile
        if timing_profile is None:
            timing_profile = RouteTimingProfile()
            parsed_route.timing_profile = timing_profile

        timing_profile.flight_status = flight_phase
        timing_profile.actual_departure_time = status_snapshot.departure_time
        timing_profile.actual_arrival_time = status_snapshot.arrival_time
    except Exception as state_error:  # pragma: no cover - defensive guard
        logger.debug("Flight state unavailable while activating route: %s", state_error)

    return RouteResponse(
        id=route_id,
        name=parsed_route.metadata.name,
        description=parsed_route.metadata.description,
        point_count=parsed_route.metadata.point_count,
        is_active=True,
        imported_at=parsed_route.metadata.imported_at,
        has_timing_data=has_timing_data,
        timing_profile=parsed_route.timing_profile,
        flight_phase=flight_phase,
        eta_mode=eta_mode,
    )


@router.post("/deactivate", response_model=dict, summary="Deactivate active route")
async def deactivate_route(
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> dict:
    """
    Deactivate the currently active route.

    Returns:
    - Status message
    """
    if not route_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route manager not initialized",
        )

    route_manager.deactivate_route()

    # Clear POI projections on route deactivation
    if poi_manager:
        try:
            cleared_count = poi_manager.clear_poi_projections()
            logger.info(
                f"Cleared projections for {cleared_count} POIs on route "
                f"deactivation"
            )
        except Exception as e:
            logger.error(f"Failed to clear POI projections: {e}")

    return {"message": "Route deactivated successfully"}
