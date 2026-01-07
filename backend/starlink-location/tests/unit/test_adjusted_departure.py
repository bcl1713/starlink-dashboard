"""Unit tests for adjusted departure time functionality."""

import pytest
from datetime import datetime, timezone, timedelta

from app.mission.models import MissionLeg, TransportConfig
from app.mission.timeline_builder.calculator import (
    derive_mission_window,
    TimelineComputationError,
)
from app.mission.validation import (
    validate_adjusted_departure_time,
)
from app.models.route import ParsedRoute, RoutePoint, RouteTimingProfile, RouteMetadata


class TestMissionLegTimeOffset:
    """Tests for MissionLeg.get_time_offset_seconds() method."""

    def test_no_adjustment_returns_none(self):
        """When adjusted_departure_time is None, get_time_offset_seconds returns None."""
        leg = MissionLeg(
            id="test-leg",
            name="Test Leg",
            route_id="test-route",
            transports=TransportConfig(initial_x_satellite_id="X-1"),
            adjusted_departure_time=None,
        )

        original = datetime(2025, 10, 27, 16, 45, 0, tzinfo=timezone.utc)
        assert leg.get_time_offset_seconds(original) is None

    def test_positive_offset(self):
        """Positive offset (departure delayed by 40 minutes)."""
        original = datetime(2025, 10, 27, 16, 45, 0, tzinfo=timezone.utc)
        adjusted = datetime(
            2025, 10, 27, 17, 25, 0, tzinfo=timezone.utc
        )  # 40 minutes later

        leg = MissionLeg(
            id="test-leg",
            name="Test Leg",
            route_id="test-route",
            transports=TransportConfig(initial_x_satellite_id="X-1"),
            adjusted_departure_time=adjusted,
        )

        offset = leg.get_time_offset_seconds(original)
        assert offset == 2400.0  # 40 minutes = 2400 seconds

    def test_negative_offset(self):
        """Negative offset (departure moved 40 minutes earlier)."""
        original = datetime(2025, 10, 27, 16, 45, 0, tzinfo=timezone.utc)
        adjusted = datetime(
            2025, 10, 27, 16, 5, 0, tzinfo=timezone.utc
        )  # 40 minutes earlier

        leg = MissionLeg(
            id="test-leg",
            name="Test Leg",
            route_id="test-route",
            transports=TransportConfig(initial_x_satellite_id="X-1"),
            adjusted_departure_time=adjusted,
        )

        offset = leg.get_time_offset_seconds(original)
        assert offset == -2400.0  # -40 minutes = -2400 seconds

    def test_large_positive_offset(self):
        """Large positive offset (9 hours later)."""
        original = datetime(2025, 10, 27, 16, 45, 0, tzinfo=timezone.utc)
        adjusted = datetime(
            2025, 10, 28, 1, 45, 0, tzinfo=timezone.utc
        )  # 9 hours later

        leg = MissionLeg(
            id="test-leg",
            name="Test Leg",
            route_id="test-route",
            transports=TransportConfig(initial_x_satellite_id="X-1"),
            adjusted_departure_time=adjusted,
        )

        offset = leg.get_time_offset_seconds(original)
        assert offset == 32400.0  # 9 hours = 32400 seconds

    def test_large_negative_offset(self):
        """Large negative offset (9 hours earlier)."""
        original = datetime(2025, 10, 27, 16, 45, 0, tzinfo=timezone.utc)
        adjusted = datetime(
            2025, 10, 27, 7, 45, 0, tzinfo=timezone.utc
        )  # 9 hours earlier

        leg = MissionLeg(
            id="test-leg",
            name="Test Leg",
            route_id="test-route",
            transports=TransportConfig(initial_x_satellite_id="X-1"),
            adjusted_departure_time=adjusted,
        )

        offset = leg.get_time_offset_seconds(original)
        assert offset == -32400.0  # -9 hours = -32400 seconds


class TestDeriveMissionWindow:
    """Tests for derive_mission_window with adjusted departure times."""

    def _create_test_route(
        self,
        departure: datetime,
        arrival: datetime,
    ) -> ParsedRoute:
        """Helper to create a test route with timing."""
        return ParsedRoute(
            metadata=RouteMetadata(
                name="Test Route",
                file_path="test.kml",
                point_count=2,
            ),
            timing_profile=RouteTimingProfile(
                departure_time=departure,
                arrival_time=arrival,
            ),
            points=[
                RoutePoint(
                    latitude=35.0,
                    longitude=-120.0,
                    altitude=10000.0,
                    expected_arrival_time=departure,
                ),
                RoutePoint(
                    latitude=36.0,
                    longitude=-121.0,
                    altitude=10000.0,
                    expected_arrival_time=arrival,
                ),
            ],
            waypoints=[],
        )

    def test_no_adjustment(self):
        """Without adjustment, returns original times from route."""
        departure = datetime(2025, 10, 27, 16, 45, 0, tzinfo=timezone.utc)
        arrival = datetime(2025, 10, 27, 22, 15, 0, tzinfo=timezone.utc)
        route = self._create_test_route(departure, arrival)

        start, end = derive_mission_window(route, adjusted_departure_time=None)

        assert start == departure
        assert end == arrival

    def test_positive_adjustment(self):
        """Positive adjustment (40 minutes later) shifts both start and end."""
        original_departure = datetime(2025, 10, 27, 16, 45, 0, tzinfo=timezone.utc)
        original_arrival = datetime(2025, 10, 27, 22, 15, 0, tzinfo=timezone.utc)
        adjusted_departure = datetime(
            2025, 10, 27, 17, 25, 0, tzinfo=timezone.utc
        )  # 40 min later

        route = self._create_test_route(original_departure, original_arrival)
        start, end = derive_mission_window(
            route, adjusted_departure_time=adjusted_departure
        )

        # Both should be shifted by 40 minutes
        assert start == adjusted_departure
        assert end == original_arrival + timedelta(minutes=40)

    def test_negative_adjustment(self):
        """Negative adjustment (40 minutes earlier) shifts both start and end."""
        original_departure = datetime(2025, 10, 27, 16, 45, 0, tzinfo=timezone.utc)
        original_arrival = datetime(2025, 10, 27, 22, 15, 0, tzinfo=timezone.utc)
        adjusted_departure = datetime(
            2025, 10, 27, 16, 5, 0, tzinfo=timezone.utc
        )  # 40 min earlier

        route = self._create_test_route(original_departure, original_arrival)
        start, end = derive_mission_window(
            route, adjusted_departure_time=adjusted_departure
        )

        # Both should be shifted by -40 minutes
        assert start == adjusted_departure
        assert end == original_arrival - timedelta(minutes=40)

    def test_preserves_duration(self):
        """Adjustment preserves the duration of the mission."""
        original_departure = datetime(2025, 10, 27, 16, 45, 0, tzinfo=timezone.utc)
        original_arrival = datetime(2025, 10, 27, 22, 15, 0, tzinfo=timezone.utc)
        original_duration = (original_arrival - original_departure).total_seconds()

        adjusted_departure = datetime(
            2025, 10, 27, 18, 0, 0, tzinfo=timezone.utc
        )  # 75 min later

        route = self._create_test_route(original_departure, original_arrival)
        start, end = derive_mission_window(
            route, adjusted_departure_time=adjusted_departure
        )

        adjusted_duration = (end - start).total_seconds()
        assert adjusted_duration == original_duration

    def test_large_offset(self):
        """Large offset (10 hours) is allowed and applied correctly."""
        original_departure = datetime(2025, 10, 27, 16, 45, 0, tzinfo=timezone.utc)
        original_arrival = datetime(2025, 10, 27, 22, 15, 0, tzinfo=timezone.utc)
        adjusted_departure = datetime(
            2025, 10, 28, 2, 45, 0, tzinfo=timezone.utc
        )  # 10 hours later

        route = self._create_test_route(original_departure, original_arrival)
        start, end = derive_mission_window(
            route, adjusted_departure_time=adjusted_departure
        )

        assert start == adjusted_departure
        assert end == original_arrival + timedelta(hours=10)

    def test_missing_timing_profile_raises_error(self):
        """Route without timing profile raises TimelineComputationError."""
        route = ParsedRoute(
            metadata=RouteMetadata(
                name="Test Route",
                file_path="test.kml",
                point_count=0,
            ),
            timing_profile=None,
            points=[],
            waypoints=[],
        )

        with pytest.raises(TimelineComputationError, match="Route timing data missing"):
            derive_mission_window(route, adjusted_departure_time=None)


class TestValidateAdjustedDepartureTime:
    """Tests for validate_adjusted_departure_time function."""

    def test_no_warning_for_small_offset(self):
        """Offset within threshold (< 8 hours) produces no warnings."""
        original = datetime(2025, 10, 27, 16, 45, 0, tzinfo=timezone.utc)
        adjusted = datetime(
            2025, 10, 27, 18, 0, 0, tzinfo=timezone.utc
        )  # 1.25 hours later

        warnings = validate_adjusted_departure_time(adjusted, original)
        assert warnings == []

    def test_no_warning_at_threshold(self):
        """Offset exactly at threshold (8 hours) produces no warnings."""
        original = datetime(2025, 10, 27, 16, 45, 0, tzinfo=timezone.utc)
        adjusted = datetime(
            2025, 10, 28, 0, 45, 0, tzinfo=timezone.utc
        )  # exactly 8 hours later

        warnings = validate_adjusted_departure_time(adjusted, original)
        assert warnings == []

    def test_warning_for_large_positive_offset(self):
        """Offset exceeding threshold (> 8 hours later) produces warning."""
        original = datetime(2025, 10, 27, 16, 45, 0, tzinfo=timezone.utc)
        adjusted = datetime(
            2025, 10, 28, 2, 0, 0, tzinfo=timezone.utc
        )  # 9.25 hours later

        warnings = validate_adjusted_departure_time(adjusted, original)

        assert len(warnings) == 1
        assert "Large time shift detected" in warnings[0]
        assert "9.2 hours later" in warnings[0]
        assert "Consider requesting new route" in warnings[0]

    def test_warning_for_large_negative_offset(self):
        """Offset exceeding threshold (> 8 hours earlier) produces warning."""
        original = datetime(2025, 10, 27, 16, 45, 0, tzinfo=timezone.utc)
        adjusted = datetime(
            2025, 10, 27, 6, 0, 0, tzinfo=timezone.utc
        )  # 10.75 hours earlier

        warnings = validate_adjusted_departure_time(adjusted, original)

        assert len(warnings) == 1
        assert "Large time shift detected" in warnings[0]
        assert "10.8 hours earlier" in warnings[0]
        assert "Consider requesting new route" in warnings[0]

    def test_warning_threshold_boundary(self):
        """Offset just beyond threshold triggers warning."""
        original = datetime(2025, 10, 27, 16, 45, 0, tzinfo=timezone.utc)
        # 8 hours + 1 minute = 481 minutes (just over 480 minute threshold)
        adjusted = datetime(2025, 10, 28, 0, 46, 0, tzinfo=timezone.utc)

        warnings = validate_adjusted_departure_time(adjusted, original)

        assert len(warnings) == 1
        assert "Large time shift detected" in warnings[0]

    def test_no_exception_raised(self):
        """Validation never raises exceptions, only returns warnings."""
        original = datetime(2025, 10, 27, 16, 45, 0, tzinfo=timezone.utc)
        adjusted = datetime(
            2025, 10, 30, 16, 45, 0, tzinfo=timezone.utc
        )  # 3 days later

        # Should not raise any exception
        warnings = validate_adjusted_departure_time(adjusted, original)

        assert len(warnings) == 1  # Warning present but no exception

    def test_zero_offset(self):
        """Zero offset (same time) produces no warnings."""
        original = datetime(2025, 10, 27, 16, 45, 0, tzinfo=timezone.utc)
        adjusted = datetime(2025, 10, 27, 16, 45, 0, tzinfo=timezone.utc)

        warnings = validate_adjusted_departure_time(adjusted, original)
        assert warnings == []
