"""Route and KML data models for the Starlink location service."""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class RoutePoint(BaseModel):
    """Represents a single point in a route (from KML coordinate)."""

    latitude: float = Field(..., description="Latitude in decimal degrees (-90 to 90)")
    longitude: float = Field(..., description="Longitude in decimal degrees (-180 to 180)")
    altitude: Optional[float] = Field(
        default=None, description="Altitude in meters above sea level"
    )
    sequence: int = Field(default=0, description="Order of point in route (0-indexed)")
    expected_arrival_time: Optional[datetime] = Field(
        default=None, description="Expected arrival time at this waypoint (UTC, ISO-8601)"
    )
    expected_segment_speed_knots: Optional[float] = Field(
        default=None, description="Expected speed for segment ending at this point (in knots)"
    )

    model_config = {"json_schema_extra": {"example": {"latitude": 40.7128, "longitude": -74.0060, "altitude": 100, "sequence": 0, "expected_arrival_time": "2025-10-27T16:57:55Z", "expected_segment_speed_knots": 598.0}}}


class RouteWaypoint(BaseModel):
    """Represents a waypoint parsed from a KML Placemark."""

    name: Optional[str] = Field(default=None, description="Waypoint name as defined in KML")
    description: Optional[str] = Field(default=None, description="Waypoint description text")
    style_url: Optional[str] = Field(default=None, description="Referenced style URL for icon/styling")
    latitude: float = Field(..., description="Waypoint latitude in decimal degrees")
    longitude: float = Field(..., description="Waypoint longitude in decimal degrees")
    altitude: Optional[float] = Field(default=None, description="Waypoint altitude if provided")
    order: int = Field(..., description="Document order index of this waypoint")
    role: Optional[str] = Field(
        default=None,
        description="Semantic role (e.g., 'departure', 'arrival', 'waypoint', 'alternate')",
    )
    expected_arrival_time: Optional[datetime] = Field(
        default=None, description="Expected arrival time at this waypoint (UTC, ISO-8601), parsed from description"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "WMSA",
                "description": "Sultan Abdul Aziz Shah\nTime Over Waypoint: 2025-10-27 16:57:55Z",
                "style_url": "#destWaypointIcon",
                "latitude": 3.132222,
                "longitude": 101.55028,
                "altitude": None,
                "order": 42,
                "role": "departure",
                "expected_arrival_time": "2025-10-27T16:57:55Z",
            }
        }
    }


class RouteMetadata(BaseModel):
    """Metadata about a parsed KML route."""

    name: str = Field(..., description="Name of the route from KML")
    description: Optional[str] = Field(default=None, description="Description from KML")
    file_path: str = Field(..., description="Path to the source KML file")
    imported_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When route was imported",
    )
    point_count: int = Field(..., description="Total number of points in route")


class RouteTimingProfile(BaseModel):
    """Timing profile for a route with expected speeds and arrival times."""

    departure_time: Optional[datetime] = Field(
        default=None, description="Expected departure time (UTC, ISO-8601)"
    )
    arrival_time: Optional[datetime] = Field(
        default=None, description="Expected arrival time at route end (UTC, ISO-8601)"
    )
    total_expected_duration_seconds: Optional[float] = Field(
        default=None, description="Total expected flight duration in seconds"
    )
    actual_departure_time: Optional[datetime] = Field(
        default=None, description="Observed departure time when flight state transitioned from PRE_DEPARTURE"
    )
    actual_arrival_time: Optional[datetime] = Field(
        default=None, description="Observed arrival time when flight state transitioned to POST_ARRIVAL"
    )
    flight_status: str = Field(
        default="pre_departure",
        description="Current flight status for route timing profile (pre_departure, in_flight, post_arrival)",
    )
    has_timing_data: bool = Field(
        default=False, description="Whether route has timing metadata"
    )
    segment_count_with_timing: int = Field(
        default=0, description="Number of segments with calculated expected speeds"
    )

    def get_total_duration(self) -> Optional[float]:
        """Get total expected duration in seconds."""
        if self.departure_time and self.arrival_time:
            delta = self.arrival_time - self.departure_time
            return delta.total_seconds()
        return self.total_expected_duration_seconds

    def is_departed(self) -> bool:
        """Return True if the flight has departed based on status or recorded timestamp."""
        status = (self.flight_status or "pre_departure").lower()
        if status != "pre_departure":
            return True
        return self.actual_departure_time is not None

    def is_in_flight(self) -> bool:
        """Return True if the current flight status reflects in-flight operations."""
        status = (self.flight_status or "pre_departure").lower()
        return status == "in_flight"

    model_config = {
        "json_schema_extra": {
            "example": {
                "departure_time": "2025-10-27T16:45:00Z",
                "arrival_time": "2025-10-27T22:05:00Z",
                "total_expected_duration_seconds": 20100.0,
                "actual_departure_time": "2025-10-27T16:48:12Z",
                "actual_arrival_time": None,
                "flight_status": "in_flight",
                "has_timing_data": True,
                "segment_count_with_timing": 128,
            }
        }
    }


class ParsedRoute(BaseModel):
    """Complete route data parsed from a KML file."""

    metadata: RouteMetadata = Field(..., description="Route metadata")
    points: list[RoutePoint] = Field(..., description="Ordered list of route points")
    waypoints: list[RouteWaypoint] = Field(
        default_factory=list,
        description="Optional waypoint placemarks associated with the route",
    )
    timing_profile: Optional[RouteTimingProfile] = Field(
        default=None, description="Timing profile if route has embedded timing data"
    )

    def get_total_distance(self) -> float:
        """
        Calculate total route distance using Haversine formula.

        Returns:
            Total distance in meters
        """
        import math

        if len(self.points) < 2:
            return 0.0

        earth_radius_m = 6371000.0  # Earth's radius in meters

        def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            """Calculate distance between two points using Haversine formula."""
            lat1_rad = math.radians(lat1)
            lon1_rad = math.radians(lon1)
            lat2_rad = math.radians(lat2)
            lon2_rad = math.radians(lon2)

            dlat = lat2_rad - lat1_rad
            dlon = lon2_rad - lon1_rad

            a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            return earth_radius_m * c

        total_distance = 0.0
        for i in range(len(self.points) - 1):
            p1 = self.points[i]
            p2 = self.points[i + 1]
            distance = haversine_distance(p1.latitude, p1.longitude, p2.latitude, p2.longitude)
            total_distance += distance

        return total_distance

    def get_bounds(self) -> dict[str, float]:
        """
        Get geographic bounding box of the route.

        Returns:
            Dictionary with min/max lat/lon
        """
        if not self.points:
            return {"min_lat": 0, "max_lat": 0, "min_lon": 0, "max_lon": 0}

        lats = [p.latitude for p in self.points]
        lons = [p.longitude for p in self.points]

        return {
            "min_lat": min(lats),
            "max_lat": max(lats),
            "min_lon": min(lons),
            "max_lon": max(lons),
        }


class RouteResponse(BaseModel):
    """Response model for route API endpoints."""

    id: str = Field(..., description="Unique route identifier (filename without extension)")
    name: str = Field(..., description="Route name from KML")
    description: Optional[str] = Field(default=None, description="Route description")
    point_count: int = Field(..., description="Number of points in route")
    is_active: bool = Field(default=False, description="Whether this is the active route")
    imported_at: datetime = Field(..., description="When route was imported")
    imported_poi_count: Optional[int] = Field(
        default=None,
        description="Number of POIs imported from the KML upload (only set on upload response)",
    )
    skipped_poi_count: Optional[int] = Field(
        default=None,
        description="Number of waypoint placemarks skipped during POI import",
    )
    has_timing_data: bool = Field(
        default=False, description="Whether route has embedded timing metadata"
    )
    timing_profile: Optional[RouteTimingProfile] = Field(
        default=None,
        description="Timing profile with departure/arrival/duration info (if has_timing_data is True)",
    )
    flight_phase: Optional[str] = Field(
        default=None,
        description="Current flight phase (pre_departure, in_flight, post_arrival) when route is active",
    )
    eta_mode: Optional[str] = Field(
        default=None,
        description="Current ETA mode (anticipated or estimated) when route is active",
    )


class RouteListResponse(BaseModel):
    """Response model for list routes endpoint."""

    routes: list[RouteResponse] = Field(..., description="List of available routes")
    total: int = Field(..., description="Total number of routes")


class RouteDetailResponse(BaseModel):
    """Response model for route detail endpoint."""

    id: str = Field(..., description="Unique route identifier")
    name: str = Field(..., description="Route name from KML")
    description: Optional[str] = Field(default=None, description="Route description")
    point_count: int = Field(..., description="Number of points in route")
    is_active: bool = Field(default=False, description="Whether this is the active route")
    imported_at: datetime = Field(..., description="When route was imported")
    file_path: str = Field(..., description="Path to KML file")
    points: list[RoutePoint] = Field(..., description="All route points")
    statistics: dict = Field(..., description="Route statistics (distance, bounds)")
    poi_count: int = Field(
        default=0, description="Number of POIs currently associated with this route"
    )
    waypoints: list[RouteWaypoint] = Field(
        default_factory=list,
        description="Waypoint placemarks extracted from the KML (for POI import/reference)",
    )
    timing_profile: Optional[RouteTimingProfile] = Field(
        default=None, description="Timing profile if route has embedded timing data"
    )
    has_timing_data: bool = Field(
        default=False, description="Whether the timing profile contains schedule metadata"
    )
    flight_phase: Optional[str] = Field(
        default=None,
        description="Current flight phase (pre_departure, in_flight, post_arrival) when route is active",
    )
    eta_mode: Optional[str] = Field(
        default=None,
        description="Current ETA mode (anticipated or estimated) when route is active",
    )


class RouteStatsResponse(BaseModel):
    """Response model for route statistics endpoint."""

    distance_meters: float = Field(..., description="Total route distance in meters")
    distance_km: float = Field(..., description="Total route distance in kilometers")
    point_count: int = Field(..., description="Total number of points")
    bounds: dict = Field(..., description="Geographic bounds (min/max lat/lon)")
