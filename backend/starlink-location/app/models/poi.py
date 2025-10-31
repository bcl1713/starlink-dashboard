"""Point of Interest (POI) data models for the Starlink location service."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


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
    latitude: float = Field(..., description="Latitude in decimal degrees (-90 to 90)")
    longitude: float = Field(..., description="Longitude in decimal degrees (-180 to 180)")
    icon: str = Field(default="marker", description="Icon identifier")
    category: Optional[str] = Field(default=None, description="POI category")
    description: Optional[str] = Field(default=None, description="POI description")
    route_id: Optional[str] = Field(default=None, description="Associated route ID")

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v):
        """Validate latitude is in valid range (-90 to 90)."""
        if not -90 <= v <= 90:
            raise ValueError("Latitude must be between -90 and 90 degrees")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v):
        """Validate longitude is in valid range (-180 to 180)."""
        if not -180 <= v <= 180:
            raise ValueError("Longitude must be between -180 and 180 degrees")
        return v

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
    latitude: Optional[float] = Field(default=None, description="Latitude (-90 to 90)")
    longitude: Optional[float] = Field(default=None, description="Longitude (-180 to 180)")
    icon: Optional[str] = Field(default=None, description="Icon identifier")
    category: Optional[str] = Field(default=None, description="POI category")
    description: Optional[str] = Field(default=None, description="POI description")

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v):
        """Validate latitude is in valid range (-90 to 90)."""
        if v is not None and not -90 <= v <= 90:
            raise ValueError("Latitude must be between -90 and 90 degrees")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v):
        """Validate longitude is in valid range (-180 to 180)."""
        if v is not None and not -180 <= v <= 180:
            raise ValueError("Longitude must be between -180 and 180 degrees")
        return v

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


class POIWithETA(BaseModel):
    """POI data with real-time ETA information."""

    poi_id: str = Field(..., description="POI identifier")
    name: str = Field(..., description="POI name")
    latitude: float = Field(..., description="POI latitude in decimal degrees")
    longitude: float = Field(..., description="POI longitude in decimal degrees")
    category: Optional[str] = Field(default=None, description="POI category")
    icon: str = Field(default="marker", description="Icon identifier")
    eta_seconds: float = Field(..., description="Estimated time to arrival in seconds (-1 if no speed)")
    distance_meters: float = Field(..., description="Distance to POI in meters")
    bearing_degrees: Optional[float] = Field(default=None, description="Bearing to POI in degrees (0=North)")
    course_status: Optional[str] = Field(
        default=None,
        description="Course status relative to heading: 'on_course' (<45°), 'slightly_off' (45-90°), 'off_track' (90-135°), 'behind' (>135°)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "poi_id": "jfk-airport",
                "name": "JFK Airport",
                "latitude": 40.6413,
                "longitude": -73.7781,
                "category": "airport",
                "icon": "airport",
                "eta_seconds": 1080.0,
                "distance_meters": 45000.0,
                "bearing_degrees": 125.0,
                "course_status": "on_course",
            }
        }
    }


class POIETAListResponse(BaseModel):
    """Response model for POI ETA list endpoint."""

    pois: list[POIWithETA] = Field(default_factory=list, description="List of POIs with ETA data")
    total: int = Field(default=0, description="Total number of POIs")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When this data was calculated")

    model_config = {
        "json_schema_extra": {
            "example": {
                "pois": [],
                "total": 0,
                "timestamp": "2025-10-30T10:00:00",
            }
        }
    }
