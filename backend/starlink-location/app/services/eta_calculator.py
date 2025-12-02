"""ETA and distance calculation service with speed smoothing and dual-mode support."""

import logging
import math
import time
from collections import deque
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from app.models.poi import POI
from app.models.flight_status import ETAMode, FlightPhase

if TYPE_CHECKING:
    from app.models.route import ParsedRoute

logger = logging.getLogger(__name__)


class ETACalculator:
    """
    Calculate ETA and distance to POIs with speed smoothing.

    Features:
    - Exponential moving average for speed smoothing
    - Haversine formula for great-circle distance
    - Support for custom speed update intervals
    - Tracking of passed POIs
    """

    def __init__(
        self,
        smoothing_duration_seconds: float = 120.0,
        default_speed_knots: float = 150.0,
    ):
        """
        Initialize ETA calculator.

        Args:
            smoothing_duration_seconds: Duration of time-based smoothing window in seconds (default: 120s = 2 min)
            default_speed_knots: Default speed to use when no speed data available
        """
        self.smoothing_duration_seconds = smoothing_duration_seconds
        self.default_speed_knots = default_speed_knots
        self.earth_radius_m = 6371000.0  # Earth's radius in meters

        # Speed smoothing using time-based rolling window
        # Store tuples of (speed, timestamp) to enable time-based windowing
        self._speed_history: deque[tuple[float, float]] = (
            deque()
        )  # (speed_knots, timestamp)
        self._smoothed_speed: float = default_speed_knots
        self._last_update_time: Optional[datetime] = None

        # POI tracking
        self._passed_pois: set[str] = set()  # Track POI IDs that have been passed
        self._poi_distance_threshold_m = 100.0  # 100m threshold for "passed"

    def update_speed(self, current_speed_knots: float) -> None:
        """
        Update current speed and recalculate smoothed speed.

        Uses time-based rolling window average for speed smoothing.
        Only considers samples within the smoothing window duration.

        Args:
            current_speed_knots: Current speed in knots
        """
        current_time = time.time()
        self._speed_history.append((current_speed_knots, current_time))

        # Remove samples older than smoothing window
        cutoff_time = current_time - self.smoothing_duration_seconds
        while self._speed_history and self._speed_history[0][1] < cutoff_time:
            self._speed_history.popleft()

        # Calculate average of samples within window
        if len(self._speed_history) > 0:
            self._smoothed_speed = sum(speed for speed, _ in self._speed_history) / len(
                self._speed_history
            )
        else:
            self._smoothed_speed = self.default_speed_knots

        self._last_update_time = datetime.now(timezone.utc)

        logger.debug(
            f"Speed updated: raw={current_speed_knots:.1f}kn, smoothed={self._smoothed_speed:.1f}kn, samples={len(self._speed_history)}"
        )

    def get_smoothed_speed(self) -> float:
        """
        Get current smoothed speed.

        Returns:
            Smoothed speed in knots
        """
        return self._smoothed_speed

    def calculate_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Calculate great-circle distance between two points using Haversine formula.

        Args:
            lat1: Starting latitude in degrees
            lon1: Starting longitude in degrees
            lat2: Ending latitude in degrees
            lon2: Ending longitude in degrees

        Returns:
            Distance in meters
        """
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return self.earth_radius_m * c

    def calculate_eta(
        self, distance_meters: float, speed_knots: Optional[float] = None
    ) -> float:
        """
        Calculate estimated time to arrival (ETA) for a given distance and speed.

        Args:
            distance_meters: Distance in meters
            speed_knots: Speed in knots (uses smoothed speed if not provided)

        Returns:
            ETA in seconds (negative for passed POIs, -1 for zero/no speed)
        """
        speed = speed_knots if speed_knots is not None else self._smoothed_speed

        # Handle zero or very small speed (below 0.5 knots is effectively stationary)
        # This prevents division by near-zero values and extreme ETA estimates
        # At less than 0.5 knots, meaningful ETA predictions are unreliable
        if speed < 0.5:
            return -1.0

        # Convert distance to nautical miles
        nautical_miles = distance_meters / 1852.0  # 1 nautical mile = 1852 meters

        # Calculate time in hours
        time_hours = nautical_miles / speed

        # Convert to seconds
        eta_seconds = time_hours * 3600.0

        return eta_seconds

    def calculate_poi_metrics(
        self,
        current_lat: float,
        current_lon: float,
        pois: list[POI],
        speed_knots: Optional[float] = None,
        active_route: Optional["ParsedRoute"] = None,
        eta_mode: ETAMode = ETAMode.ESTIMATED,
        flight_phase: Optional[FlightPhase] = None,
    ) -> dict[str, dict]:
        """
        Calculate distance and ETA metrics for all POIs with dual-mode support.

        When an active route with timing data is provided, POIs that are waypoints
        on that route will use route-aware ETA calculations (segment-based speeds).
        POIs not on the active route fall back to distance/speed calculation.

        Args:
            current_lat: Current latitude
            current_lon: Current longitude
            pois: List of POI objects
            speed_knots: Current speed in knots (uses smoothed speed if not provided)
            active_route: Optional ParsedRoute with timing data for route-aware calculations
            eta_mode: ETA calculation mode (ANTICIPATED or ESTIMATED)

        Returns:
            Dictionary mapping POI ID to dict with 'eta', 'distance', 'passed', 'eta_type',
            and flight phase metadata keys
        """
        metrics = {}
        phase_value = flight_phase.value if flight_phase else None
        is_pre_departure = (
            flight_phase == FlightPhase.PRE_DEPARTURE if flight_phase else False
        )

        for poi in pois:
            distance = self.calculate_distance(
                current_lat, current_lon, poi.latitude, poi.longitude
            )

            # Try route-aware ETA calculation if active route available
            eta = None
            if (
                active_route
                and poi.route_id
                and poi.route_id == active_route.metadata.file_path
            ):
                if eta_mode == ETAMode.ESTIMATED:
                    # In estimated mode, use speed blending for more accurate ETAs
                    eta = self._calculate_route_aware_eta_estimated(
                        current_lat, current_lon, poi, active_route, speed_knots
                    )
                else:
                    # In anticipated mode, use planned route times
                    eta = self._calculate_route_aware_eta_anticipated(
                        current_lat, current_lon, poi, active_route
                    )

            # Fall back to distance/speed calculation if route-aware failed
            if eta is None:
                # Both modes fall back to distance-based calculation
                # In anticipated mode, use a conservative default speed if no timing data available
                fallback_speed = (
                    speed_knots if speed_knots is not None else self.default_speed_knots
                )
                eta = self.calculate_eta(distance, fallback_speed)

            # Determine if POI has been passed
            passed = distance < self._poi_distance_threshold_m

            # Track passed POIs
            if passed and poi.id not in self._passed_pois:
                self._passed_pois.add(poi.id)
                logger.info(f"POI passed: {poi.name} (ID: {poi.id})")

            metrics[poi.id] = {
                "poi_name": poi.name,
                "poi_category": poi.category
                or "",  # Use empty string for null categories
                "distance_meters": distance,
                "eta_seconds": eta,
                "eta_type": eta_mode.value,
                "passed": passed,
                "flight_phase": phase_value,
                "is_pre_departure": is_pre_departure,
            }

        return metrics

    def _calculate_route_aware_eta(
        self,
        current_lat: float,
        current_lon: float,
        poi: POI,
        active_route: "ParsedRoute",
    ) -> Optional[float]:
        """
        DEPRECATED: Use _calculate_route_aware_eta_estimated or _calculate_route_aware_eta_anticipated instead.

        This method is kept for backward compatibility but delegates to estimated mode.
        """
        return self._calculate_route_aware_eta_estimated(
            current_lat, current_lon, poi, active_route
        )

    def _calculate_route_aware_eta_estimated(
        self,
        current_lat: float,
        current_lon: float,
        poi: POI,
        active_route: "ParsedRoute",
        current_speed_knots: Optional[float] = None,
    ) -> Optional[float]:
        """
        Calculate ETA using segment-based speeds with speed blending (estimated/in-flight mode).

        Implements intelligent speed calculation:
        - Current segment: Blend current speed with expected segment speed
          Formula: blended_speed = (current_speed + expected_speed) / 2
        - Future segments: Use expected segment speeds from route timing data
        - Off-route POIs: Project to route, then apply same logic

        Handles two cases:
        1. POI is on the active route (matches a waypoint by name)
        2. POI is off-route but has projection data

        Args:
            current_lat: Current latitude
            current_lon: Current longitude
            poi: POI object whose name should match a waypoint name (or has projection data)
            active_route: ParsedRoute with timing data
            current_speed_knots: Current speed for blending (uses smoothed speed if not provided)

        Returns:
            ETA in seconds if route-aware calculation succeeds, None to fall back to distance/speed
        """
        # Early return if no timing data on route
        if (
            not active_route.timing_profile
            or not active_route.timing_profile.has_timing_data
        ):
            return None

        # Try to find matching waypoint on route by name (on-route POI case)
        matching_waypoint = None
        matching_waypoint_index = None
        for idx, waypoint in enumerate(active_route.waypoints):
            if waypoint.name.upper() == poi.name.upper():
                matching_waypoint = waypoint
                matching_waypoint_index = idx
                break

        # If POI is on the route, use direct route-aware calculation
        if matching_waypoint:
            return self._calculate_on_route_eta_estimated(
                current_lat,
                current_lon,
                matching_waypoint,
                active_route,
                current_speed_knots,
            )

        # If POI is not on route but has projection data, use projection-based calculation
        if (
            poi.projected_latitude is not None
            and poi.projected_longitude is not None
            and poi.projected_route_progress is not None
        ):
            return self._calculate_off_route_eta_with_projection_estimated(
                current_lat, current_lon, poi, active_route, current_speed_knots
            )

        # If neither on-route nor has projection, return None to fall back to distance/speed
        return None

    def _calculate_route_aware_eta_anticipated(
        self,
        current_lat: float,
        current_lon: float,
        poi: POI,
        active_route: "ParsedRoute",
    ) -> Optional[float]:
        """
        Calculate ETA using expected times from flight plan (anticipated/pre-departure mode).

        Pre-departure, we don't have actual speed data, so we use:
        - Waypoint expected_arrival_time from route timing data
        - Uses POI's projected waypoint index if available

        Handles two cases:
        1. POI is on the active route (matches a waypoint by name or projected index)
        2. POI is off-route with projection data

        Args:
            current_lat: Current latitude
            current_lon: Current longitude
            poi: POI object with optional projected_waypoint_index
            active_route: ParsedRoute with timing data

        Returns:
            ETA in seconds (time until expected arrival) if available, None to fall back
        """
        # Early return if no timing data on route
        if (
            not active_route.timing_profile
            or not active_route.timing_profile.has_timing_data
        ):
            return None

        # Check if route has departure time for reference
        if not active_route.timing_profile.departure_time:
            return None

        try:
            current_time = datetime.now(timezone.utc)

            # First, try to find matching waypoint on route by name
            # This handles explicitly named waypoints in the KML
            for waypoint in active_route.waypoints:
                if waypoint.name and waypoint.name.upper() == poi.name.upper():
                    # Found matching waypoint with expected arrival time
                    if waypoint.expected_arrival_time:
                        # Calculate time until expected arrival
                        time_until_arrival = (
                            waypoint.expected_arrival_time - current_time
                        )
                        eta_seconds = time_until_arrival.total_seconds()

                        # Return positive ETA or -1 if time has passed
                        if eta_seconds > 0:
                            return eta_seconds
                        else:
                            return -1.0

            # Second, try to use POI's projected waypoint index
            # This is set by route-aware projection for off-route POIs
            if poi.projected_waypoint_index is not None:
                waypoint_idx = poi.projected_waypoint_index
                if 0 <= waypoint_idx < len(active_route.waypoints):
                    waypoint = active_route.waypoints[waypoint_idx]
                    if waypoint.expected_arrival_time:
                        # Calculate time until expected arrival at projected waypoint
                        time_until_arrival = (
                            waypoint.expected_arrival_time - current_time
                        )
                        eta_seconds = time_until_arrival.total_seconds()

                        # Return positive ETA or -1 if time has passed
                        if eta_seconds > 0:
                            return eta_seconds
                        else:
                            return -1.0

            # If no waypoint found, return None to fall back to distance/speed
            return None

        except Exception as e:
            logger.debug(f"Anticipated ETA calculation failed for {poi.name}: {e}")
            return None

    def _calculate_on_route_eta_estimated(
        self,
        current_lat: float,
        current_lon: float,
        destination_waypoint: "RouteWaypoint",
        active_route: "ParsedRoute",
        current_speed_knots: Optional[float] = None,
    ) -> Optional[float]:
        """
        Calculate ETA for a waypoint with speed blending (estimated/in-flight mode).

        Uses intelligent speed calculation:
        - Current segment: Blend current speed with expected segment speed
          Formula: blended_speed = (current_speed + expected_speed) / 2
        - Future segments: Use expected segment speeds from route timing data

        Args:
            current_lat: Current latitude
            current_lon: Current longitude
            destination_waypoint: Destination waypoint on the route
            active_route: ParsedRoute with timing data
            current_speed_knots: Current speed for blending (uses smoothed speed if not provided)

        Returns:
            ETA in seconds if calculation succeeds, None otherwise
        """
        try:
            speed = (
                current_speed_knots
                if current_speed_knots is not None
                else self._smoothed_speed
            )

            # Find nearest route point to current position
            nearest_point_index = 0
            nearest_distance = float("inf")

            for idx, point in enumerate(active_route.points):
                dist = self.calculate_distance(
                    current_lat, current_lon, point.latitude, point.longitude
                )
                if dist < nearest_distance:
                    nearest_distance = dist
                    nearest_point_index = idx

            # Calculate remaining distance and time segment by segment
            total_eta_seconds = 0.0

            # Walk through segments from nearest point to destination
            for idx in range(nearest_point_index, len(active_route.points) - 1):
                current_point = active_route.points[idx]
                next_point = active_route.points[idx + 1]

                # Check if we've reached the destination waypoint
                if (
                    current_point.latitude == destination_waypoint.latitude
                    and current_point.longitude == destination_waypoint.longitude
                ):
                    break

                # Calculate segment distance
                segment_distance = self.calculate_distance(
                    current_point.latitude,
                    current_point.longitude,
                    next_point.latitude,
                    next_point.longitude,
                )

                # Determine speed for this segment with blending for current segment
                if idx == nearest_point_index:
                    # Current segment: blend current speed with expected speed
                    expected_speed = current_point.expected_segment_speed_knots or speed
                    blended_speed = (speed + expected_speed) / 2.0
                    segment_speed_knots = blended_speed
                else:
                    # Future segments: use expected speed if available
                    segment_speed_knots = (
                        current_point.expected_segment_speed_knots or speed
                    )

                # Calculate time for this segment (avoid division by zero)
                if segment_speed_knots > 0.5:
                    distance_nm = segment_distance / 1852.0
                    segment_time = (distance_nm / segment_speed_knots) * 3600.0
                    total_eta_seconds += segment_time

            # Return total ETA or None if calculation failed
            if total_eta_seconds > 0:
                return total_eta_seconds

            return None

        except Exception as e:
            logger.debug(f"On-route estimated ETA calculation failed: {e}")
            return None

    def _calculate_on_route_eta(
        self,
        current_lat: float,
        current_lon: float,
        destination_waypoint: "RouteWaypoint",
        active_route: "ParsedRoute",
    ) -> Optional[float]:
        """
        Calculate ETA for a waypoint that is on the active route.

        Uses segment-based speeds from route timing data.
        DEPRECATED: This delegates to estimated mode for backward compatibility.

        Args:
            current_lat: Current latitude
            current_lon: Current longitude
            destination_waypoint: Destination waypoint on the route
            active_route: ParsedRoute with timing data

        Returns:
            ETA in seconds if calculation succeeds, None otherwise
        """
        # Delegate to estimated mode for backward compatibility
        return self._calculate_on_route_eta_estimated(
            current_lat, current_lon, destination_waypoint, active_route
        )

    def _calculate_off_route_eta_with_projection_estimated(
        self,
        current_lat: float,
        current_lon: float,
        poi: POI,
        active_route: "ParsedRoute",
        current_speed_knots: Optional[float] = None,
    ) -> Optional[float]:
        """
        Calculate ETA for off-route POI with speed blending (estimated/in-flight mode).

        Uses the same segment-walking logic as on-route POIs, but walks only
        from current position to the POI's projection point on the route.

        Implements speed blending:
        - Current segment: Blend current speed with expected segment speed
        - Future segments: Use expected segment speeds

        Strategy:
        1. Find nearest route point to current position
        2. Find which route segment contains the projection point
        3. Walk segments from current position to the projection point
        4. Use blended speed for current segment, expected speeds for subsequent segments

        Args:
            current_lat: Current latitude
            current_lon: Current longitude
            poi: POI with projection data (projected_latitude, projected_longitude)
            active_route: ParsedRoute with timing data
            current_speed_knots: Current speed for blending (uses smoothed speed if not provided)

        Returns:
            ETA in seconds if calculation succeeds, None otherwise
        """
        try:
            speed = (
                current_speed_knots
                if current_speed_knots is not None
                else self._smoothed_speed
            )

            # Find nearest route point to current position
            nearest_point_index = 0
            nearest_distance = float("inf")

            for idx, point in enumerate(active_route.points):
                dist = self.calculate_distance(
                    current_lat, current_lon, point.latitude, point.longitude
                )
                if dist < nearest_distance:
                    nearest_distance = dist
                    nearest_point_index = idx

            # Find which route segment contains the projection point
            projection_segment_index = None
            for idx in range(len(active_route.points) - 1):
                p1 = active_route.points[idx]
                p2 = active_route.points[idx + 1]

                # Check if projection point lies on this segment
                dist_to_segment = self._distance_to_line_segment(
                    poi.projected_latitude,
                    poi.projected_longitude,
                    p1.latitude,
                    p1.longitude,
                    p2.latitude,
                    p2.longitude,
                )

                if (
                    dist_to_segment < 1000
                ):  # Within 1km of segment (projection tolerance)
                    projection_segment_index = idx
                    break

            # If we couldn't find the projection segment, fall back to distance/speed
            if projection_segment_index is None:
                return None

            # Calculate remaining distance and time segment by segment with speed blending
            total_eta_seconds = 0.0

            # Walk through segments from nearest point to projection point
            for idx in range(nearest_point_index, projection_segment_index + 1):
                current_point = active_route.points[idx]
                next_point = active_route.points[idx + 1]

                # Calculate segment distance
                segment_distance = self.calculate_distance(
                    current_point.latitude,
                    current_point.longitude,
                    next_point.latitude,
                    next_point.longitude,
                )

                # Determine speed for this segment with blending for current segment
                if idx == nearest_point_index:
                    # Current segment: blend current speed with expected speed
                    expected_speed = current_point.expected_segment_speed_knots or speed
                    blended_speed = (speed + expected_speed) / 2.0
                    segment_speed_knots = blended_speed
                else:
                    # Future segments: use expected speed if available
                    segment_speed_knots = (
                        current_point.expected_segment_speed_knots or speed
                    )

                # Calculate time for this segment (avoid division by zero)
                if segment_speed_knots > 0.5:
                    distance_nm = segment_distance / 1852.0
                    segment_time = (distance_nm / segment_speed_knots) * 3600.0
                    total_eta_seconds += segment_time

            # Return total ETA or None if calculation failed
            if total_eta_seconds > 0:
                return total_eta_seconds

            return None

        except Exception as e:
            logger.debug(
                f"Off-route estimated ETA calculation with projection failed for {poi.name}: {e}"
            )
            return None

    def _calculate_off_route_eta_with_projection(
        self,
        current_lat: float,
        current_lon: float,
        poi: POI,
        active_route: "ParsedRoute",
    ) -> Optional[float]:
        """
        Calculate ETA for a POI that is off-route but has projection data.

        Uses the same segment-walking logic as on-route POIs, but walks only
        from current position to the POI's projection point on the route.

        DEPRECATED: This delegates to estimated mode for backward compatibility.

        Strategy:
        1. Find nearest route point to current position
        2. Find which route segment contains the projection point
        3. Walk segments from current position to the projection point
        4. Use current speed for first segment, expected speeds for subsequent segments

        Args:
            current_lat: Current latitude
            current_lon: Current longitude
            poi: POI with projection data (projected_latitude, projected_longitude)
            active_route: ParsedRoute with timing data

        Returns:
            ETA in seconds if calculation succeeds, None otherwise
        """
        # Delegate to estimated mode for backward compatibility
        return self._calculate_off_route_eta_with_projection_estimated(
            current_lat, current_lon, poi, active_route
        )

    def _distance_to_line_segment(
        self,
        point_lat: float,
        point_lon: float,
        seg_start_lat: float,
        seg_start_lon: float,
        seg_end_lat: float,
        seg_end_lon: float,
    ) -> float:
        """
        Calculate perpendicular distance from a point to a line segment.

        Args:
            point_lat/lon: Point to measure distance from
            seg_start_lat/lon: Start of line segment
            seg_end_lat/lon: End of line segment

        Returns:
            Distance in meters
        """
        # Using simplified haversine-based distance to line segment
        # This is a rough approximation for short segments

        # Distance from point to segment start
        dist_to_start = self.calculate_distance(
            point_lat, point_lon, seg_start_lat, seg_start_lon
        )

        # Distance from point to segment end
        dist_to_end = self.calculate_distance(
            point_lat, point_lon, seg_end_lat, seg_end_lon
        )

        # Distance along segment
        segment_length = self.calculate_distance(
            seg_start_lat, seg_start_lon, seg_end_lat, seg_end_lon
        )

        # If segment is very short, return distance to start
        if segment_length < 1:
            return dist_to_start

        # Use triangle inequality: perpendicular distance is approximate
        # For a point on the segment, sum of distances to ends equals segment length
        # Deviation from this tells us how far off the segment the point is
        max_dist = max(dist_to_start, dist_to_end)
        min_dist = min(dist_to_start, dist_to_end)

        # Perpendicular distance approximation
        if dist_to_start + dist_to_end > segment_length:
            # Point is roughly perpendicular to segment
            perp_dist = (
                dist_to_start**2 + dist_to_end**2 - segment_length**2
            ) / (2 * segment_length)
            return abs(perp_dist)
        else:
            # Point is outside segment bounds
            return min_dist

    def reset(self) -> None:
        """Reset calculator state."""
        self._speed_history.clear()
        self._smoothed_speed = self.default_speed_knots
        self._passed_pois.clear()
        self._last_update_time = None
        logger.info(
            f"ETA calculator reset (smoothing window: {self.smoothing_duration_seconds}s)"
        )

    def get_passed_pois(self) -> set[str]:
        """
        Get set of POI IDs that have been passed.

        Returns:
            Set of passed POI IDs
        """
        return self._passed_pois.copy()

    def clear_passed_pois(self) -> None:
        """Clear the set of passed POIs (useful when route resets)."""
        self._passed_pois.clear()
        logger.info("Cleared passed POIs tracking")

    def get_stats(self) -> dict:
        """
        Get calculator statistics.

        Returns:
            Dictionary with current stats
        """
        # Calculate window coverage (time from oldest to newest sample)
        window_coverage_seconds = 0.0
        if len(self._speed_history) > 1:
            oldest_time = self._speed_history[0][1]
            newest_time = self._speed_history[-1][1]
            window_coverage_seconds = newest_time - oldest_time

        return {
            "smoothed_speed_knots": self._smoothed_speed,
            "speed_samples": len(self._speed_history),
            "smoothing_window_seconds": self.smoothing_duration_seconds,
            "current_window_coverage_seconds": window_coverage_seconds,
            "passed_pois_count": len(self._passed_pois),
            "last_update": (
                self._last_update_time.isoformat() if self._last_update_time else None
            ),
        }
