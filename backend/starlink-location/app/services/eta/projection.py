"""Route-aware ETA projection and calculation with dual-mode support."""

import logging
from typing import Optional, TYPE_CHECKING
from datetime import datetime, timezone

from app.models.poi import POI
from app.models.flight_status import ETAMode, FlightPhase
from app.services.eta.calculator import ETACalculator

if TYPE_CHECKING:
    from app.models.route import ParsedRoute

logger = logging.getLogger(__name__)


class ETAProjection:
    """
    Extends ETACalculator with route-aware projection capabilities.

    Handles:
    - POI metrics calculation with route awareness
    - Anticipated vs Estimated ETA modes
    - On-route and off-route POI projections
    """

    def __init__(self, calculator: ETACalculator):
        """
        Initialize ETA projection handler.

        Args:
            calculator: Base ETACalculator instance
        """
        self.calculator = calculator

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
            flight_phase: Current flight phase

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
            distance = self.calculator.calculate_distance(
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
                    speed_knots
                    if speed_knots is not None
                    else self.calculator.default_speed_knots
                )
                eta = self.calculator.calculate_eta(distance, fallback_speed)

            # Determine if POI has been passed
            passed = distance < self.calculator._poi_distance_threshold_m

            # Track passed POIs
            if passed and poi.id not in self.calculator._passed_pois:
                self.calculator._passed_pois.add(poi.id)
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
                else self.calculator._smoothed_speed
            )

            # Find nearest route point to current position
            nearest_point_index = 0
            nearest_distance = float("inf")

            for idx, point in enumerate(active_route.points):
                dist = self.calculator.calculate_distance(
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
                segment_distance = self.calculator.calculate_distance(
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
                else self.calculator._smoothed_speed
            )

            # Find nearest route point to current position
            nearest_point_index = 0
            nearest_distance = float("inf")

            for idx, point in enumerate(active_route.points):
                dist = self.calculator.calculate_distance(
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
                dist_to_segment = self.calculator._distance_to_line_segment(
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
                segment_distance = self.calculator.calculate_distance(
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
