"""Satellite catalog API endpoints.

Provides REST API for accessing satellite metadata including transport type,
position, and other configuration data.
"""

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from app.satellites.catalog import get_satellite_catalog

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


# Create router
router = APIRouter(prefix="/api/satellites", tags=["satellites"])


@router.get("", response_model=List[SatelliteResponse])
async def list_satellites() -> List[SatelliteResponse]:
    """List all available satellites in the catalog.

    Returns all satellites from the satellite catalog with their metadata.
    Currently filters to X-Band satellites for mission planning use cases.

    Returns:
        List of satellites with id, transport, position, and color data.

    Example:
        GET /api/satellites
        Response: [
            {
                "satellite_id": "X-1",
                "transport": "X",
                "longitude": null,
                "slot": "X-Slot-1",
                "color": "#FF6B6B"
            }
        ]
    """
    catalog = get_satellite_catalog()

    # Get all X-Band satellites
    x_band_satellites = catalog.get_by_transport("X")

    # Convert to response model
    response_data = [
        SatelliteResponse(
            satellite_id=sat.satellite_id,
            transport=sat.transport,
            longitude=sat.longitude,
            slot=sat.slot,
            color=sat.color,
        )
        for sat in x_band_satellites
    ]

    return response_data
