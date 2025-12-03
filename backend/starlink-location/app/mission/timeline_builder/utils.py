"""Utility functions for timeline computation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from app.mission.timeline_builder.calculator import RouteTemporalProjector

from app.models.route import ParsedRoute, RouteWaypoint

logger = logging.getLogger(__name__)

DEFAULT_CRUISE_ALTITUDE_M = 10668.0  # ~35,000 ft


def ensure_datetime(value: datetime) -> datetime:
    """Ensure datetime has timezone info (UTC if missing)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def interpolate_altitude(
    prev_altitude: float | None,
    next_altitude: float | None,
    ratio: float,
) -> float:
    """Interpolate altitude between two points."""
    if prev_altitude is not None and next_altitude is not None:
        return prev_altitude + ratio * (next_altitude - prev_altitude)
    if prev_altitude is not None:
        return prev_altitude
    if next_altitude is not None:
        return next_altitude
    return DEFAULT_CRUISE_ALTITUDE_M


def interpolate_longitude(prev_lon: float, next_lon: float, ratio: float) -> float:
    """Interpolate longitude across the dateline using the shortest path."""
    import math

    delta = ((next_lon - prev_lon + 540.0) % 360.0) - 180.0
    interpolated = prev_lon + delta * ratio
    # Normalize back to [-180, 180]
    interpolated = ((interpolated + 180.0) % 360.0) - 180.0
    # Handle edge case of -180 exactly
    if math.isclose(interpolated, -180.0):
        return 180.0
    return interpolated


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute haversine distance between two points in meters."""
    import math

    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def pick_satellite(values: Sequence[str]) -> str | None:
    """Pick a satellite from a collection (sorts and returns first)."""
    if not values:
        return None
    return sorted(values)[0]


def nearest_waypoint_name(
    route: ParsedRoute, sample_lat: float, sample_lon: float
) -> str | None:
    """Return nearest waypoint name for debugging."""
    if not route.waypoints:
        return None

    closest_name: str | None = None
    closest_distance = float("inf")

    for waypoint in route.waypoints:
        if waypoint.latitude is None or waypoint.longitude is None:
            continue
        distance = haversine_meters(
            sample_lat,
            sample_lon,
            waypoint.latitude,
            waypoint.longitude,
        )
        if distance < closest_distance:
            closest_distance = distance
            closest_name = waypoint.name or f"waypoint-{waypoint.order}"

    return closest_name


def find_waypoint_coordinates(
    route: ParsedRoute, waypoint_name: str | None
) -> tuple[float, float] | None:
    """Find coordinates for a waypoint by name."""
    if not route or not waypoint_name:
        return None
    normalized = waypoint_name.strip().lower()
    for waypoint in route.waypoints or []:
        name = (waypoint.name or f"waypoint-{waypoint.order}").strip().lower()
        if (
            name == normalized
            and waypoint.latitude is not None
            and waypoint.longitude is not None
        ):
            return waypoint.latitude, waypoint.longitude
    return None


def timestamp_for_waypoint(
    waypoint: RouteWaypoint | None, projector: RouteTemporalProjector
) -> datetime | None:
    """Get timestamp for a waypoint (from timing or projection)."""
    if not waypoint:
        return None
    if waypoint.expected_arrival_time:
        return waypoint.expected_arrival_time
    projection = projector.project(waypoint.latitude, waypoint.longitude)
    return projection.timestamp
