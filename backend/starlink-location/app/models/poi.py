"""Point of Interest (POI) data models for the Starlink location service."""

# FR-004: File exceeds 300 lines (337 lines) because POI models define 6+ related
# Pydantic classes with shared validators, enums, and geographic calculations.
# Splitting would fragment the POI domain model. Deferred to v0.4.0.

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class POI(BaseModel):
    """POI stored in the system with all properties."""

    id: str = Field(..., description="Unique POI identifier (UUID or slug)")
    name: str = Field(..., description="Name of the POI")
    latitude: float = Field(..., description="Latitude in decimal degrees")
    longitude: float = Field(..., description="Longitude in decimal degrees")
    icon: str = Field(default="marker", description="Icon identifier for mapping")
    category: str | None = Field(
        default=None, description="POI category (e.g., 'airport', 'city')"
    )
    description: str | None = Field(
        default=None, description="Detailed description of the POI"
    )
    route_id: str | None = Field(
        default=None, description="Associated route ID if route-specific"
    )
    mission_id: str | None = Field(
        default=None, description="Associated mission ID if mission-scoped"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When POI was created",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When POI was last updated",
    )
    # Route projection fields (calculated when route is active, cleared on deactivation)
    projected_latitude: float | None = Field(
        default=None, description="Latitude of projection point on active route"
    )
    projected_longitude: float | None = Field(
        default=None, description="Longitude of projection point on active route"
    )
    projected_waypoint_index: int | None = Field(
        default=None, description="Index of closest route point"
    )
    projected_route_progress: float | None = Field(
        default=None,
        description="Progress percentage (0-100) where POI projects on route",
    )

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
                "mission_id": None,
                "projected_latitude": None,
                "projected_longitude": None,
                "projected_waypoint_index": None,
                "projected_route_progress": None,
            }
        }
    }


class POICreate(BaseModel):
    """Request model for creating a new POI."""

    name: str = Field(..., description="Name of the POI", min_length=1)
    latitude: float = Field(..., description="Latitude in decimal degrees (-90 to 90)")
    longitude: float = Field(
        ..., description="Longitude in decimal degrees (-180 to 180)"
    )
    icon: str = Field(default="marker", description="Icon identifier")
    category: str | None = Field(default=None, description="POI category")
    description: str | None = Field(default=None, description="POI description")
    mission_id: str | None = Field(default=None, description="Associated mission ID")
    route_id: str | None = Field(default=None, description="Associated route ID")

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
        """Validate and normalize longitude to the -180 to 180 degree range."""
        if not -180 <= v <= 360:
            raise ValueError("Longitude must be between -180 and 360 degrees")
        if v > 180:
            v -= 360
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
                "mission_id": None,
            }
        }
    }


class POIUpdate(BaseModel):
    """Request model for updating a POI."""

    name: str | None = Field(default=None, description="Name of the POI")
    latitude: float | None = Field(default=None, description="Latitude (-90 to 90)")
    longitude: float | None = Field(default=None, description="Longitude (-180 to 180)")
    icon: str | None = Field(default=None, description="Icon identifier")
    category: str | None = Field(default=None, description="POI category")
    description: str | None = Field(default=None, description="POI description")

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
        """Validate and normalize longitude to the -180 to 180 degree range."""
        if v is not None:
            if not -180 <= v <= 360:
                raise ValueError("Longitude must be between -180 and 360 degrees")
            if v > 180:
                v -= 360
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
    category: str | None
    active: bool = Field(
        ...,
        description="Whether this POI is currently active (based on associated route/mission active status)",
    )
    description: str | None
    route_id: str | None
    mission_id: str | None = None
    created_at: datetime
    updated_at: datetime
    # Route projection fields (only populated when route is active)
    projected_latitude: float | None = None
    projected_longitude: float | None = None
    projected_waypoint_index: int | None = None
    projected_route_progress: float | None = None

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
                "mission_id": None,
                "created_at": "2025-10-24T00:00:00",
                "updated_at": "2025-10-24T00:00:00",
                "projected_latitude": None,
                "projected_longitude": None,
                "projected_waypoint_index": None,
                "projected_route_progress": None,
            }
        }
    }


class POIListResponse(BaseModel):
    """Response model for POI list endpoint."""

    pois: list[POIResponse] = Field(default_factory=list, description="List of POIs")
    total: int = Field(default=0, description="Total number of POIs")
    route_id: str | None = Field(
        default=None, description="Filter by route_id if applicable"
    )
    mission_id: str | None = Field(
        default=None, description="Filter by mission_id if applicable"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "pois": [],
                "total": 0,
                "route_id": None,
                "mission_id": None,
            }
        }
    }


class POIWithETA(BaseModel):
    """POI data with real-time ETA information."""

    poi_id: str = Field(..., description="POI identifier")
    name: str = Field(..., description="POI name")
    latitude: float = Field(..., description="POI latitude in decimal degrees")
    longitude: float = Field(..., description="POI longitude in decimal degrees")
    category: str | None = Field(default=None, description="POI category")
    icon: str = Field(default="marker", description="Icon identifier")
    active: bool = Field(
        ...,
        description="Whether this POI is currently active (based on associated route/mission active status)",
    )
    eta_seconds: float = Field(
        ..., description="Estimated time to arrival in seconds (-1 if no speed)"
    )
    eta_type: str = Field(
        default="estimated",
        description="ETA type: 'anticipated' (pre-departure, based on flight plan) or 'estimated' (post-departure, based on telemetry)",
    )
    is_pre_departure: bool = Field(
        default=False,
        description="True when the active flight has not yet departed; anticipated ETAs will set this flag",
    )
    flight_phase: str | None = Field(
        default=None,
        description="Flight phase associated with this ETA (pre_departure, in_flight, post_arrival)",
    )
    distance_meters: float = Field(..., description="Distance to POI in meters")
    bearing_degrees: float | None = Field(
        default=None, description="Bearing to POI in degrees (0=North)"
    )
    course_status: str | None = Field(
        default=None,
        description="Course status relative to heading: 'on_course' (<45°), 'slightly_off' (45-90°), 'off_track' (90-135°), 'behind' (>135°)",
    )
    # Route-aware projection fields (populated when active route exists)
    is_on_active_route: bool = Field(
        default=False, description="Whether POI projects to active route"
    )
    projected_latitude: float | None = Field(
        default=None, description="Projected point on route"
    )
    projected_longitude: float | None = Field(
        default=None, description="Projected point on route"
    )
    projected_waypoint_index: int | None = Field(
        default=None, description="Index of closest route point"
    )
    projected_route_progress: float | None = Field(
        default=None, description="Progress % where POI projects on route"
    )
    route_aware_status: str | None = Field(
        default=None,
        description="Route awareness status: 'ahead_on_route', 'already_passed', 'not_on_route', 'pre_departure', or None if no active route",
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
                "eta_type": "estimated",
                "is_pre_departure": False,
                "flight_phase": "in_flight",
                "distance_meters": 45000.0,
                "bearing_degrees": 125.0,
                "course_status": "on_course",
                "is_on_active_route": True,
                "projected_latitude": 40.6400,
                "projected_longitude": -73.7800,
                "projected_waypoint_index": 42,
                "projected_route_progress": 45.5,
                "route_aware_status": "ahead_on_route",
            }
        }
    }


class POIETAListResponse(BaseModel):
    """Response model for POI ETA list endpoint."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "pois": [],
                "total": 0,
                "timestamp": "2025-10-30T10:00:00Z",
            }
        },
    )

    pois: list[POIWithETA] = Field(
        default_factory=list, description="List of POIs with ETA data"
    )
    total: int = Field(default=0, description="Total number of POIs")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this data was calculated",
    )

    @model_validator(mode="after")
    def _timestamp_must_be_utc_aware(self) -> "POIETAListResponse":
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        self.timestamp = self.timestamp.astimezone(timezone.utc)
        return self
