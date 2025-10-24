"""Point of Interest (POI) data models for the Starlink location service."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class POI(BaseModel):
    """POI stored in the system with all properties."""

    id: str = Field(..., description="Unique POI identifier (UUID or slug)")
    name: str = Field(..., description="Name of the POI")
    latitude: float = Field(..., description="Latitude in decimal degrees")
    longitude: float = Field(..., description="Longitude in decimal degrees")
    icon: str = Field(default="marker", description="Icon identifier for mapping")
    category: Optional[str] = Field(default=None, description="POI category (e.g., 'airport', 'city')")
    description: Optional[str] = Field(default=None, description="Detailed description of the POI")
    route_id: Optional[str] = Field(default=None, description="Associated route ID if route-specific")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When POI was created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="When POI was last updated")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "jfk-airport",
                "name": "JFK Airport",
                "latitude": 40.6413,
                "longitude": -73.7781,
                "icon": "airport",
                "category": "airport",
                "description": "John F. Kennedy International Airport",
                "route_id": None,
            }
        }
    }


class POICreate(BaseModel):
    """Request model for creating a new POI."""

    name: str = Field(..., description="Name of the POI", min_length=1)
    latitude: float = Field(..., description="Latitude in decimal degrees")
    longitude: float = Field(..., description="Longitude in decimal degrees")
    icon: str = Field(default="marker", description="Icon identifier")
    category: Optional[str] = Field(default=None, description="POI category")
    description: Optional[str] = Field(default=None, description="POI description")
    route_id: Optional[str] = Field(default=None, description="Associated route ID")

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Central Park",
                "latitude": 40.7829,
                "longitude": -73.9654,
                "icon": "park",
                "category": "landmark",
                "description": "Public park in Manhattan",
            }
        }
    }


class POIUpdate(BaseModel):
    """Request model for updating a POI."""

    name: Optional[str] = Field(default=None, description="Name of the POI")
    latitude: Optional[float] = Field(default=None, description="Latitude")
    longitude: Optional[float] = Field(default=None, description="Longitude")
    icon: Optional[str] = Field(default=None, description="Icon identifier")
    category: Optional[str] = Field(default=None, description="POI category")
    description: Optional[str] = Field(default=None, description="POI description")

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Central Park Updated",
                "icon": "landmark",
            }
        }
    }


class POIResponse(BaseModel):
    """Response model for POI API endpoints."""

    id: str
    name: str
    latitude: float
    longitude: float
    icon: str
    category: Optional[str]
    description: Optional[str]
    route_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "central-park",
                "name": "Central Park",
                "latitude": 40.7829,
                "longitude": -73.9654,
                "icon": "park",
                "category": "landmark",
                "description": "Public park in Manhattan",
                "route_id": None,
                "created_at": "2025-10-24T00:00:00",
                "updated_at": "2025-10-24T00:00:00",
            }
        }
    }


class POIListResponse(BaseModel):
    """Response model for POI list endpoint."""

    pois: list[POIResponse] = Field(default_factory=list, description="List of POIs")
    total: int = Field(default=0, description="Total number of POIs")
    route_id: Optional[str] = Field(default=None, description="Filter by route_id if applicable")

    model_config = {
        "json_schema_extra": {
            "example": {
                "pois": [],
                "total": 0,
                "route_id": None,
            }
        }
    }
