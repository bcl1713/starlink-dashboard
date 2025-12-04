"""KML timing data extraction and route timing profile generation."""

import logging
import re
from datetime import datetime
from typing import Optional

from app.models.route import RoutePoint, RouteWaypoint, RouteTimingProfile
from app.services.kml.geometry import haversine_distance

logger = logging.getLogger(__name__)

# Regex pattern for extracting timestamps from waypoint descriptions
TIMESTAMP_PATTERN = re.compile(
    r"Time Over Waypoint:\s*(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})Z"
)


def extract_timestamp_from_description(
    description: Optional[str],
) -> Optional[datetime]:
    """
    Extract timestamp from waypoint description.

    Looks for pattern: "Time Over Waypoint: YYYY-MM-DD HH:MM:SSZ"

    Args:
        description: Waypoint description text

    Returns:
        datetime object if timestamp found and valid, None otherwise

    Example:
        >>> desc = "Airport\\n Time Over Waypoint: 2025-10-27 16:51:13Z"
        >>> ts = extract_timestamp_from_description(desc)
        >>> ts.isoformat()
        '2025-10-27T16:51:13'
    """
    if not description:
        return None

    match = TIMESTAMP_PATTERN.search(description)
    if not match:
        return None

    try:
        timestamp_str = match.group(1)
        # Parse format: "2025-10-27 16:51:13"
        return datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except (ValueError, IndexError) as e:
        logger.debug(f"Failed to parse timestamp from description: {e}")
        return None


def assign_waypoint_timestamps_to_points(
    points: list[RoutePoint],
    waypoints: list[RouteWaypoint],
) -> None:
    """
    Assign waypoint timestamps to the nearest route points.

    For each waypoint with a timestamp, find the closest route point and assign the timestamp.
    This creates a mapping of specific times to specific locations along the route.

    Args:
        points: List of RoutePoint objects to be updated in-place
        waypoints: List of RouteWaypoint objects with extracted timestamps
    """
    # Build a list of waypoints with timestamps
    timed_waypoints = [wp for wp in waypoints if wp.expected_arrival_time is not None]

    if not timed_waypoints:
        logger.debug(
            "No waypoints with timestamps found; skipping timestamp assignment"
        )
        return

    logger.debug(
        f"Assigning timestamps from {len(timed_waypoints)} waypoints to route points"
    )

    # For each timed waypoint, find the nearest route point
    for waypoint in timed_waypoints:
        if points:
            # Find closest point by calculating haversine distance
            min_distance = float("inf")
            closest_point = None

            for point in points:
                distance = haversine_distance(
                    waypoint.latitude,
                    waypoint.longitude,
                    point.latitude,
                    point.longitude,
                )
                if distance < min_distance:
                    min_distance = distance
                    closest_point = point

            # Assign timestamp if we found a point (within reasonable tolerance, ~1000m)
            if closest_point is not None and min_distance < 1000:
                closest_point.expected_arrival_time = waypoint.expected_arrival_time
                logger.debug(
                    f"Assigned timestamp {waypoint.expected_arrival_time} to point "
                    f"({closest_point.latitude}, {closest_point.longitude}) "
                    f"(distance: {min_distance:.0f}m from waypoint {waypoint.name})"
                )


def calculate_segment_speeds(points: list[RoutePoint]) -> None:
    """
    Calculate expected speeds for segments between consecutive points with timing.

    For each pair of consecutive points where both have timestamps, calculates the
    speed using the haversine distance and time delta. Stores speed in the second
    point of each pair.

    Formula: speed_knots = distance_meters / time_seconds * (3600 / 1852)
    (converts m/s to knots: 1 knot = 1852 m / 3600 s)

    Args:
        points: List of RoutePoint objects to update in-place
    """
    if len(points) < 2:
        logger.debug("Insufficient points for speed calculation (need at least 2)")
        return

    speeds_calculated = 0

    for i in range(1, len(points)):
        prev_point = points[i - 1]
        curr_point = points[i]

        # Both points must have timestamps to calculate speed
        if (
            prev_point.expected_arrival_time is None
            or curr_point.expected_arrival_time is None
        ):
            continue

        # Calculate time delta in seconds
        time_delta = curr_point.expected_arrival_time - prev_point.expected_arrival_time
        time_seconds = time_delta.total_seconds()

        # Skip if time delta is zero or negative (invalid)
        if time_seconds <= 0:
            logger.debug(
                f"Skipping segment {i-1}->{i}: invalid time delta ({time_seconds}s)"
            )
            continue

        # Calculate distance in meters
        distance_meters = haversine_distance(
            prev_point.latitude,
            prev_point.longitude,
            curr_point.latitude,
            curr_point.longitude,
        )

        # Calculate speed: convert m/s to knots (1 knot = 1852 m / 3600 s)
        speed_ms = distance_meters / time_seconds
        speed_knots = speed_ms * (3600 / 1852)

        # Store speed in the current (end) point
        curr_point.expected_segment_speed_knots = speed_knots
        speeds_calculated += 1

        logger.debug(
            f"Segment {i-1}->{i}: {distance_meters:.0f}m in {time_seconds:.0f}s = {speed_knots:.1f} knots"
        )

    logger.debug(f"Calculated speeds for {speeds_calculated} segments")


def build_route_timing_profile(
    route_name: str,
    points: list[RoutePoint],
    waypoints: list[RouteWaypoint],
) -> Optional[RouteTimingProfile]:
    """
    Build RouteTimingProfile with departure/arrival times and total duration.

    Extracts departure code from route name (e.g., "KADW" from "KADW-PHNL") and
    finds corresponding departure and arrival timestamps from waypoints and points.

    Args:
        route_name: Route name (e.g., "Flight Plan KADW-PHNL")
        points: List of RoutePoint objects with assigned timestamps
        waypoints: List of RouteWaypoint objects with extracted timestamps

    Returns:
        RouteTimingProfile with timing data, or None if insufficient timing information
    """
    # Extract airport codes from route name (format: "...XXXX-YYYY" or "XXXX-YYYY")
    # Look for pattern like "KADW-PHNL" in the route name
    airport_pattern = re.search(r"([A-Z]{3,4})-([A-Z]{3,4})", route_name)

    if not airport_pattern:
        logger.debug(f"Could not extract airport codes from route name: {route_name}")
        return None

    departure_code = airport_pattern.group(1)
    arrival_code = airport_pattern.group(2)

    # Find departure waypoint matching the departure code
    departure_waypoint = None
    for wp in waypoints:
        if wp.name and wp.name.upper() == departure_code:
            departure_waypoint = wp
            break

    # Find first point with timestamp (departure time)
    departure_time = None
    if departure_waypoint and departure_waypoint.expected_arrival_time:
        departure_time = departure_waypoint.expected_arrival_time
    else:
        # Fallback: find first point with any timestamp
        for point in points:
            if point.expected_arrival_time:
                departure_time = point.expected_arrival_time
                break

    # Find arrival waypoint and time
    arrival_waypoint = None
    for wp in waypoints:
        if wp.name and wp.name.upper() == arrival_code:
            arrival_waypoint = wp
            break

    # Find last point with timestamp (arrival time)
    arrival_time = None
    if arrival_waypoint and arrival_waypoint.expected_arrival_time:
        arrival_time = arrival_waypoint.expected_arrival_time
    else:
        # Fallback: find last point with any timestamp
        for point in reversed(points):
            if point.expected_arrival_time:
                arrival_time = point.expected_arrival_time
                break

    # Count how many points have timing information
    points_with_timing = sum(1 for p in points if p.expected_arrival_time is not None)

    # If we have at least some timing information, create the profile
    if departure_time is not None or arrival_time is not None or points_with_timing > 0:
        # Calculate total duration if we have both times
        total_duration_seconds = None
        if departure_time and arrival_time:
            duration = arrival_time - departure_time
            total_duration_seconds = duration.total_seconds()

        timing_profile = RouteTimingProfile(
            departure_time=departure_time,
            arrival_time=arrival_time,
            total_expected_duration_seconds=total_duration_seconds,
            has_timing_data=points_with_timing > 0,
            segment_count_with_timing=sum(
                1 for p in points if p.expected_segment_speed_knots is not None
            ),
        )

        logger.info(
            f"Created timing profile for {route_name}: "
            f"departure={departure_time}, arrival={arrival_time}, "
            f"duration={total_duration_seconds}s, points_with_timing={points_with_timing}"
        )

        return timing_profile

    logger.debug(f"Insufficient timing data for route {route_name}")
    return None
