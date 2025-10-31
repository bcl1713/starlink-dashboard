"""POI CRUD API endpoints for managing points of interest."""

import math
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.models.poi import (
    POICreate,
    POIETAListResponse,
    POIListResponse,
    POIResponse,
    POIUpdate,
    POIWithETA,
)
from app.services.poi_manager import POIManager

# Global coordinator reference for accessing telemetry
_coordinator: Optional[object] = None


def set_coordinator(coordinator):
    """Set the simulation coordinator reference."""
    global _coordinator
    _coordinator = coordinator

# Initialize POI manager
poi_manager = POIManager()

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
    if course_diff < 15:
        return "on_course"
    elif course_diff < 45:
        return "slightly_off"
    elif course_diff < 90:
        return "off_track"
    else:
        return "behind"


@router.get("", response_model=POIListResponse, summary="List all POIs")
async def list_pois(route_id: Optional[str] = Query(None, description="Filter by route ID")) -> POIListResponse:
    """
    Get list of all POIs, optionally filtered by route.

    Query Parameters:
    - route_id: Optional route ID to filter POIs

    Returns:
    - List of POI objects and total count
    """
    pois = poi_manager.list_pois(route_id=route_id)
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
            created_at=poi.created_at,
            updated_at=poi.updated_at,
        )
        for poi in pois
    ]

    return POIListResponse(pois=responses, total=len(responses), route_id=route_id)


@router.get("/etas", response_model=POIETAListResponse, summary="Get all POIs with real-time ETA data")
async def get_pois_with_etas(
    route_id: Optional[str] = Query(None, description="Filter by route ID"),
    latitude: Optional[str] = Query(None, description="Current latitude (decimal degrees)"),
    longitude: Optional[str] = Query(None, description="Current longitude (decimal degrees)"),
    speed_knots: Optional[str] = Query(None, description="Current speed in knots"),
    status: Optional[str] = Query(None, description="Filter by course status (comma-separated: on_course,slightly_off,off_track,behind)"),
) -> POIETAListResponse:
    """
    Get all POIs with real-time ETA and distance data.

    This endpoint calculates ETA and distance for all POIs based on current position and speed.
    Uses coordinator telemetry if available, otherwise uses query parameters or fallback values.

    Query Parameters:
    - route_id: Optional route ID to filter by
    - latitude: Current latitude (optional, uses coordinator if available)
    - longitude: Current longitude (optional, uses coordinator if available)
    - speed_knots: Current speed in knots (optional, uses coordinator if available)
    - status: Optional course status filter (comma-separated list of: on_course, slightly_off, off_track, behind)

    Returns:
    - JSON object with list of POIs with ETA data and timestamp

    Raises:
    - 400: Failed to calculate ETA
    """
    try:
        # Get current position from coordinator if available
        heading = 0.0  # Default heading
        if _coordinator:
            try:
                telemetry = _coordinator.get_current_telemetry()
                latitude = telemetry.position.latitude
                longitude = telemetry.position.longitude
                speed_knots = telemetry.position.speed
                heading = telemetry.position.heading
            except Exception as e:
                # Fall back to query parameters if coordinator fails
                latitude = None
                longitude = None
                speed_knots = None

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

        # Parse status filter if provided
        status_filter = set()
        if status:
            status_filter = set(s.strip() for s in status.split(",") if s.strip())

        pois = poi_manager.list_pois(route_id=route_id)

        # Calculate ETA and distance for each POI
        from app.core.eta_service import get_eta_calculator

        eta_calc = get_eta_calculator()

        pois_with_eta = []
        for poi in pois:
            # Calculate distance using Haversine formula
            distance = eta_calc.calculate_distance(
                latitude, longitude, poi.latitude, poi.longitude
            )

            # Calculate ETA
            eta_seconds = eta_calc.calculate_eta(distance, speed_knots)

            # Calculate bearing
            bearing = calculate_bearing(latitude, longitude, poi.latitude, poi.longitude)

            # Calculate course status
            course_status = calculate_course_status(heading, bearing)

            # Apply status filter if specified
            if status_filter and course_status not in status_filter:
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
                    distance_meters=distance,
                    bearing_degrees=bearing,
                    course_status=course_status,
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
        return {"name": "No POIs available"}

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

    return {"name": closest.name if closest else "No POIs available"}


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
    - JSON object with 'eta_seconds' field containing ETA in seconds
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
        return {"eta_seconds": -1}

    from app.core.eta_service import get_eta_calculator
    eta_calc = get_eta_calculator()

    closest_eta = float('inf')

    for poi in pois:
        distance = eta_calc.calculate_distance(lat, lon, poi.latitude, poi.longitude)
        eta_seconds = eta_calc.calculate_eta(distance, speed)
        if eta_seconds < closest_eta:
            closest_eta = eta_seconds

    return {"eta_seconds": max(0, closest_eta) if closest_eta != float('inf') else -1}


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
        created_at=poi.created_at,
        updated_at=poi.updated_at,
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

    Returns:
    - Created POI object with ID and timestamps

    Raises:
    - 400: Invalid input data
    """
    try:
        poi = poi_manager.create_poi(poi_create)

        return POIResponse(
            id=poi.id,
            name=poi.name,
            latitude=poi.latitude,
            longitude=poi.longitude,
            icon=poi.icon,
            category=poi.category,
            description=poi.description,
            route_id=poi.route_id,
            created_at=poi.created_at,
            updated_at=poi.updated_at,
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


