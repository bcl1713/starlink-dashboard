"""Satellite catalog API endpoints.

Provides REST API for accessing satellite metadata including transport type,
position, and other configuration data. Satellites are stored as POIs with
category="satellite" in the POI system.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.models.poi import POICreate, POIUpdate
from app.services.poi_manager import POIManager

logger = logging.getLogger(__name__)

# Define response model for satellite data
class SatelliteResponse(BaseModel):
    """Response model for satellite data."""

    satellite_id: str
    transport: str
    longitude: float | None = None
    slot: str | None = None
    color: str

    class Config:
        """Pydantic config."""

        from_attributes = True


class SatelliteCreate(BaseModel):
    """Request model for creating a satellite."""

    satellite_id: str = Field(..., description="Satellite ID (e.g., 'X-1')", min_length=1)
    transport: str = Field(..., description="Transport type (X, Ka, or Ku)", min_length=1)
    longitude: float = Field(..., description="Longitude in decimal degrees (-180 to 180)")
    slot: Optional[str] = Field(default=None, description="Orbital slot name")
    color: str = Field(default="#FFFFFF", description="Display color in hex format")


class SatelliteUpdate(BaseModel):
    """Request model for updating a satellite."""

    satellite_id: Optional[str] = Field(default=None, description="Satellite ID")
    transport: Optional[str] = Field(default=None, description="Transport type")
    longitude: Optional[float] = Field(default=None, description="Longitude (-180 to 180)")
    slot: Optional[str] = Field(default=None, description="Orbital slot name")
    color: Optional[str] = Field(default=None, description="Display color in hex format")


# Global POI manager instance (set by main.py)
_poi_manager: Optional[POIManager] = None


def set_poi_manager(manager: POIManager) -> None:
    """Set the POI manager instance (called by main.py during startup)."""
    global _poi_manager
    _poi_manager = manager


# Create router
router = APIRouter(prefix="/api/satellites", tags=["satellites"])


@router.get("", response_model=List[SatelliteResponse])
async def list_satellites() -> List[SatelliteResponse]:
    """List all available satellites in the catalog.

    Returns all satellites from the POI system where category="satellite".
    These are geostationary X-Band satellites at the equator (latitude=0).

    Returns:
        List of satellites with id, transport, position, and color data.

    Example:
        GET /api/satellites
        Response: [
            {
                "satellite_id": "X-1",
                "transport": "X",
                "longitude": -120.0,
                "slot": "X-Slot-1",
                "color": "#FF6B6B"
            }
        ]
    """
    if not _poi_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="POI manager not initialized",
        )

    # Get all POIs with category="satellite"
    pois = _poi_manager.list_pois()
    satellites = [poi for poi in pois if poi.category == "satellite"]

    # Convert POIs to satellite response format
    response_data = []
    for poi in satellites:
        transport = poi.icon or "X"
        # Default colors by transport type
        default_colors = {
            "X": "#FF6B6B",
            "Ka": "#4CAF50",
            "Ku": "#00BCD4",
        }
        color = default_colors.get(transport, "#FFFFFF")

        response_data.append(
            SatelliteResponse(
                satellite_id=poi.name,  # POI name is the satellite ID
                transport=transport,  # Use icon field to store transport type
                longitude=poi.longitude,
                slot=poi.description,  # Use description field for slot info
                color=color,  # Use default color based on transport
            )
        )

    return response_data


@router.post("", response_model=SatelliteResponse, status_code=status.HTTP_201_CREATED, summary="Create a new satellite")
async def create_satellite(satellite_create: SatelliteCreate) -> SatelliteResponse:
    """Create a new satellite.

    Satellites are stored as POIs with category="satellite" and latitude=0 (equator).

    Request Body:
    - satellite_id: Satellite ID (e.g., "X-1", "X-2")
    - transport: Transport type (X, Ka, or Ku)
    - longitude: Longitude position (-180 to 180 degrees)
    - slot: Optional orbital slot name
    - color: Optional display color in hex format

    Returns:
        Created satellite object

    Raises:
        - 400: Invalid input data
        - 503: POI manager not initialized
    """
    if not _poi_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="POI manager not initialized",
        )

    # Validate longitude
    if not -180 <= satellite_create.longitude <= 180:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Longitude must be between -180 and 180 degrees",
        )

    try:
        # Create POI with category="satellite", latitude=0 (equator)
        poi_create = POICreate(
            name=satellite_create.satellite_id,
            latitude=0.0,  # Geostationary satellites at equator
            longitude=satellite_create.longitude,
            icon=satellite_create.transport,  # Store transport type in icon field
            category="satellite",
            description=satellite_create.slot,  # Store slot name in description
        )

        poi = _poi_manager.create_poi(poi_create)

        # Get default color based on transport
        default_colors = {
            "X": "#FF6B6B",
            "Ka": "#4CAF50",
            "Ku": "#00BCD4",
        }
        color = satellite_create.color or default_colors.get(satellite_create.transport, "#FFFFFF")

        return SatelliteResponse(
            satellite_id=poi.name,
            transport=poi.icon or "X",
            longitude=poi.longitude,
            slot=poi.description,
            color=color,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create satellite: {str(e)}",
        )


@router.put("/{satellite_id}", response_model=SatelliteResponse, summary="Update a satellite")
async def update_satellite(
    satellite_id: str, satellite_update: SatelliteUpdate
) -> SatelliteResponse:
    """Update an existing satellite.

    Path Parameters:
    - satellite_id: Satellite ID to update

    Request Body (all fields optional):
    - satellite_id: New satellite ID (only if renaming)
    - transport: Transport type
    - longitude: Longitude position
    - slot: Orbital slot name
    - color: Display color

    Returns:
        Updated satellite object

    Raises:
        - 400: Invalid input data
        - 404: Satellite not found
        - 503: POI manager not initialized
    """
    if not _poi_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="POI manager not initialized",
        )

    # Find POI by satellite_id (name)
    poi = _poi_manager.find_poi_by_name(satellite_id)
    if not poi or poi.category != "satellite":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Satellite not found: {satellite_id}",
        )

    # Validate longitude if provided
    if satellite_update.longitude is not None:
        if not -180 <= satellite_update.longitude <= 180:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Longitude must be between -180 and 180 degrees",
            )

    try:
        # Build update payload
        poi_update_data = {}
        if satellite_update.satellite_id:
            poi_update_data["name"] = satellite_update.satellite_id
        if satellite_update.transport:
            poi_update_data["icon"] = satellite_update.transport
        if satellite_update.longitude is not None:
            poi_update_data["longitude"] = satellite_update.longitude
        if satellite_update.slot is not None:
            poi_update_data["description"] = satellite_update.slot

        poi_update = POIUpdate(**poi_update_data)
        updated_poi = _poi_manager.update_poi(poi.id, poi_update)

        if not updated_poi:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Satellite not found: {satellite_id}",
            )

        # Get default color based on transport
        transport = updated_poi.icon or "X"
        default_colors = {
            "X": "#FF6B6B",
            "Ka": "#4CAF50",
            "Ku": "#00BCD4",
        }
        color = satellite_update.color or default_colors.get(transport, "#FFFFFF")

        return SatelliteResponse(
            satellite_id=updated_poi.name,
            transport=transport,
            longitude=updated_poi.longitude,
            slot=updated_poi.description,
            color=color,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update satellite: {str(e)}",
        )


@router.delete("/{satellite_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a satellite")
async def delete_satellite(satellite_id: str) -> None:
    """Delete a satellite.

    Path Parameters:
    - satellite_id: Satellite ID to delete

    Raises:
        - 404: Satellite not found
        - 503: POI manager not initialized
    """
    if not _poi_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="POI manager not initialized",
        )

    # Find POI by satellite_id (name)
    poi = _poi_manager.find_poi_by_name(satellite_id)
    if not poi or poi.category != "satellite":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Satellite not found: {satellite_id}",
        )

    success = _poi_manager.delete_poi(poi.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Satellite not found: {satellite_id}",
        )
