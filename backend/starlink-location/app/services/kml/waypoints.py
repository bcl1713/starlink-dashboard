"""Waypoint identification and classification from KML placemarks."""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from app.models.route import RouteWaypoint
from app.services.kml.geometry import CoordinateTriple
from app.services.kml.timing import extract_timestamp_from_description

logger = logging.getLogger(__name__)


@dataclass
class WaypointData:
    """Represents a waypoint placemark extracted from the KML document."""

    name: Optional[str]
    description: Optional[str]
    style_url: Optional[str]
    coordinate: Optional[CoordinateTriple]
    altitude_mode: Optional[str]
    order: int


def identify_primary_waypoints(
    route_name: Optional[str], waypoints: list[WaypointData]
) -> tuple[Optional[WaypointData], Optional[WaypointData]]:
    """Identify departure and arrival waypoints from route name.

    Parses route name in format "DEPARTURE-ARRIVAL" (e.g., "RKSO-KADW").
    Falls back to first/last waypoint with #destWaypointIcon style if parsing fails.

    Args:
        route_name: Route name string, may contain airport codes
        waypoints: List of WaypointData objects to search

    Returns:
        Tuple of (departure_waypoint, arrival_waypoint), either may be None
    """
    departure_code: Optional[str] = None
    arrival_code: Optional[str] = None

    # Extract airport codes from route name (e.g., "RKSO-KADW" → RKSO, KADW)
    if route_name:
        route_name_upper = route_name.upper()
        match = re.search(r"\b([A-Z0-9]{3,5})[-→]+([A-Z0-9]{3,5})\b", route_name_upper)
        if match:
            departure_code, arrival_code = match.group(1), match.group(2)
            logger.info("Parsed route name: %s → %s", departure_code, arrival_code)

    # Try to match waypoints by code
    departure_wp = match_waypoint_by_code(waypoints, departure_code, prefer_last=False)
    arrival_wp = match_waypoint_by_code(waypoints, arrival_code, prefer_last=True)

    # Fallback: find first/last waypoint with #destWaypointIcon style
    if departure_wp is None:
        departure_wp = next(
            (
                wp
                for wp in waypoints
                if wp.coordinate is not None
                and wp.style_url
                and "dest" in wp.style_url.lower()
            ),
            None,
        )

    if arrival_wp is None:
        arrival_wp = next(
            (
                wp
                for wp in reversed(waypoints)
                if wp.coordinate is not None
                and wp.style_url
                and "dest" in wp.style_url.lower()
            ),
            None,
        )

    # Final fallback: use first/last waypoint with any coordinate
    if departure_wp is None:
        departure_wp = next((wp for wp in waypoints if wp.coordinate is not None), None)

    if arrival_wp is None:
        arrival_wp = next(
            (wp for wp in reversed(waypoints) if wp.coordinate is not None),
            None,
        )

    return departure_wp, arrival_wp


def match_waypoint_by_code(
    waypoints: list[WaypointData],
    code: Optional[str],
    *,
    prefer_last: bool,
) -> Optional[WaypointData]:
    """Find a waypoint whose name matches the supplied code.

    Args:
        waypoints: List of WaypointData objects to search
        code: Airport or waypoint code to match (case-insensitive)
        prefer_last: If True, search from end of list; if False, from beginning

    Returns:
        Matching WaypointData object or None if not found
    """
    if not code:
        return None

    code_upper = code.upper()
    iterator = reversed(waypoints) if prefer_last else iter(waypoints)

    for waypoint in iterator:
        if waypoint.name and waypoint.coordinate:
            if waypoint.name.upper() == code_upper:
                return waypoint

    return None


def build_route_waypoints(
    waypoints: list[WaypointData],
    departure_wp: Optional[WaypointData],
    arrival_wp: Optional[WaypointData],
) -> list[RouteWaypoint]:
    """Convert waypoint data into RouteWaypoint models with basic role tagging and timing extraction.

    Args:
        waypoints: List of WaypointData objects to convert
        departure_wp: Identified departure waypoint for role tagging
        arrival_wp: Identified arrival waypoint for role tagging

    Returns:
        List of RouteWaypoint objects with roles and timing data
    """
    route_waypoints: list[RouteWaypoint] = []

    for waypoint in waypoints:
        coord = waypoint.coordinate
        if coord is None:
            continue

        role: Optional[str] = None
        if departure_wp and waypoint.order == departure_wp.order:
            role = "departure"
        elif arrival_wp and waypoint.order == arrival_wp.order:
            role = "arrival"
        elif waypoint.style_url:
            style_lower = waypoint.style_url.lower()
            if "alt" in style_lower:
                role = "alternate"
            elif "dest" in style_lower:
                role = "waypoint"

        # Extract timestamp from waypoint description
        expected_arrival_time = extract_timestamp_from_description(waypoint.description)

        route_waypoints.append(
            RouteWaypoint(
                name=waypoint.name,
                description=waypoint.description,
                style_url=waypoint.style_url,
                latitude=coord.latitude,
                longitude=coord.longitude,
                altitude=coord.altitude,
                order=waypoint.order,
                role=role,
                expected_arrival_time=expected_arrival_time,
            )
        )

    return route_waypoints
