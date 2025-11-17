"""POI CRUD API endpoints for managing points of interest."""

import logging
import math
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.models.poi import (
    POI,
    POICreate,
    POIETAListResponse,
    POIListResponse,
    POIResponse,
    POIUpdate,
    POIWithETA,
)
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from app.mission.routes import get_active_mission_id
from app.mission.storage import load_mission, MissionStorage

logger = logging.getLogger(__name__)

# Global coordinator reference for accessing telemetry
_coordinator: Optional[object] = None

# Global POI manager instance (set by main.py)
poi_manager: Optional[POIManager] = None
# Global route manager (optional; set when available)
_route_manager: Optional[RouteManager] = None


def set_coordinator(coordinator):
    """Set the simulation coordinator reference."""
    global _coordinator
    _coordinator = coordinator


def set_poi_manager(manager: POIManager) -> None:
    """Set the POI manager instance (called by main.py during startup)."""
    global poi_manager
    poi_manager = manager


def set_route_manager(route_manager: RouteManager) -> None:
    """Set the RouteManager instance for route-aware ETA calculations."""
    global _route_manager
    _route_manager = route_manager

# Create API router
router = APIRouter(prefix="/api/pois", tags=["pois"])


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate bearing from point 1 to point 2 in degrees (0=North, 90=East).

    Args:
        lat1: Starting latitude in decimal degrees
        lon1: Starting longitude in decimal degrees
        lat2: Ending latitude in decimal degrees
        lon2: Ending longitude in decimal degrees

    Returns:
        Bearing in degrees (0-360)
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)

    x = math.sin(dlon) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(
        lat2_rad
    ) * math.cos(dlon)

    bearing_rad = math.atan2(x, y)
    bearing_deg = math.degrees(bearing_rad)

    # Normalize to 0-360 range
    return (bearing_deg + 360) % 360


def calculate_course_status(heading: float, bearing: float) -> str:
    """
    Determine course status relative to vessel heading.

    Calculates the shortest angular difference between current heading
    and bearing to POI, then categorizes as one of four statuses.

    Args:
        heading: Current vessel heading in degrees (0=North)
        bearing: Bearing to POI in degrees (0=North)

    Returns:
        Course status string: 'on_course', 'slightly_off', 'off_track', or 'behind'
    """
    # Calculate shortest angular difference
    course_diff = abs(heading - bearing)
    if course_diff > 180:
        course_diff = 360 - course_diff

    # Categorize based on angle thresholds
    if course_diff < 10:
        return "on_course"
    elif course_diff < 45:
        return "slightly_off"
    elif course_diff < 65:
        return "off_track"
    else:
        return "behind"


def _calculate_poi_active_status(
    poi: POI,
    route_manager: RouteManager,
    mission_storage: MissionStorage,
) -> bool:
    """
    Calculate whether a POI is currently active based on its associated
    route or mission.

    Logic:
    - Global POIs (no route_id/mission_id): always active
    - Route POIs: active if their route is the active route
    - Mission POIs: active if their mission has is_active=true

    Args:
        poi: The POI to check
        route_manager: RouteManager instance to check active route
        mission_storage: Mission storage instance to check mission status

    Returns:
        bool: True if POI is active, False otherwise
    """
    # Global POIs are always active
    if poi.route_id is None and poi.mission_id is None:
        return True

    # Check route-based POIs
    if poi.route_id is not None:
        active_route = route_manager.get_active_route()
        return active_route is not None and active_route.id == poi.route_id

    # Check mission-based POIs
    if poi.mission_id is not None:
        try:
            mission = mission_storage.load_mission(poi.mission_id)
            return mission.is_active if mission else False
        except Exception:
            # Mission not found or error loading
            return False

    return False


@router.get("", response_model=POIListResponse, summary="List all POIs")
async def list_pois(
    route_id: Optional[str] = Query(None, description="Filter by route ID"),
    mission_id: Optional[str] = Query(None, description="Filter by mission ID"),
) -> POIListResponse:
    """
    Get list of all POIs, optionally filtered by route.

    Query Parameters:
    - route_id: Optional route ID to filter POIs
    - mission_id: Optional mission ID to filter POIs

    Returns:
    - List of POI objects and total count
    """
    if mission_id:
        # If a specific mission is requested, filter by it.
        pois = poi_manager.list_pois(route_id=route_id, mission_id=mission_id)
    elif route_id:
        # If only a route is requested, get all its POIs and then filter mission events.
        all_route_pois = poi_manager.list_pois(route_id=route_id)
        mission_event_pois = [
            poi for poi in all_route_pois if poi.category == "mission-event" and poi.mission_id
        ]

        if mission_event_pois:
            latest_mission_poi = max(
                mission_event_pois,
                key=lambda poi: poi.updated_at or poi.created_at,
            )
            latest_mission_id = latest_mission_poi.mission_id

            # Keep non-mission events, and mission events from the latest mission
            pois = [
                p for p in all_route_pois
                if p.category != "mission-event"
                or not p.mission_id
                or p.mission_id == latest_mission_id
            ]
        else:
            pois = all_route_pois
    else:
        # No route or mission specified, get all POIs.
        pois = poi_manager.list_pois()
    responses = [
        POIResponse(
            id=poi.id,
            name=poi.name,
            latitude=poi.latitude,
            longitude=poi.longitude,
            icon=poi.icon,
            category=poi.category,
            description=poi.description,
            route_id=poi.route_id,
            mission_id=poi.mission_id,
            created_at=poi.created_at,
            updated_at=poi.updated_at,
            projected_latitude=poi.projected_latitude,
            projected_longitude=poi.projected_longitude,
            projected_waypoint_index=poi.projected_waypoint_index,
            projected_route_progress=poi.projected_route_progress,
        )
        for poi in pois
    ]

    return POIListResponse(pois=responses, total=len(responses), route_id=route_id, mission_id=mission_id)


@router.get("/etas", response_model=POIETAListResponse, summary="Get all POIs with real-time ETA data")
async def get_pois_with_etas(
    route_id: Optional[str] = Query(None, description="Filter by route ID"),
    latitude: Optional[str] = Query(None, description="Current latitude (decimal degrees)"),
    longitude: Optional[str] = Query(None, description="Current longitude (decimal degrees)"),
    speed_knots: Optional[str] = Query(None, description="Current speed in knots"),
    status_filter: Optional[str] = Query(None, description="Filter by course status (comma-separated: on_course,slightly_off,off_track,behind)"),
    category: Optional[str] = Query(None, description="Filter by POI category (comma-separated: departure,arrival,waypoint,alternate)"),
) -> POIETAListResponse:
    """
    Get all POIs with real-time ETA and distance data.

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
                if hasattr(_coordinator, 'route_manager'):
                    active_route = _coordinator.route_manager.get_active_route()
                    # Get progress from position simulator if available
                    if hasattr(_coordinator, 'position_sim') and _coordinator.position_sim:
                        current_route_progress = _coordinator.position_sim.progress * 100.0 if _coordinator.position_sim.progress else None
            except Exception as e:
                # Fall back to query parameters if coordinator fails
                latitude = None
                longitude = None
                speed_knots = None

        # If coordinator doesn't have route manager or is unavailable, try _route_manager directly
        if not active_route and _route_manager:
            active_route = _route_manager.get_active_route()

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
            status_filter_set = set(s.strip() for s in status_filter.split(",") if s.strip())

        # Parse category filter if provided
        category_filter = set()
        if category:
            category_filter = set(c.strip() for c in category.split(",") if c.strip())

        pois = poi_manager.list_pois(route_id=route_id)

        # Calculate ETA and distance for each POI
        from app.core.eta_service import get_eta_calculator
        from app.services.flight_state_manager import get_flight_state_manager
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
        route_projection_distance_threshold_m = 20000.0  # Treat POIs beyond 20km as off-route

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
                    eta_seconds = eta_calc.calculate_eta(distance, eta_calc.default_speed_knots)

            # Calculate bearing
            bearing = calculate_bearing(latitude, longitude, poi.latitude, poi.longitude)

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
                and (
                    projected_distance_to_route is None
                    or close_to_route
                )
            )

            if active_route and poi.projected_route_progress is not None:
                projected_waypoint_index = poi.projected_waypoint_index
                projected_route_progress = poi.projected_route_progress

                if is_on_active_route:
                    if current_route_progress is not None:
                        if projected_route_progress >= (current_route_progress - progress_epsilon):
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
                eta_seconds = eta_calc.calculate_eta(distance, eta_calc.default_speed_knots)

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

            pois_with_eta.append(
                POIWithETA(
                    poi_id=poi.id,
                    name=poi.name,
                    latitude=poi.latitude,
                    longitude=poi.longitude,
                    category=poi.category,
                    icon=poi.icon,
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
        pois_with_eta.sort(key=lambda p: p.eta_seconds if p.eta_seconds >= 0 else float('inf'))

        return POIETAListResponse(pois=pois_with_eta, total=len(pois_with_eta))

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to calculate ETA: {str(e)}",
        )


@router.get("/count/total", response_model=dict, summary="Get POI count")
async def count_pois(route_id: Optional[str] = Query(None, description="Filter by route ID")) -> dict:
    """
    Get count of POIs, optionally filtered by route.

    Query Parameters:
    - route_id: Optional route ID to filter by

    Returns:
    - JSON object with count
    """
    count = poi_manager.count_pois(route_id=route_id)
    return {"count": count, "route_id": route_id}


@router.get("/stats/next-destination", response_model=dict, summary="Get next destination (closest POI name)")
async def get_next_destination(
    latitude: Optional[str] = Query(None),
    longitude: Optional[str] = Query(None),
    speed_knots: Optional[str] = Query(None),
) -> dict:
    """
    Get the name of the closest POI (next destination).

    Uses coordinator telemetry if available, otherwise uses query parameters or fallback values.

    Query Parameters:
    - latitude: Current latitude (optional, uses coordinator if available)
    - longitude: Current longitude (optional, uses coordinator if available)
    - speed_knots: Current speed in knots (optional, uses coordinator if available)

    Returns:
    - JSON object with 'name' field containing the closest POI name
    """
    try:
        # Get current position from coordinator if available
        if _coordinator:
            try:
                telemetry = _coordinator.get_current_telemetry()
                lat = telemetry.position.latitude
                lon = telemetry.position.longitude
                speed = telemetry.position.speed
            except Exception:
                # Fall back to query parameters or defaults
                lat = float(latitude) if latitude else 41.6
                lon = float(longitude) if longitude else -74.0
                speed = float(speed_knots) if speed_knots else 67.0
        else:
            # Use fallback coordinates when no coordinator available
            lat = float(latitude) if latitude else 41.6
            lon = float(longitude) if longitude else -74.0
            speed = float(speed_knots) if speed_knots else 67.0
    except (ValueError, TypeError):
        lat, lon, speed = 41.6, -74.0, 67.0

    pois = poi_manager.list_pois()
    if not pois:
        status_eta_mode = "estimated"
        status_phase = None
        try:
            from app.services.flight_state_manager import get_flight_state_manager

            snapshot = get_flight_state_manager().get_status()
            status_eta_mode = snapshot.eta_mode.value
            status_phase = snapshot.phase.value
        except Exception:  # pragma: no cover - defensive guard
            pass
        return {
            "name": "No POIs available",
            "eta_type": status_eta_mode,
            "flight_phase": status_phase,
            "eta_seconds": -1,
        }

    from app.core.eta_service import get_eta_calculator
    eta_calc = get_eta_calculator()

    closest = None
    closest_eta = float('inf')

    for poi in pois:
        distance = eta_calc.calculate_distance(lat, lon, poi.latitude, poi.longitude)
        eta_seconds = eta_calc.calculate_eta(distance, speed)
        if eta_seconds < closest_eta:
            closest_eta = eta_seconds
            closest = poi
    status_eta_mode = "estimated"
    status_phase = None
    try:
        from app.services.flight_state_manager import get_flight_state_manager

        snapshot = get_flight_state_manager().get_status()
        status_eta_mode = snapshot.eta_mode.value
        status_phase = snapshot.phase.value
    except Exception:  # pragma: no cover - defensive guard
        pass

    eta_value = max(0, closest_eta) if closest_eta != float('inf') else -1
    return {
        "name": closest.name if closest else "No POIs available",
        "eta_type": status_eta_mode,
        "flight_phase": status_phase,
        "eta_seconds": eta_value,
    }


@router.get("/stats/next-eta", response_model=dict, summary="Get time to next arrival (closest POI ETA)")
async def get_next_eta(
    latitude: Optional[str] = Query(None),
    longitude: Optional[str] = Query(None),
    speed_knots: Optional[str] = Query(None),
) -> dict:
    """
    Get the ETA in seconds to the closest POI.

    Uses coordinator telemetry if available, otherwise uses query parameters or fallback values.

    Query Parameters:
    - latitude: Current latitude (optional, uses coordinator if available)
    - longitude: Current longitude (optional, uses coordinator if available)
    - speed_knots: Current speed in knots (optional, uses coordinator if available)

    Returns:
    - JSON object with:
      - `name`: Closest POI name (or fallback message)
      - `eta_seconds`: ETA in seconds (or -1 if unavailable)
      - `eta_type`: Current ETA mode (`anticipated` / `estimated`)
      - `flight_phase`: Current flight phase (may be null if unavailable)
    """
    try:
        # Get current position from coordinator if available
        if _coordinator:
            try:
                telemetry = _coordinator.get_current_telemetry()
                lat = telemetry.position.latitude
                lon = telemetry.position.longitude
                speed = telemetry.position.speed
            except Exception:
                # Fall back to query parameters or defaults
                lat = float(latitude) if latitude else 41.6
                lon = float(longitude) if longitude else -74.0
                speed = float(speed_knots) if speed_knots else 67.0
        else:
            # Use fallback coordinates when no coordinator available
            lat = float(latitude) if latitude else 41.6
            lon = float(longitude) if longitude else -74.0
            speed = float(speed_knots) if speed_knots else 67.0
    except (ValueError, TypeError):
        lat, lon, speed = 41.6, -74.0, 67.0

    pois = poi_manager.list_pois()
    if not pois:
        status_eta_mode = "estimated"
        status_phase = None
        try:
            from app.services.flight_state_manager import get_flight_state_manager

            snapshot = get_flight_state_manager().get_status()
            status_eta_mode = snapshot.eta_mode.value
            status_phase = snapshot.phase.value
        except Exception:  # pragma: no cover - defensive guard
            pass
        return {
            "eta_seconds": -1,
            "eta_type": status_eta_mode,
            "flight_phase": status_phase,
        }

    from app.core.eta_service import get_eta_calculator
    eta_calc = get_eta_calculator()

    closest_eta = float('inf')

    for poi in pois:
        distance = eta_calc.calculate_distance(lat, lon, poi.latitude, poi.longitude)
        eta_seconds = eta_calc.calculate_eta(distance, speed)
        if eta_seconds < closest_eta:
            closest_eta = eta_seconds

    status_eta_mode = "estimated"
    status_phase = None
    try:
        from app.services.flight_state_manager import get_flight_state_manager

        snapshot = get_flight_state_manager().get_status()
        status_eta_mode = snapshot.eta_mode.value
        status_phase = snapshot.phase.value
    except Exception:  # pragma: no cover - defensive guard
        pass

    return {
        "eta_seconds": max(0, closest_eta) if closest_eta != float('inf') else -1,
        "eta_type": status_eta_mode,
        "flight_phase": status_phase,
    }


@router.get("/stats/approaching", response_model=dict, summary="Get count of approaching POIs (< 30 min)")
async def get_approaching_pois(
    latitude: Optional[str] = Query(None),
    longitude: Optional[str] = Query(None),
    speed_knots: Optional[str] = Query(None),
) -> dict:
    """
    Get count of POIs that will be reached within 30 minutes.

    Uses coordinator telemetry if available, otherwise uses query parameters or fallback values.

    Query Parameters:
    - latitude: Current latitude (optional, uses coordinator if available)
    - longitude: Current longitude (optional, uses coordinator if available)
    - speed_knots: Current speed in knots (optional, uses coordinator if available)

    Returns:
    - JSON object with 'count' field containing number of approaching POIs
    """
    try:
        # Get current position from coordinator if available
        if _coordinator:
            try:
                telemetry = _coordinator.get_current_telemetry()
                lat = telemetry.position.latitude
                lon = telemetry.position.longitude
                speed = telemetry.position.speed
            except Exception:
                # Fall back to query parameters or defaults
                lat = float(latitude) if latitude else 41.6
                lon = float(longitude) if longitude else -74.0
                speed = float(speed_knots) if speed_knots else 67.0
        else:
            # Use fallback coordinates when no coordinator available
            lat = float(latitude) if latitude else 41.6
            lon = float(longitude) if longitude else -74.0
            speed = float(speed_knots) if speed_knots else 67.0
    except (ValueError, TypeError):
        lat, lon, speed = 41.6, -74.0, 67.0

    pois = poi_manager.list_pois()
    if not pois:
        return {"count": 0}

    from app.core.eta_service import get_eta_calculator
    eta_calc = get_eta_calculator()

    approaching_count = 0
    threshold_seconds = 1800  # 30 minutes

    for poi in pois:
        distance = eta_calc.calculate_distance(lat, lon, poi.latitude, poi.longitude)
        eta_seconds = eta_calc.calculate_eta(distance, speed)
        if 0 <= eta_seconds < threshold_seconds:
            approaching_count += 1

    return {"count": approaching_count}


@router.get("/{poi_id}", response_model=POIResponse, summary="Get a specific POI")
async def get_poi(poi_id: str) -> POIResponse:
    """
    Get a specific POI by ID.

    Path Parameters:
    - poi_id: POI identifier

    Returns:
    - POI object

    Raises:
    - 404: POI not found
    """
    poi = poi_manager.get_poi(poi_id)
    if not poi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"POI not found: {poi_id}",
        )

    return POIResponse(
        id=poi.id,
        name=poi.name,
        latitude=poi.latitude,
        longitude=poi.longitude,
        icon=poi.icon,
        category=poi.category,
        description=poi.description,
        route_id=poi.route_id,
        mission_id=poi.mission_id,
        created_at=poi.created_at,
        updated_at=poi.updated_at,
        projected_latitude=poi.projected_latitude,
        projected_longitude=poi.projected_longitude,
        projected_waypoint_index=poi.projected_waypoint_index,
        projected_route_progress=poi.projected_route_progress,
    )


@router.post("", response_model=POIResponse, status_code=status.HTTP_201_CREATED, summary="Create a new POI")
async def create_poi(poi_create: POICreate) -> POIResponse:
    """
    Create a new POI.

    Request Body:
    - name: POI name (required)
    - latitude: Latitude coordinate (required)
    - longitude: Longitude coordinate (required)
    - icon: Icon identifier (optional, default: "marker")
    - category: POI category (optional)
    - description: POI description (optional)
    - route_id: Associated route ID (optional)
    - mission_id: Associated mission ID (optional)

    Returns:
    - Created POI object with ID and timestamps

    Raises:
    - 400: Invalid input data
    """
    try:
        # Get active route for POI projection
        active_route = None
        if _coordinator and hasattr(_coordinator, 'route_manager'):
            try:
                active_route = _coordinator.route_manager.get_active_route()
            except Exception:
                pass

        poi = poi_manager.create_poi(poi_create, active_route=active_route)

        return POIResponse(
            id=poi.id,
            name=poi.name,
            latitude=poi.latitude,
            longitude=poi.longitude,
            icon=poi.icon,
            category=poi.category,
            description=poi.description,
            route_id=poi.route_id,
            mission_id=poi.mission_id,
            created_at=poi.created_at,
            updated_at=poi.updated_at,
            projected_latitude=poi.projected_latitude,
            projected_longitude=poi.projected_longitude,
            projected_waypoint_index=poi.projected_waypoint_index,
            projected_route_progress=poi.projected_route_progress,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create POI: {str(e)}",
        )


@router.put("/{poi_id}", response_model=POIResponse, summary="Update a POI")
async def update_poi(poi_id: str, poi_update: POIUpdate) -> POIResponse:
    """
    Update an existing POI.

    Path Parameters:
    - poi_id: POI identifier

    Request Body (all fields optional):
    - name: POI name
    - latitude: Latitude coordinate
    - longitude: Longitude coordinate
    - icon: Icon identifier
    - category: POI category
    - description: POI description

    Returns:
    - Updated POI object

    Raises:
    - 404: POI not found
    - 400: Invalid update data
    """
    try:
        poi = poi_manager.update_poi(poi_id, poi_update)
        if not poi:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"POI not found: {poi_id}",
            )

        return POIResponse(
            id=poi.id,
            name=poi.name,
            latitude=poi.latitude,
            longitude=poi.longitude,
            icon=poi.icon,
            category=poi.category,
            description=poi.description,
            route_id=poi.route_id,
            mission_id=poi.mission_id,
            created_at=poi.created_at,
            updated_at=poi.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update POI: {str(e)}",
        )


@router.delete("/{poi_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a POI")
async def delete_poi(poi_id: str) -> None:
    """
    Delete a POI.

    Path Parameters:
    - poi_id: POI identifier

    Raises:
    - 404: POI not found
    """
    success = poi_manager.delete_poi(poi_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"POI not found: {poi_id}",
        )
