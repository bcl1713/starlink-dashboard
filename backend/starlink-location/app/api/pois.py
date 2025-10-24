"""POI CRUD API endpoints for managing points of interest."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.models.poi import POICreate, POIListResponse, POIResponse, POIUpdate
from app.services.poi_manager import POIManager

# Initialize POI manager
poi_manager = POIManager()

# Create API router
router = APIRouter(prefix="/api/pois", tags=["pois"])


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
