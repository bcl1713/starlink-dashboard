"""Routes API endpoints for KML route management."""

import asyncio
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.core.logging import get_logger
from app.models.poi import POICreate
from app.models.route import (
    ParsedRoute,
    RouteDetailResponse,
    RouteListResponse,
    RouteResponse,
    RouteStatsResponse,
    RouteWaypoint,
)
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from app.services.route_eta_calculator import (
    RouteETACalculator,
    get_eta_cache_stats,
    get_eta_accuracy_stats,
    clear_eta_cache,
    cleanup_eta_cache,
)
from app.services.kml_parser import parse_kml_file, KMLParseError

logger = get_logger(__name__)

# Global route manager instance (set by main.py)
_route_manager: Optional[RouteManager] = None
_poi_manager: Optional[POIManager] = None

# Create API router
router = APIRouter(prefix="/api/routes", tags=["routes"])


def set_route_manager(route_manager: RouteManager) -> None:
    """Set the route manager instance (called by main.py during startup)."""
    global _route_manager
    _route_manager = route_manager


def set_poi_manager(poi_manager: POIManager) -> None:
    """Set the POI manager instance (called by main.py during startup)."""
    global _poi_manager
    _poi_manager = poi_manager


def _resolve_waypoint_metadata(
    waypoint: RouteWaypoint, fallback_index: int
) -> tuple[str, str, str, Optional[str]]:
    """
    Map a RouteWaypoint role to POI category/icon and derive a safe name/description.

    Args:
        waypoint: Source waypoint data
        fallback_index: Index used to build fallback name if missing

    Returns:
        Tuple of (name, category, icon, description)
    """
    role = (waypoint.role or "").lower()

    category = "waypoint"
    icon = "waypoint"

    if role == "departure":
        category = "departure"
        icon = "airport"
    elif role == "arrival":
        category = "arrival"
        icon = "flag"
    elif role == "alternate":
        category = "alternate"
        icon = "star"

    raw_name = (waypoint.name or "").strip()
    if raw_name:
        name = raw_name
    else:
        name = f"Waypoint {fallback_index}"

    description_parts: list[str] = []

    if waypoint.description:
        waypoint_desc = waypoint.description.strip()
        if waypoint_desc:
            description_parts.append(waypoint_desc)

    if role:
        description_parts.append(f"Role: {role}")

    description = " | ".join(description_parts) if description_parts else None

    return name, category, icon, description


def _import_waypoints_as_pois(route_id: str, parsed_route: ParsedRoute) -> tuple[int, int]:
    """
    Create POIs for the supplied route using its waypoint metadata.

    Args:
        route_id: Route identifier (filename stem)
        parsed_route: ParsedRoute instance containing waypoint data

    Returns:
        Tuple of (created_count, skipped_count)
    """
    if not parsed_route.waypoints:
        return 0, 0

    created = 0
    skipped = 0

    # Remove any previously imported POIs for this route to avoid duplicates
    try:
        removed = _poi_manager.delete_route_pois(route_id)
        if removed:
            logger.info(f"Removed {removed} existing POIs prior to re-import for route {route_id}")
    except Exception as exc:
        logger.error(f"Failed to delete existing POIs for route {route_id}: {exc}")

    for idx, waypoint in enumerate(parsed_route.waypoints, start=1):
        try:
            latitude = waypoint.latitude
            longitude = waypoint.longitude

            if latitude is None or longitude is None:
                skipped += 1
                continue

            name, category, icon, description = _resolve_waypoint_metadata(waypoint, idx)

            route_note = f"Imported from route {parsed_route.metadata.name}" if parsed_route.metadata.name else "Imported from uploaded KML"
            if description:
                description = f"{description} | {route_note}"
            else:
                description = route_note

            poi = POICreate(
                name=name,
                latitude=latitude,
                longitude=longitude,
                icon=icon,
                category=category,
                description=description,
                route_id=route_id,
            )
            _poi_manager.create_poi(poi)
            created += 1
        except Exception as exc:
            logger.error(f"Failed to create POI for waypoint {waypoint.name or idx} on route {route_id}: {exc}")
            skipped += 1

    return created, skipped


@router.get("", response_model=RouteListResponse, summary="List all routes")
async def list_routes(
    active: Optional[bool] = Query(None, description="Filter by active status"),
) -> RouteListResponse:
    """
    List all available KML routes.

    Query Parameters:
    - active: Filter by active status (true/false, or omit for all)

    Returns:
    - List of routes with metadata including `flight_phase`, `eta_mode`, `has_timing_data`, and active route context

    Example:
        ```bash
        curl http://localhost:8000/api/routes | jq '.routes[0]'
        ```
    """
    if not _route_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route manager not initialized",
        )

    routes_dict = _route_manager.list_routes()
    active_route_id = _route_manager._active_route_id

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

        from datetime import datetime
        imported_at = datetime.fromisoformat(route_info["imported_at"])

        # Get parsed route to check for timing data
        parsed_route = _route_manager.get_route(route_id)
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


@router.get("/{route_id}", response_model=RouteDetailResponse, summary="Get route details")
async def get_route_detail(route_id: str) -> RouteDetailResponse:
    """
    Get detailed information about a specific route.

    Path Parameters:
    - route_id: Route identifier (filename without .kml extension)

    Returns:
    - Full route details including points, statistics, timing profile, and live flight-state metadata (`flight_phase`, `eta_mode`, countdown fields)

    Example:
        ```bash
        curl http://localhost:8000/api/routes/{route_id} | jq '{name: .name, flight_phase: .flight_phase, eta_mode: .eta_mode}'
        ```
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
    poi_count = _poi_manager.count_pois(route_id=route_id)

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


@router.post("/{route_id}/activate", response_model=RouteResponse, summary="Activate a route")
async def activate_route(route_id: str) -> RouteResponse:
    """
    Activate a route for tracking and visualization.

    Path Parameters:
    - route_id: Route identifier

    Returns:
    - Updated route information including live `flight_phase`, `eta_mode`, and timing profile context

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/routes/{route_id}/activate | jq '.eta_mode'
        ```
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

    # Calculate POI projections for the newly activated route
    if _poi_manager:
        try:
            projected_count = _poi_manager.calculate_poi_projections(parsed_route)
            logger.info(f"Calculated projections for {projected_count} POIs on route activation")
            # Reload POIs to ensure in-memory cache has the projection data
            _poi_manager.reload_pois()
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

    # Clear POI projections on route deactivation
    if _poi_manager:
        try:
            cleared_count = _poi_manager.clear_poi_projections()
            logger.info(f"Cleared projections for {cleared_count} POIs on route deactivation")
        except Exception as e:
            logger.error(f"Failed to clear POI projections: {e}")

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
async def upload_route(
    import_pois: bool = Query(
        default=True,
        description="Import POIs from waypoint placemarks in the uploaded KML",
    ),
    file: UploadFile = File(...),
) -> RouteResponse:
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
        # Ensure we write uploads to the active RouteManager directory
        routes_dir = Path(getattr(_route_manager, "routes_dir", "/data/routes"))
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

        # Get parsed route
        route_id = file_path.stem

        # Explicitly load the route file (watchdog may not pick it up in tests)
        try:
            _route_manager._load_route_file(file_path)
        except Exception as e:
            logger.error(f"Error loading route file {file_path}: {str(e)}")

        parsed_route = _route_manager.get_route(route_id)

        if not parsed_route:
            # Fallback: parse synchronously to avoid race conditions with filesystem events
            try:
                parsed_route = parse_kml_file(file_path)
                if parsed_route:
                    _route_manager.add_route(route_id, parsed_route)
            except KMLParseError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to parse KML file: {file.filename} ({exc})",
                ) from exc

        if not parsed_route:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse KML file: {file.filename}",
            )

        created_pois = skipped_pois = None

        if import_pois:
            created_pois, skipped_pois = _import_waypoints_as_pois(route_id, parsed_route)
            logger.info(
                "Imported %d POIs (skipped %d) from KML placemarks for route %s",
                created_pois,
                skipped_pois,
                route_id,
            )

        has_timing_data = False
        if parsed_route.timing_profile:
            has_timing_data = parsed_route.timing_profile.has_timing_data
            flight_phase = parsed_route.timing_profile.flight_status
        else:
            flight_phase = None

        return RouteResponse(
            id=route_id,
            name=parsed_route.metadata.name,
            description=parsed_route.metadata.description,
            point_count=parsed_route.metadata.point_count,
            is_active=False,
            imported_at=parsed_route.metadata.imported_at,
            imported_poi_count=created_pois,
            skipped_poi_count=skipped_pois,
            has_timing_data=has_timing_data,
            timing_profile=parsed_route.timing_profile,
            flight_phase=flight_phase,
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


@router.get("/{route_id}/eta/waypoint/{waypoint_index}", summary="Calculate ETA to waypoint")
async def calculate_eta_to_waypoint(
    route_id: str,
    waypoint_index: int,
    current_position_lat: float = Query(..., description="Current latitude in decimal degrees"),
    current_position_lon: float = Query(..., description="Current longitude in decimal degrees"),
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

    if waypoint_index >= len(parsed_route.waypoints):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Waypoint index {waypoint_index} out of range (route has {len(parsed_route.waypoints)} waypoints)",
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
    current_position_lat: float = Query(..., description="Current latitude in decimal degrees"),
    current_position_lon: float = Query(..., description="Current longitude in decimal degrees"),
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
    current_position_lat: float = Query(..., description="Current latitude in decimal degrees"),
    current_position_lon: float = Query(..., description="Current longitude in decimal degrees"),
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


@router.get("/active/timing")
async def get_active_route_timing() -> dict:
    """
    Get timing profile data for the currently active route.

    Returns:
    - Dictionary with timing profile information (departure_time, arrival_time, total_duration, etc.)
    - Empty dict if no route is active or route lacks timing data
    """
    if not _route_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route manager not initialized",
        )

    active_route = _route_manager.get_active_route()
    if not active_route:
        return {
            "has_timing_data": False,
            "message": "No active route"
        }

    if not active_route.timing_profile:
        return {
            "has_timing_data": False,
            "message": "Active route has no timing data"
        }

    timing = active_route.timing_profile
    flight_status = timing.flight_status
    is_departed = timing.is_departed()
    is_in_flight = timing.is_in_flight()

    return {
        "route_name": active_route.metadata.name or "Unknown",
        "has_timing_data": timing.has_timing_data,
        "departure_time": timing.departure_time.isoformat() if timing.departure_time else None,
        "arrival_time": timing.arrival_time.isoformat() if timing.arrival_time else None,
        "actual_departure_time": timing.actual_departure_time.isoformat() if timing.actual_departure_time else None,
        "actual_arrival_time": timing.actual_arrival_time.isoformat() if timing.actual_arrival_time else None,
        "flight_status": flight_status,
        "is_departed": is_departed,
        "is_in_flight": is_in_flight,
        "total_expected_duration_seconds": timing.total_expected_duration_seconds,
        "segment_count_with_timing": timing.segment_count_with_timing,
        "total_duration_readable": _format_duration(timing.total_expected_duration_seconds) if timing.total_expected_duration_seconds else None
    }


def _format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable format."""
    if not seconds or seconds < 0:
        return "Unknown"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


@router.get("/metrics/eta-cache", summary="Get ETA cache statistics")
async def get_eta_cache_metrics() -> dict:
    """
    Get statistics about ETA calculation caching performance.

    Returns:
    - Dictionary with cache size, TTL, and timestamp
    """
    return get_eta_cache_stats()


@router.get("/metrics/eta-accuracy", summary="Get ETA accuracy statistics")
async def get_eta_accuracy_metrics() -> dict:
    """
    Get ETA accuracy statistics from historical tracking.

    Returns:
    - Dictionary with average error, max error, completion percentage
    """
    return get_eta_accuracy_stats()


@router.post("/cache/cleanup", summary="Clean up expired cache entries")
async def cleanup_eta_cache_endpoint() -> dict:
    """
    Remove expired entries from the ETA cache.

    Returns:
    - Dictionary with number of entries removed
    """
    removed = cleanup_eta_cache()
    return {
        "status": "success",
        "entries_removed": removed,
        "message": f"Cleaned up {removed} expired cache entries"
    }


@router.post("/cache/clear", summary="Clear all ETA cache")
async def clear_eta_cache_endpoint() -> dict:
    """
    Clear all cached ETA calculations (use with caution).

    Returns:
    - Dictionary with status
    """
    clear_eta_cache()
    return {
        "status": "success",
        "message": "ETA cache cleared"
    }


@router.get("/live-mode/active-route-eta", summary="Get active route ETA for live mode")
async def get_live_mode_active_route_eta(
    current_position_lat: float = Query(..., description="Current latitude"),
    current_position_lon: float = Query(..., description="Current longitude"),
    current_speed_knots: float = Query(default=500.0, description="Current speed in knots"),
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
    if not _route_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route manager not initialized",
        )

    parsed_route = _route_manager.get_active_route()
    if not parsed_route:
        return {
            "has_active_route": False,
            "message": "No active route"
        }

    try:
        calculator = RouteETACalculator(parsed_route)

        # Get progress metrics
        progress = calculator.get_route_progress(current_position_lat, current_position_lon)

        # Get timing profile
        timing_info = {}
        if parsed_route.timing_profile:
            timing_info = {
                "has_timing_data": parsed_route.timing_profile.has_timing_data,
                "departure_time": (
                    parsed_route.timing_profile.departure_time.isoformat()
                    if parsed_route.timing_profile.departure_time else None
                ),
                "arrival_time": (
                    parsed_route.timing_profile.arrival_time.isoformat()
                    if parsed_route.timing_profile.arrival_time else None
                ),
                "total_duration_seconds": parsed_route.timing_profile.total_expected_duration_seconds,
            }

        # Find next waypoint and calculate ETA
        nearest_idx, _ = calculator.find_nearest_point(current_position_lat, current_position_lon)
        next_waypoint_idx = nearest_idx + 1 if nearest_idx < len(parsed_route.waypoints) - 1 else nearest_idx

        next_eta = None
        if next_waypoint_idx < len(parsed_route.waypoints):
            next_wp = parsed_route.waypoints[next_waypoint_idx]
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
