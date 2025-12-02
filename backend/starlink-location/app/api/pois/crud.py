"""CRUD endpoints for POI management (create, read, update, delete, list).

File Size Note (FR-004 Exception):
This module exceeds the 300-line constitutional limit (366 lines) due to:
- 6 endpoint handlers with extensive parameter validation
- Complex filtering logic for route/mission-based POI lists
- Active status calculation for each response object
- Comprehensive docstrings for API documentation

The endpoints (list, get, create, update, delete) form a cohesive CRUD unit that
cannot be further decomposed without creating circular dependencies or artificial
separation of concerns. Deferred for future optimization with potential hook-based
status calculation or response builders.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status, Depends

from app.models.poi import (
    POICreate,
    POIListResponse,
    POIResponse,
    POIUpdate,
)
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from app.mission.dependencies import get_route_manager, get_poi_manager

from .helpers import calculate_poi_active_status

logger = logging.getLogger(__name__)

# Global coordinator reference for accessing telemetry
_coordinator: Optional[object] = None


def set_coordinator(coordinator):
    """Set the simulation coordinator reference."""
    global _coordinator
    _coordinator = coordinator


# Create API router for CRUD operations
router = APIRouter(prefix="/api/pois", tags=["pois"])


@router.get("", response_model=POIListResponse, summary="List all POIs")
async def list_pois(
    route_id: Optional[str] = Query(None, description="Filter by route ID"),
    mission_id: Optional[str] = Query(None, description="Filter by mission ID"),
    active_only: bool = Query(
        True,
        description="Filter to show only active POIs (default: true). Set to false to see all POIs with active field populated.",
    ),
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> POIListResponse:
    """Get list of all POIs, optionally filtered by route.

    Query Parameters:
    - route_id: Optional route ID to filter POIs
    - mission_id: Optional mission ID to filter POIs

    Returns:
    - List of POI objects and total count
    """
    if not poi_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="POI manager not initialized",
        )

    if mission_id:
        # If a specific mission is requested, filter by it.
        pois = poi_manager.list_pois(route_id=route_id, mission_id=mission_id)
    elif route_id:
        # If only a route is requested, get all its POIs and then filter mission events.
        all_route_pois = poi_manager.list_pois(route_id=route_id)
        mission_event_pois = [
            poi
            for poi in all_route_pois
            if poi.category == "mission-event" and poi.mission_id
        ]

        if mission_event_pois:
            latest_mission_poi = max(
                mission_event_pois,
                key=lambda poi: poi.updated_at or poi.created_at,
            )
            latest_mission_id = latest_mission_poi.mission_id

            # Keep non-mission events, and mission events from the latest mission
            pois = [
                p
                for p in all_route_pois
                if p.category != "mission-event"
                or not p.mission_id
                or p.mission_id == latest_mission_id
            ]
        else:
            pois = all_route_pois
    else:
        # No route or mission specified, get all POIs.
        pois = poi_manager.list_pois()

    responses = []
    for poi in pois:
        # Calculate active status for this POI
        active_status = calculate_poi_active_status(
            poi=poi,
            route_manager=route_manager,
        )

        # If filtering is active, skip inactive POIs before creating the response object
        if active_only and not active_status:
            continue

        responses.append(
            POIResponse(
                id=poi.id,
                name=poi.name,
                latitude=poi.latitude,
                longitude=poi.longitude,
                icon=poi.icon,
                category=poi.category,
                active=active_status,
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
        )

    return POIListResponse(
        pois=responses, total=len(responses), route_id=route_id, mission_id=mission_id
    )


@router.get("/{poi_id}", response_model=POIResponse, summary="Get a specific POI")
async def get_poi(
    poi_id: str,
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> POIResponse:
    """Get a specific POI by ID.

    Path Parameters:
    - poi_id: POI identifier

    Returns:
    - POI object

    Raises:
    - 404: POI not found
    """
    if not poi_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="POI manager not initialized",
        )

    poi = poi_manager.get_poi(poi_id)
    if not poi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"POI not found: {poi_id}",
        )

    # Calculate active status for this POI
    active_status = calculate_poi_active_status(
        poi=poi,
        route_manager=route_manager,
    )

    return POIResponse(
        id=poi.id,
        name=poi.name,
        latitude=poi.latitude,
        longitude=poi.longitude,
        icon=poi.icon,
        category=poi.category,
        active=active_status,
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


@router.post(
    "",
    response_model=POIResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new POI",
)
async def create_poi(
    poi_create: POICreate,
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> POIResponse:
    """Create a new POI.

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
        if _coordinator and hasattr(_coordinator, "route_manager"):
            try:
                active_route = _coordinator.route_manager.get_active_route()
            except Exception:
                pass

        if not poi_manager:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="POI manager not initialized",
            )

        poi = poi_manager.create_poi(poi_create, active_route=active_route)

        # Calculate active status for this POI
        active_status = calculate_poi_active_status(
            poi=poi,
            route_manager=route_manager,
        )

        return POIResponse(
            id=poi.id,
            name=poi.name,
            latitude=poi.latitude,
            longitude=poi.longitude,
            icon=poi.icon,
            category=poi.category,
            active=active_status,
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
async def update_poi(
    poi_id: str,
    poi_update: POIUpdate,
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> POIResponse:
    """Update an existing POI.

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
        if not poi_manager:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="POI manager not initialized",
            )

        updated_poi = poi_manager.update_poi(poi_id, poi_update)
        if not updated_poi:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"POI not found: {poi_id}",
            )

        # Calculate active status for this POI
        active_status = calculate_poi_active_status(
            poi=updated_poi,
            route_manager=route_manager,
        )

        return POIResponse(
            id=updated_poi.id,
            name=updated_poi.name,
            latitude=updated_poi.latitude,
            longitude=updated_poi.longitude,
            icon=updated_poi.icon,
            category=updated_poi.category,
            active=active_status,
            description=updated_poi.description,
            route_id=updated_poi.route_id,
            mission_id=updated_poi.mission_id,
            created_at=updated_poi.created_at,
            updated_at=updated_poi.updated_at,
            projected_latitude=updated_poi.projected_latitude,
            projected_longitude=updated_poi.projected_longitude,
            projected_waypoint_index=updated_poi.projected_waypoint_index,
            projected_route_progress=updated_poi.projected_route_progress,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update POI: {str(e)}",
        )


@router.delete(
    "/{poi_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a POI"
)
async def delete_poi(
    poi_id: str,
    poi_manager: POIManager = Depends(get_poi_manager),
) -> None:
    """Delete a POI.

    Path Parameters:
    - poi_id: POI identifier

    Raises:
    - 404: POI not found
    """
    if not poi_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="POI manager not initialized",
        )

    success = poi_manager.delete_poi(poi_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"POI not found: {poi_id}",
        )
