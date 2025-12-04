"""ETA and distance calculation endpoints for POIs.

File Size Note (FR-004 Exception):
This module exceeds the 300-line constitutional limit (400 lines) due to:
- Complex dual-mode ETA calculation (anticipated vs estimated)
- Route-aware status determination with multi-condition logic
- Multiple filtering mechanisms (status, category, active_only)
- Haversine distance calculations and bearing computations
- Comprehensive docstrings for API documentation

The get_pois_with_etas() endpoint is a single monolithic calculation that
interweaves telemetry, coordinator integration, flight state, route progress,
and filtering in a manner that cannot be cleanly separated without losing
contextual integrity. The endpoint represents one cohesive business operation
with multiple internal concerns that are interdependent.

Deferred for future refactoring with potential separation of:
- Calculation logic into services
- Filtering into separate utilities
- Status determination into dedicated calculators
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status, Depends

from app.models.poi import POIETAListResponse, POIWithETA
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from app.mission.dependencies import get_route_manager, get_poi_manager

from .helpers import (
    calculate_bearing,
    calculate_course_status,
    calculate_poi_active_status,
)

logger = logging.getLogger(__name__)

# Global coordinator reference for accessing telemetry
_coordinator: Optional[object] = None


def set_coordinator(coordinator: object) -> None:
    """Set the simulation coordinator reference for POI ETA calculations.

    Stores a reference to the coordinator to enable access to real-time
    telemetry data for ETA and distance calculations.

    Args:
        coordinator: Simulation coordinator instance providing telemetry
    """
    global _coordinator
    _coordinator = coordinator


# Create API router for ETA endpoints
# NOTE: Prefix is NOT set here - it's handled at the module level in __init__.py
router = APIRouter(tags=["pois"])


@router.get(
    "/etas",
    response_model=POIETAListResponse,
    summary="Get all POIs with real-time ETA data",
)
async def get_pois_with_etas(
    route_id: Optional[str] = Query(None, description="Filter by route ID"),
    latitude: Optional[str] = Query(
        None, description="Current latitude (decimal degrees)"
    ),
    longitude: Optional[str] = Query(
        None, description="Current longitude (decimal degrees)"
    ),
    speed_knots: Optional[str] = Query(None, description="Current speed in knots"),
    status_filter: Optional[str] = Query(
        None,
        description="Filter by course status (comma-separated: on_course,slightly_off,off_track,behind)",
    ),
    category: Optional[str] = Query(
        None,
        description="Filter by POI category (comma-separated: departure,arrival,waypoint,alternate)",
    ),
    active_only: bool = Query(
        True,
        description="Filter to show only active POIs (default: true). Set to false to see all POIs with active field populated.",
    ),
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> POIETAListResponse:
    """Get all POIs with real-time ETA and distance data.

    This endpoint calculates ETA and distance for all POIs based on current position and speed.
    When an active route exists, POIs are filtered by route progress (showing only future POIs).
    Uses coordinator telemetry if available, otherwise uses query parameters or fallback values.

    Query Parameters:
    - route_id: Optional route ID to filter by
    - latitude: Current latitude (optional, uses coordinator if available)
    - longitude: Current longitude (optional, uses coordinator if available)
    - speed_knots: Current speed in knots (optional, uses coordinator if available)
    - status: Optional course status filter (comma-separated list of: on_course, slightly_off, off_track, behind)
    - category: Optional POI category filter (comma-separated list of: departure, arrival, waypoint, alternate)

    Returns:
    - JSON object containing:
      - `pois`: List of POIs with ETA metadata (eta_seconds, distance_meters, eta_type, flight_phase, is_pre_departure)
      - `eta_mode`: Current ETA mode (`anticipated` or `estimated`)
      - `flight_phase`: Current flight phase (`pre_departure`, `in_flight`, `post_arrival`)
      - `timestamp`: ISO8601 timestamp of the calculation

    Example:
        ```bash
        curl http://localhost:8000/api/pois/etas | jq '.pois[0]'
        ```

    Raises:
    - 400: Failed to calculate ETA
    """
    try:
        # Get current position from coordinator if available
        heading = 0.0  # Default heading
        current_route_progress = None
        active_route = None

        if _coordinator:
            try:
                telemetry = _coordinator.get_current_telemetry()
                latitude = telemetry.position.latitude
                longitude = telemetry.position.longitude
                speed_knots = telemetry.position.speed
                heading = telemetry.position.heading

                # Get active route and current progress
                if hasattr(_coordinator, "route_manager"):
                    active_route = _coordinator.route_manager.get_active_route()
                    # Get progress from position simulator if available
                    if (
                        hasattr(_coordinator, "position_sim")
                        and _coordinator.position_sim
                    ):
                        current_route_progress = (
                            _coordinator.position_sim.progress * 100.0
                            if _coordinator.position_sim.progress
                            else None
                        )
            except Exception:
                # Fall back to query parameters if coordinator fails
                latitude = None
                longitude = None
                speed_knots = None

        # If coordinator doesn't have route manager or is unavailable, try route_manager directly
        if not active_route and route_manager:
            active_route = route_manager.get_active_route()

        active_route_id = None
        if active_route and active_route.metadata and active_route.metadata.file_path:
            try:
                active_route_id = Path(active_route.metadata.file_path).stem
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.debug("Failed to derive active route ID from metadata: %s", exc)
                active_route_id = active_route.metadata.file_path

        # Use query parameters if provided (override coordinator)
        if latitude is None or latitude == "":
            latitude = 41.6 if _coordinator is None else latitude
        else:
            try:
                latitude = float(latitude)
            except (ValueError, TypeError):
                latitude = 41.6 if _coordinator is None else latitude

        if longitude is None or longitude == "":
            longitude = -74.0 if _coordinator is None else longitude
        else:
            try:
                longitude = float(longitude)
            except (ValueError, TypeError):
                longitude = -74.0 if _coordinator is None else longitude

        if speed_knots is None or speed_knots == "":
            speed_knots = 67.0 if _coordinator is None else speed_knots
        else:
            try:
                speed_knots = float(speed_knots)
            except (ValueError, TypeError):
                speed_knots = 67.0 if _coordinator is None else speed_knots

        # In live mode we may not have simulator progress; derive it from the active route instead.
        if (
            active_route
            and current_route_progress is None
            and latitude is not None
            and longitude is not None
        ):
            try:
                from app.services.route_eta_calculator import RouteETACalculator

                route_calculator = RouteETACalculator(active_route)
                progress_info = route_calculator.get_route_progress(latitude, longitude)
                current_route_progress = progress_info.get("progress_percent")
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.debug("Failed to calculate route progress for POI ETAs: %s", exc)
                current_route_progress = None

        # Parse status filter if provided
        status_filter_set = set()
        if status_filter:
            status_filter_set = set(
                s.strip() for s in status_filter.split(",") if s.strip()
            )

        # Parse category filter if provided
        category_filter = set()
        if category:
            category_filter = set(c.strip() for c in category.split(",") if c.strip())

        if not poi_manager:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="POI manager not initialized",
            )

        pois = poi_manager.list_pois(route_id=route_id)

        # Calculate ETA and distance for each POI
        from app.core.eta_service import get_eta_calculator
        from app.services.flight_state import get_flight_state_manager
        from app.models.flight_status import ETAMode, FlightPhase

        eta_calc = get_eta_calculator()

        status_snapshot = None
        try:
            flight_state = get_flight_state_manager()
            status_snapshot = flight_state.get_status()
        except Exception as state_error:  # pragma: no cover - defensive guard
            logger.debug("Flight state unavailable for POI ETAs: %s", state_error)

        if status_snapshot:
            current_eta_mode = status_snapshot.eta_mode
            flight_phase_value = status_snapshot.phase.value
            is_pre_departure = status_snapshot.phase == FlightPhase.PRE_DEPARTURE
        else:
            current_eta_mode = ETAMode.ESTIMATED
            flight_phase_value = None
            is_pre_departure = False

        pois_with_eta = []
        progress_epsilon = 0.05  # Prevent jitter from flipping ahead/passed status
        route_projection_distance_threshold_m = (
            20000.0  # Treat POIs beyond 20km as off-route
        )

        for poi in pois:
            # Calculate distance using Haversine formula
            distance = eta_calc.calculate_distance(
                latitude, longitude, poi.latitude, poi.longitude
            )

            # Calculate ETA - use dual-mode calculation
            eta_seconds = None
            eta_type = current_eta_mode.value

            if active_route:
                # Try route-aware ETA calculation first with mode-specific logic
                if current_eta_mode == ETAMode.ESTIMATED:
                    eta_seconds = eta_calc._calculate_route_aware_eta_estimated(
                        latitude, longitude, poi, active_route, speed_knots
                    )
                else:  # ANTICIPATED mode
                    eta_seconds = eta_calc._calculate_route_aware_eta_anticipated(
                        latitude, longitude, poi, active_route
                    )

            # Fall back to distance/speed calculation if route-aware failed
            if eta_seconds is None:
                if current_eta_mode == ETAMode.ESTIMATED:
                    eta_seconds = eta_calc.calculate_eta(distance, speed_knots)
                else:  # ANTICIPATED mode fallback: use default cruise speed
                    eta_seconds = eta_calc.calculate_eta(
                        distance, eta_calc.default_speed_knots
                    )

            # Calculate bearing
            bearing = calculate_bearing(
                latitude, longitude, poi.latitude, poi.longitude
            )

            # Calculate course status
            course_status = calculate_course_status(heading, bearing)

            # Determine route-aware status
            projected_waypoint_index = None
            projected_route_progress = None
            route_aware_status = None

            projected_distance_to_route = None
            if (
                poi.projected_latitude is not None
                and poi.projected_longitude is not None
            ):
                projected_distance_to_route = eta_calc.calculate_distance(
                    poi.latitude,
                    poi.longitude,
                    poi.projected_latitude,
                    poi.projected_longitude,
                )

            belongs_to_active_route = bool(
                active_route
                and active_route_id
                and poi.route_id
                and poi.route_id == active_route_id
            )
            close_to_route = bool(
                projected_distance_to_route is not None
                and projected_distance_to_route <= route_projection_distance_threshold_m
            )

            is_on_active_route = bool(
                active_route
                and belongs_to_active_route
                and (projected_distance_to_route is None or close_to_route)
            )

            if active_route and poi.projected_route_progress is not None:
                projected_waypoint_index = poi.projected_waypoint_index
                projected_route_progress = poi.projected_route_progress

                if is_on_active_route:
                    if current_route_progress is not None:
                        if projected_route_progress >= (
                            current_route_progress - progress_epsilon
                        ):
                            route_aware_status = "ahead_on_route"
                        else:
                            route_aware_status = "already_passed"
                    else:
                        route_aware_status = "ahead_on_route"
                else:
                    route_aware_status = "not_on_route"
            elif active_route and not is_on_active_route:
                route_aware_status = "not_on_route"

            # Preserve ETA visibility for standalone POIs during pre-departure countdowns
            if route_aware_status == "not_on_route" and is_pre_departure:
                route_aware_status = "pre_departure"

            # If anticipated ETA returned negative time but POI is still ahead, fall back to distance-based estimate
            if (
                current_eta_mode == ETAMode.ANTICIPATED
                and route_aware_status == "ahead_on_route"
                and (eta_seconds is None or eta_seconds < 0)
            ):
                eta_seconds = eta_calc.calculate_eta(
                    distance, eta_calc.default_speed_knots
                )

            # Apply status filter if specified
            # When a route is active and POI is on the route, use route-aware filtering
            # Otherwise, fall back to angle-based filtering
            if status_filter_set:
                if active_route and is_on_active_route:
                    # Route-aware: only show if ahead on route
                    if route_aware_status != "ahead_on_route":
                        continue
                else:
                    # Angle-based: use course_status as before
                    if course_status not in status_filter_set:
                        continue

            # Apply category filter if specified
            # Include POIs with null category (manually created) always
            if category_filter and poi.category:
                if poi.category not in category_filter:
                    continue

            # Calculate active status for this POI
            active_status = calculate_poi_active_status(
                poi=poi,
                route_manager=route_manager,
            )

            # If filtering is active, skip inactive POIs before creating the response object
            if active_only and not active_status:
                continue

            pois_with_eta.append(
                POIWithETA(
                    poi_id=poi.id,
                    name=poi.name,
                    latitude=poi.latitude,
                    longitude=poi.longitude,
                    category=poi.category,
                    icon=poi.icon,
                    active=active_status,
                    eta_seconds=eta_seconds,
                    eta_type=eta_type,
                    is_pre_departure=is_pre_departure,
                    flight_phase=flight_phase_value,
                    distance_meters=distance,
                    bearing_degrees=bearing,
                    course_status=course_status,
                    is_on_active_route=is_on_active_route,
                    projected_latitude=poi.projected_latitude,
                    projected_longitude=poi.projected_longitude,
                    projected_waypoint_index=projected_waypoint_index,
                    projected_route_progress=projected_route_progress,
                    route_aware_status=route_aware_status,
                )
            )

        # Sort by ETA (ascending) so closest POIs appear first
        pois_with_eta.sort(
            key=lambda p: p.eta_seconds if p.eta_seconds >= 0 else float("inf")
        )

        return POIETAListResponse(pois=pois_with_eta, total=len(pois_with_eta))

    except Exception as calculation_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to calculate ETA: {str(calculation_error)}",
        )
