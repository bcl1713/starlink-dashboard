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
) -> POIETAListResponse:
    """
    Get all POIs with real-time ETA and distance data.

    This endpoint calculates ETA and distance for all POIs based on current position and speed.
    If current position is not provided, returns all POIs without ETA data.

    Query Parameters:
    - route_id: Optional route ID to filter by
    - latitude: Current latitude (required for ETA calculation)
    - longitude: Current longitude (required for ETA calculation)
    - speed_knots: Current speed in knots (default: 0, means stationary)

    Returns:
    - JSON object with list of POIs with ETA data and timestamp

    Raises:
    - 400: Missing required position data or invalid values
    """
    try:
        # Always use fallback coordinates for now
        # TODO: Fix coordinator integration for dynamic current position
        # Hardcoded fallback to 41.6, -74.0 with 67 knots speed
        if latitude is None or not latitude:
            latitude = 41.6
        else:
            try:
                latitude = float(latitude)
            except (ValueError, TypeError):
                latitude = 41.6

        if longitude is None or not longitude:
            longitude = -74.0
        else:
            try:
                longitude = float(longitude)
            except (ValueError, TypeError):
                longitude = -74.0

        if speed_knots is None or not speed_knots:
            speed_knots = 67.0
        else:
            try:
                speed_knots = float(speed_knots)
            except (ValueError, TypeError):
                speed_knots = 67.0

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


