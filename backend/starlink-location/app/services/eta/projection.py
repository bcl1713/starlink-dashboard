"""Route-aware ETA projection and calculation with dual-mode support."""

# FR-004: File exceeds 300 lines (500 lines) because ETA projection bridges
# flight phase detection, route geometry, timing calculations, and mode switching.
# Refactoring would split related concerns across modules losing coherence.
# Deferred to v0.4.0.

import logging
from datetime import datetime, timezone
from math import isfinite
from typing import TYPE_CHECKING, Optional

from app.models.flight_status import ETAMode, FlightPhase
from app.models.poi import POI
from app.services.eta.calculator import ETACalculator
from app.services.route_eta.calculator import RouteETACalculator

if TYPE_CHECKING:
    from app.models.route import ParsedRoute, RouteWaypoint

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
        speed_knots: float | None = None,
        active_route: Optional["ParsedRoute"] = None,
        eta_mode: ETAMode = ETAMode.ESTIMATED,
        flight_phase: FlightPhase | None = None,
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
        current_speed_knots: float | None = None,
    ) -> float | None:
        """
        Calculate ETA using segment-based speeds with speed blending (estimated/in-flight mode).

        Implements intelligent speed calculation:
        - Current segment: Blend current speed with expected segment speed
          Formula: blended_speed = (current_speed + expected_speed) / 2
        - Future segments: Use expected segment speeds from route timing data
        - All POI types: Use their destination projection with the same logic

        Handles two cases:
        1. POI has stored destination projection data
        2. Legacy POI matches a named waypoint, projected by the same engine

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

        # A stored destination projection is authoritative, even when its name
        # matches a waypoint. Reject incomplete geometry rather than changing
        # destinations. Progress alone also appears on legacy named POIs.
        if any(
            value is not None
            for value in (
                poi.projected_latitude,
                poi.projected_longitude,
                poi.projected_waypoint_index,
            )
        ):
            return self._calculate_projected_eta_estimated(
                current_lat, current_lon, poi, active_route, current_speed_knots
            )

        for waypoint in active_route.waypoints:
            if waypoint.name and waypoint.name.upper() == poi.name.upper():
                return self._calculate_on_route_eta_estimated(
                    current_lat,
                    current_lon,
                    waypoint,
                    active_route,
                    current_speed_knots,
                )

        return None

    def _calculate_route_aware_eta_anticipated(
        self,
        current_lat: float,
        current_lon: float,
        poi: POI,
        active_route: "ParsedRoute",
    ) -> float | None:
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
        timing_profile = active_route.timing_profile
        if not timing_profile or not timing_profile.has_timing_data:
            return None

        departure_time = timing_profile.departure_time
        if not departure_time:
            return None

        try:
            current_time = datetime.now(timezone.utc)

            def anticipated_eta_for_waypoint(waypoint: "RouteWaypoint") -> float | None:
                if not waypoint.expected_arrival_time:
                    return None

                planned_duration = waypoint.expected_arrival_time - departure_time
                if planned_duration.total_seconds() < 0:
                    return None

                if departure_time > current_time:
                    return (
                        waypoint.expected_arrival_time - current_time
                    ).total_seconds()

                return planned_duration.total_seconds()

            # First, try to find matching waypoint on route by name.
            # This handles explicitly named waypoints in the KML.
            for waypoint in active_route.waypoints:
                if waypoint.name and waypoint.name.upper() == poi.name.upper():
                    return anticipated_eta_for_waypoint(waypoint)

            # Second, try to use POI's projected waypoint index.
            # This is set by route-aware projection for off-route POIs.
            if poi.projected_waypoint_index is not None:
                waypoint_idx = poi.projected_waypoint_index
                if 0 <= waypoint_idx < len(active_route.waypoints):
                    return anticipated_eta_for_waypoint(
                        active_route.waypoints[waypoint_idx]
                    )

            # If no waypoint found, return None to fall back to distance/speed
            return None

        except (
            RuntimeError,
            ValueError,
            OSError,
            KeyError,
            TypeError,
            AttributeError,
            LookupError,
            ConnectionError,
            TimeoutError,
            ImportError,
            EOFError,
        ) as e:
            logger.debug(f"Anticipated ETA calculation failed for {poi.name}: {e}")
            return None

    def _calculate_on_route_eta_estimated(
        self,
        current_lat: float,
        current_lon: float,
        destination_waypoint: "RouteWaypoint",
        active_route: "ParsedRoute",
        current_speed_knots: float | None = None,
    ) -> float | None:
        """Normalize a legacy named waypoint into the shared destination contract."""
        try:
            latitude = destination_waypoint.latitude
            longitude = destination_waypoint.longitude
            if (
                not isfinite(latitude)
                or not isfinite(longitude)
                or not -90 <= latitude <= 90
                or not -180 <= longitude <= 180
            ):
                return None
            projection = RouteETACalculator(active_route).project_poi_to_route(
                latitude, longitude
            )
            destination = POI(
                id="route-waypoint",
                name=destination_waypoint.name,
                latitude=latitude,
                longitude=longitude,
                projected_latitude=projection["projected_lat"],
                projected_longitude=projection["projected_lon"],
                projected_waypoint_index=projection["projected_waypoint_index"],
                projected_route_progress=projection["projected_route_progress"],
            )
            return self._calculate_projected_eta_estimated(
                current_lat, current_lon, destination, active_route, current_speed_knots
            )
        except (ValueError, TypeError, AttributeError, LookupError) as exc:
            logger.debug("Named waypoint ETA projection failed: %s", exc)
            return None

    def _calculate_off_route_eta_with_projection_estimated(
        self,
        current_lat: float,
        current_lon: float,
        poi: POI,
        active_route: "ParsedRoute",
        current_speed_knots: float | None = None,
    ) -> float | None:
        """Compatibility entry point for callers with a projected destination."""
        return self._calculate_projected_eta_estimated(
            current_lat, current_lon, poi, active_route, current_speed_knots
        )

    def _calculate_projected_eta_estimated(
        self,
        current_lat: float,
        current_lon: float,
        poi: POI,
        active_route: "ParsedRoute",
        current_speed_knots: float | None = None,
    ) -> float | None:
        """Walk remaining route segments for every POI kind and waypoint name.

        Project the current position continuously and stop at the destination's
        projection. Blend measured speed with the end point's planned speed for
        the first remaining segment; use planned speeds for future segments.
        """
        try:
            speed = (
                current_speed_knots
                if current_speed_knots is not None
                else self.calculator._smoothed_speed
            )
            projection_latitude = poi.projected_latitude
            projection_longitude = poi.projected_longitude
            projection_segment_index = poi.projected_waypoint_index
            projection_progress = poi.projected_route_progress

            if (
                projection_latitude is None
                or projection_longitude is None
                or projection_segment_index is None
                or projection_progress is None
                or not all(
                    isfinite(value)
                    for value in (
                        current_lat,
                        current_lon,
                        speed,
                        projection_latitude,
                        projection_longitude,
                        projection_progress,
                    )
                )
                or not -90 <= current_lat <= 90
                or not -180 <= current_lon <= 180
                or not -90 <= projection_latitude <= 90
                or not -180 <= projection_longitude <= 180
                or not 0 <= projection_progress <= 100
                or speed <= 0.5
                or not 0 <= projection_segment_index < len(active_route.points) - 1
            ):
                return None

            current_projection = RouteETACalculator(active_route).project_poi_to_route(
                current_lat, current_lon
            )
            current_segment_index = current_projection["projected_waypoint_index"]
            if (
                current_projection["projected_route_progress"] >= projection_progress
                or current_segment_index > projection_segment_index
            ):
                return None

            total_eta_seconds = 0.0
            first_remaining_segment = True
            for idx in range(current_segment_index, projection_segment_index + 1):
                current_point = active_route.points[idx]
                segment_timing_point = active_route.points[idx + 1]
                if idx == projection_segment_index:
                    segment_end_latitude = projection_latitude
                    segment_end_longitude = projection_longitude
                else:
                    segment_end_latitude = segment_timing_point.latitude
                    segment_end_longitude = segment_timing_point.longitude
                segment_distance = self.calculator.calculate_distance(
                    (
                        current_projection["projected_lat"]
                        if idx == current_segment_index
                        else current_point.latitude
                    ),
                    (
                        current_projection["projected_lon"]
                        if idx == current_segment_index
                        else current_point.longitude
                    ),
                    segment_end_latitude,
                    segment_end_longitude,
                )
                if segment_distance <= 0.000001:
                    continue
                expected_speed = (
                    segment_timing_point.expected_segment_speed_knots or speed
                )
                segment_speed_knots = (
                    (speed + expected_speed) / 2.0
                    if first_remaining_segment
                    else expected_speed
                )
                if not isfinite(segment_speed_knots) or segment_speed_knots <= 0.5:
                    return None
                total_eta_seconds += (
                    segment_distance / 1852.0 / segment_speed_knots * 3600.0
                )
                first_remaining_segment = False

            return total_eta_seconds if total_eta_seconds > 0 else None

        except (
            RuntimeError,
            ValueError,
            OSError,
            KeyError,
            TypeError,
            AttributeError,
            LookupError,
            ConnectionError,
            TimeoutError,
            ImportError,
            EOFError,
        ) as e:
            logger.debug(
                f"Projected estimated ETA calculation failed for {poi.name}: {e}"
            )
            return None
