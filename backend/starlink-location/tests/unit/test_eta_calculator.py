"""Unit tests for ETA calculator with speed smoothing."""

import math
from datetime import datetime, timedelta, timezone

import pytest

from app.models.flight_status import ETAMode, FlightPhase
from app.models.poi import POI
from app.models.route import (
    ParsedRoute,
    RouteMetadata,
    RoutePoint,
    RouteTimingProfile,
    RouteWaypoint,
)
from app.services.eta_calculator import ETACalculator


@pytest.fixture
def eta_calculator():
    """Create an ETA calculator instance."""
    return ETACalculator(smoothing_duration_seconds=120.0, default_speed_knots=150.0)


@pytest.fixture
def sample_pois():
    """Create sample POIs for testing."""
    return [
        POI(id="poi-1", name="POI 1", latitude=40.7128, longitude=-74.0060),
        POI(id="poi-2", name="POI 2", latitude=40.7140, longitude=-74.0060),
        POI(id="poi-3", name="POI 3", latitude=40.7150, longitude=-74.0060),
    ]


@pytest.fixture
def route_with_timing():
    """Create a simple route with timing metadata for route-aware calculations."""
    now = datetime.now(timezone.utc)
    metadata = RouteMetadata(
        name="Test Route",
        description="",
        file_path="routes/test-route.kml",
        imported_at=now,
        point_count=3,
    )
    points = [
        RoutePoint(latitude=0.0, longitude=0.0, sequence=0, expected_segment_speed_knots=180.0),
        RoutePoint(latitude=0.0, longitude=1.0, sequence=1, expected_segment_speed_knots=200.0),
        RoutePoint(latitude=0.0, longitude=2.0, sequence=2, expected_segment_speed_knots=210.0),
    ]
    waypoints = [
        RouteWaypoint(name="WP1", latitude=0.0, longitude=0.0, order=0, expected_arrival_time=now + timedelta(minutes=30)),
        RouteWaypoint(name="WP2", latitude=0.0, longitude=1.0, order=1, expected_arrival_time=now + timedelta(hours=1, minutes=10)),
        RouteWaypoint(name="WP3", latitude=0.0, longitude=2.0, order=2, expected_arrival_time=now + timedelta(hours=2)),
    ]
    timing_profile = RouteTimingProfile(
        departure_time=now + timedelta(minutes=5),
        arrival_time=now + timedelta(hours=3),
        has_timing_data=True,
        segment_count_with_timing=2,
    )
    return ParsedRoute(metadata=metadata, points=points, waypoints=waypoints, timing_profile=timing_profile)


@pytest.fixture
def route_without_timing():
    """Route that lacks timing metadata to verify fallback behaviour."""
    now = datetime.now(timezone.utc)
    metadata = RouteMetadata(
        name="Fallback Route",
        description="",
        file_path="routes/fallback-route.kml",
        imported_at=now,
        point_count=2,
    )
    points = [
        RoutePoint(latitude=0.0, longitude=0.0, sequence=0),
        RoutePoint(latitude=0.0, longitude=1.0, sequence=1),
    ]
    return ParsedRoute(metadata=metadata, points=points, waypoints=[], timing_profile=RouteTimingProfile(has_timing_data=False))


class TestETACalculator:
    """Test suite for ETA calculator."""

    def test_initialization(self, eta_calculator):
        """Test calculator initialization."""
        assert eta_calculator.get_smoothed_speed() == 150.0
        assert len(eta_calculator.get_passed_pois()) == 0

    def test_update_speed_single(self, eta_calculator):
        """Test updating speed with single sample."""
        eta_calculator.update_speed(200.0)

        assert eta_calculator.get_smoothed_speed() == 200.0

    def test_update_speed_rolling_average(self, eta_calculator):
        """Test speed smoothing with rolling average."""
        speeds = [100.0, 150.0, 200.0, 180.0, 170.0]

        for speed in speeds:
            eta_calculator.update_speed(speed)

        # All 5 samples should be included
        smoothed = eta_calculator.get_smoothed_speed()
        expected_average = sum(speeds) / len(speeds)

        assert abs(smoothed - expected_average) < 0.01

    def test_update_speed_window_overflow(self, eta_calculator):
        """Test that window size is maintained."""
        # Add more samples than window size
        for i in range(10):
            eta_calculator.update_speed(100.0 + i * 10)

        # Should only have last 5 samples
        assert eta_calculator.get_smoothed_speed() > 100.0
        assert eta_calculator.get_smoothed_speed() < 200.0

    def test_calculate_distance_same_point(self, eta_calculator):
        """Test distance calculation for same point."""
        distance = eta_calculator.calculate_distance(40.0, -74.0, 40.0, -74.0)

        assert distance == 0.0

    def test_calculate_distance_known_points(self, eta_calculator):
        """Test distance calculation with known points."""
        # NYC to Los Angeles is approximately 3944 km
        nyc_lat, nyc_lon = 40.7128, -74.0060
        la_lat, la_lon = 34.0522, -118.2437

        distance = eta_calculator.calculate_distance(nyc_lat, nyc_lon, la_lat, la_lon)

        # Should be approximately 3944 km (3944000 meters)
        # Allow 1% tolerance for calculation differences
        expected_distance = 3944000
        assert abs(distance - expected_distance) < expected_distance * 0.01

    def test_calculate_distance_symmetry(self, eta_calculator):
        """Test that distance calculation is symmetric."""
        lat1, lon1 = 40.0, -74.0
        lat2, lon2 = 41.0, -75.0

        d1 = eta_calculator.calculate_distance(lat1, lon1, lat2, lon2)
        d2 = eta_calculator.calculate_distance(lat2, lon2, lat1, lon1)

        assert abs(d1 - d2) < 1.0  # Within 1 meter

    def test_calculate_eta_with_speed(self, eta_calculator):
        """Test ETA calculation with provided speed."""
        distance_m = 10000  # 10 km
        speed_knots = 100.0

        eta = eta_calculator.calculate_eta(distance_m, speed_knots)

        # 10 km = 5.39957 nautical miles
        # At 100 knots: 5.39957 / 100 = 0.0539957 hours = 194.3 seconds
        assert eta > 100
        assert eta < 300

    def test_calculate_eta_with_smoothed_speed(self, eta_calculator):
        """Test ETA calculation using smoothed speed."""
        eta_calculator.update_speed(100.0)

        distance_m = 10000
        eta = eta_calculator.calculate_eta(distance_m)

        assert eta > 100
        assert eta < 300

    def test_calculate_eta_zero_speed(self, eta_calculator):
        """Test ETA with zero speed."""
        eta = eta_calculator.calculate_eta(10000, speed_knots=0.0)

        assert eta == -1.0

    def test_calculate_eta_negative_speed(self, eta_calculator):
        """Test ETA with negative speed."""
        eta = eta_calculator.calculate_eta(10000, speed_knots=-100.0)

        assert eta == -1.0

    def test_calculate_eta_no_speed_data(self, eta_calculator):
        """Test ETA when no speed data has been provided."""
        eta_calculator._smoothed_speed = 0.0
        eta = eta_calculator.calculate_eta(10000)

        assert eta == -1.0

    def test_calculate_poi_metrics(self, eta_calculator, sample_pois):
        """Test calculating metrics for multiple POIs."""
        current_lat, current_lon = 40.7128, -74.0060
        eta_calculator.update_speed(100.0)

        metrics = eta_calculator.calculate_poi_metrics(
            current_lat,
            current_lon,
            sample_pois,
            100.0,
            eta_mode=ETAMode.ANTICIPATED,
            flight_phase=FlightPhase.PRE_DEPARTURE,
        )

        assert len(metrics) == 3
        assert "poi-1" in metrics
        assert "poi-2" in metrics
        assert "poi-3" in metrics

        # All metrics should have required keys
        for poi_id, metric in metrics.items():
            assert "distance_meters" in metric
            assert "eta_seconds" in metric
            assert "passed" in metric
            assert "poi_name" in metric
            assert metric["eta_type"] == ETAMode.ANTICIPATED.value
            assert metric["flight_phase"] == FlightPhase.PRE_DEPARTURE.value
            assert metric["is_pre_departure"] is True

    def test_calculate_poi_metrics_defaults(self, eta_calculator, sample_pois):
        """Ensure optional metadata defaults when flight phase not provided."""
        metrics = eta_calculator.calculate_poi_metrics(40.7128, -74.0060, sample_pois)

        for metric in metrics.values():
            assert metric["eta_type"] == ETAMode.ESTIMATED.value
            assert metric["flight_phase"] is None
            assert metric["is_pre_departure"] is False

    def test_poi_metrics_distance_ordering(self, eta_calculator, sample_pois):
        """Test that POI distances are correctly calculated."""
        current_lat, current_lon = 40.7128, -74.0060

        metrics = eta_calculator.calculate_poi_metrics(current_lat, current_lon, sample_pois)

        # POI 1 is at current position (distance ~0)
        assert metrics["poi-1"]["distance_meters"] < 1000  # < 1km

        # POI 2 is north of current position
        assert metrics["poi-2"]["distance_meters"] > metrics["poi-1"]["distance_meters"]

        # POI 3 is further north
        assert metrics["poi-3"]["distance_meters"] > metrics["poi-2"]["distance_meters"]

    def test_passed_poi_detection(self, eta_calculator):
        """Test that POIs within threshold are marked as passed."""
        poi = POI(id="poi-1", name="Test POI", latitude=40.7128, longitude=-74.0060)

        # Current position very close to POI
        metrics = eta_calculator.calculate_poi_metrics(40.71280001, -74.00600001, [poi])

        assert metrics["poi-1"]["passed"] is True
        assert "poi-1" in eta_calculator.get_passed_pois()

    def test_passed_poi_tracking(self, eta_calculator, sample_pois):
        """Test tracking of passed POIs across multiple updates."""
        # First update - move to near POI 1
        metrics1 = eta_calculator.calculate_poi_metrics(40.7128, -74.0060, sample_pois)
        assert metrics1["poi-1"]["passed"] is True

        # Check that POI 1 is tracked as passed
        passed = eta_calculator.get_passed_pois()
        assert "poi-1" in passed

        # Second update - move away
        metrics2 = eta_calculator.calculate_poi_metrics(40.7140, -74.0060, sample_pois)

        # POI 1 should still be in passed set
        assert "poi-1" in eta_calculator.get_passed_pois()

    def test_clear_passed_pois(self, eta_calculator, sample_pois):
        """Test clearing passed POIs."""
        # Mark some POIs as passed
        eta_calculator.calculate_poi_metrics(40.7128, -74.0060, sample_pois)
        assert len(eta_calculator.get_passed_pois()) > 0

        # Clear
        eta_calculator.clear_passed_pois()
        assert len(eta_calculator.get_passed_pois()) == 0

    def test_reset(self, eta_calculator):
        """Test calculator reset."""
        eta_calculator.update_speed(200.0)
        eta_calculator._passed_pois.add("poi-1")

        eta_calculator.reset()

        assert eta_calculator.get_smoothed_speed() == 150.0
        assert len(eta_calculator.get_passed_pois()) == 0

    def test_get_stats(self, eta_calculator):
        """Test getting calculator statistics."""
        eta_calculator.update_speed(100.0)
        eta_calculator.update_speed(150.0)

        stats = eta_calculator.get_stats()

        assert "smoothed_speed_knots" in stats
        assert "speed_samples" in stats
        assert "passed_pois_count" in stats
        assert "last_update" in stats
        assert stats["speed_samples"] == 2

    def test_eta_consistency(self, eta_calculator):
        """Test that ETA is consistent for same inputs."""
        distance_m = 50000
        speed_knots = 150.0

        eta1 = eta_calculator.calculate_eta(distance_m, speed_knots)
        eta2 = eta_calculator.calculate_eta(distance_m, speed_knots)

        assert eta1 == eta2

    def test_speed_smoothing_consistency(self, eta_calculator):
        """Test that speed smoothing is stable."""
        # Add same speed multiple times
        for _ in range(10):
            eta_calculator.update_speed(120.0)

        assert eta_calculator.get_smoothed_speed() == 120.0

    def test_eta_with_very_small_distance(self, eta_calculator):
        """Test ETA calculation with very small distance."""
        eta = eta_calculator.calculate_eta(1.0, speed_knots=100.0)  # 1 meter

        # Should be very small but positive
        assert eta > 0
        assert eta < 1

    def test_eta_with_very_large_distance(self, eta_calculator):
        """Test ETA calculation with very large distance."""
        distance_m = 40000000  # 40,000 km
        eta = eta_calculator.calculate_eta(distance_m, speed_knots=150.0)

        # Should be large positive number (in seconds)
        # 40,000 km = 21,599 nautical miles / 150 knots = 144 hours = ~518,400 seconds
        assert eta > 100000

    def test_multiple_speed_updates_convergence(self, eta_calculator):
        """Test that speed converges with repeated updates."""
        speeds = [100.0, 110.0, 120.0, 130.0, 140.0, 140.0, 140.0, 140.0]

        for speed in speeds:
            eta_calculator.update_speed(speed)

        # Should converge toward recent values
        # Note: In tight test loops with fast execution (microseconds between updates),
        # the time-based smoothing window may not capture all values equally.
        # The smoothed speed should be reasonably close to the recent values.
        smoothed = eta_calculator.get_smoothed_speed()
        assert 120.0 <= smoothed <= 140.0  # Should be in range of recent values

    def test_route_aware_eta_estimated_blends_speed(self, eta_calculator, route_with_timing):
        """Estimated mode should blend current speed with segment speed for route waypoints."""
        current_lat, current_lon = 0.0, 0.0
        poi = POI(
            id="wp2",
            name="WP2",
            latitude=0.0,
            longitude=1.0,
            route_id=route_with_timing.metadata.file_path,
        )

        # Provide an explicit current speed to blend with expected segment speed
        current_speed = 150.0
        metrics = eta_calculator.calculate_poi_metrics(
            current_lat,
            current_lon,
            [poi],
            speed_knots=current_speed,
            active_route=route_with_timing,
            eta_mode=ETAMode.ESTIMATED,
            flight_phase=FlightPhase.IN_FLIGHT,
        )

        assert "wp2" in metrics
        eta_seconds = metrics["wp2"]["eta_seconds"]
        assert eta_seconds > 0
        assert metrics["wp2"]["eta_type"] == ETAMode.ESTIMATED.value

        # Expected time is based on blended speed between current and segment speed
        segment_distance = eta_calculator.calculate_distance(0.0, 0.0, 0.0, 1.0)
        expected_speed = (current_speed + route_with_timing.points[0].expected_segment_speed_knots) / 2.0
        expected_eta = (segment_distance / 1852.0) / expected_speed * 3600.0
        assert eta_seconds == pytest.approx(expected_eta, rel=0.05)

    def test_route_aware_eta_anticipated_uses_waypoint_times(self, eta_calculator, route_with_timing):
        """Anticipated mode should honour planned arrival timestamps."""
        current_lat, current_lon = 0.0, 0.0
        poi = POI(
            id="wp2",
            name="WP2",
            latitude=0.0,
            longitude=1.0,
            route_id=route_with_timing.metadata.file_path,
        )

        before_call = datetime.now(timezone.utc)
        metrics = eta_calculator.calculate_poi_metrics(
            current_lat,
            current_lon,
            [poi],
            active_route=route_with_timing,
            eta_mode=ETAMode.ANTICIPATED,
            flight_phase=FlightPhase.PRE_DEPARTURE,
        )
        after_call = datetime.now(timezone.utc)

        assert "wp2" in metrics
        eta_seconds = metrics["wp2"]["eta_seconds"]
        assert eta_seconds > 0
        assert metrics["wp2"]["eta_type"] == ETAMode.ANTICIPATED.value
        assert metrics["wp2"]["is_pre_departure"] is True

        expected_arrival = route_with_timing.waypoints[1].expected_arrival_time
        upper_bound = (expected_arrival - before_call).total_seconds()
        lower_bound = (expected_arrival - after_call).total_seconds()
        assert lower_bound <= eta_seconds <= upper_bound

    def test_route_without_timing_falls_back_to_distance(self, eta_calculator, route_without_timing):
        """When no timing data is present, calculator should fall back to distance/speed ETA."""
        current_lat, current_lon = 0.0, 0.0
        poi = POI(
            id="fallback",
            name="Fallback",
            latitude=0.0,
            longitude=1.0,
            route_id=route_without_timing.metadata.file_path,
        )
        speed_knots = 160.0

        metrics = eta_calculator.calculate_poi_metrics(
            current_lat,
            current_lon,
            [poi],
            speed_knots=speed_knots,
            active_route=route_without_timing,
            eta_mode=ETAMode.ESTIMATED,
            flight_phase=FlightPhase.IN_FLIGHT,
        )

        eta_seconds = metrics["fallback"]["eta_seconds"]
        fallback_eta = eta_calculator.calculate_eta(
            eta_calculator.calculate_distance(0.0, 0.0, 0.0, 1.0),
            speed_knots=speed_knots,
        )
        assert eta_seconds == pytest.approx(fallback_eta, rel=0.01)

    def test_eta_mode_metadata_switches_with_phase(self, eta_calculator, sample_pois):
        """`eta_type` and `is_pre_departure` metadata should reflect supplied mode/phase."""
        current_lat, current_lon = 40.7128, -74.0060

        anticipated = eta_calculator.calculate_poi_metrics(
            current_lat,
            current_lon,
            sample_pois,
            eta_mode=ETAMode.ANTICIPATED,
            flight_phase=FlightPhase.PRE_DEPARTURE,
        )
        estimated = eta_calculator.calculate_poi_metrics(
            current_lat,
            current_lon,
            sample_pois,
            eta_mode=ETAMode.ESTIMATED,
            flight_phase=FlightPhase.IN_FLIGHT,
        )

        for poi_id in anticipated:
            assert anticipated[poi_id]["eta_type"] == ETAMode.ANTICIPATED.value
            assert anticipated[poi_id]["is_pre_departure"] is True
            assert anticipated[poi_id]["flight_phase"] == FlightPhase.PRE_DEPARTURE.value

        for poi_id in estimated:
            assert estimated[poi_id]["eta_type"] == ETAMode.ESTIMATED.value
            assert estimated[poi_id]["is_pre_departure"] is False
            assert estimated[poi_id]["flight_phase"] == FlightPhase.IN_FLIGHT.value

    def test_route_projection_in_anticipated_mode(self, eta_calculator, route_with_timing):
        """Off-route POIs with projections should reuse waypoint arrival time in anticipated mode."""
        projection_index = 2
        projected_waypoint = route_with_timing.waypoints[projection_index]
        poi = POI(
            id="projected",
            name="Projected POI",
            latitude=5.0,  # arbitrary off-route point
            longitude=5.0,
            projected_latitude=projected_waypoint.latitude,
            projected_longitude=projected_waypoint.longitude,
            projected_waypoint_index=projection_index,
            projected_route_progress=75.0,
            route_id=route_with_timing.metadata.file_path,
        )

        before_call = datetime.now(timezone.utc)
        metrics = eta_calculator.calculate_poi_metrics(
            current_lat=0.0,
            current_lon=0.0,
            pois=[poi],
            active_route=route_with_timing,
            eta_mode=ETAMode.ANTICIPATED,
            flight_phase=FlightPhase.PRE_DEPARTURE,
        )
        after_call = datetime.now(timezone.utc)

        eta_seconds = metrics["projected"]["eta_seconds"]
        expected_arrival = projected_waypoint.expected_arrival_time
        upper_bound = (expected_arrival - before_call).total_seconds()
        lower_bound = (expected_arrival - after_call).total_seconds()
        assert lower_bound <= eta_seconds <= upper_bound
        assert metrics["projected"]["eta_type"] == ETAMode.ANTICIPATED.value
        assert metrics["projected"]["is_pre_departure"] is True

    def test_route_projection_estimated_blends_speed(self, eta_calculator, route_with_timing):
        """Projection path in estimated mode should fall back to route-aware blending."""
        poi = POI(
            id="projected",
            name="Projected",
            latitude=10.0,
            longitude=10.0,
            projected_latitude=route_with_timing.points[1].latitude,
            projected_longitude=route_with_timing.points[1].longitude,
            projected_waypoint_index=1,
            projected_route_progress=50.0,
            route_id=route_with_timing.metadata.file_path,
        )

        current_speed = 155.0
        metrics = eta_calculator.calculate_poi_metrics(
            current_lat=0.0,
            current_lon=0.5,
            pois=[poi],
            speed_knots=current_speed,
            active_route=route_with_timing,
            eta_mode=ETAMode.ESTIMATED,
            flight_phase=FlightPhase.IN_FLIGHT,
        )

        eta_seconds = metrics["projected"]["eta_seconds"]
        assert eta_seconds > 0
        assert metrics["projected"]["eta_type"] == ETAMode.ESTIMATED.value

        # Since projection lands near the second segment, ensure ETA is shorter than pure distance fallback.
        fallback_eta = eta_calculator.calculate_eta(
            eta_calculator.calculate_distance(0.0, 0.5, route_with_timing.points[2].latitude, route_with_timing.points[2].longitude),
            speed_knots=current_speed,
        )
        assert eta_seconds < fallback_eta

    def test_poi_metrics_empty_list(self, eta_calculator):
        """Test calculating metrics with empty POI list."""
        metrics = eta_calculator.calculate_poi_metrics(40.0, -74.0, [])

        assert len(metrics) == 0
