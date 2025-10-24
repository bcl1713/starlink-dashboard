"""Route and KML data models for the Starlink location service."""

from datetime import datetime
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

    model_config = {"json_schema_extra": {"example": {"latitude": 40.7128, "longitude": -74.0060, "altitude": 100, "sequence": 0}}}


class RouteMetadata(BaseModel):
    """Metadata about a parsed KML route."""

    name: str = Field(..., description="Name of the route from KML")
    description: Optional[str] = Field(default=None, description="Description from KML")
    file_path: str = Field(..., description="Path to the source KML file")
    imported_at: datetime = Field(
        default_factory=datetime.utcnow, description="When route was imported"
    )
    point_count: int = Field(..., description="Total number of points in route")


class ParsedRoute(BaseModel):
    """Complete route data parsed from a KML file."""

    metadata: RouteMetadata = Field(..., description="Route metadata")
    points: list[RoutePoint] = Field(..., description="Ordered list of route points")

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
