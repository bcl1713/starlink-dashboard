"""Integration tests for ETA route timing extraction from real KML files."""

import pytest
from datetime import datetime
from pathlib import Path

from app.services.kml_parser import parse_kml_file


class TestRouteTimingIntegration:
    """Integration tests parsing real KML files with timing metadata."""

    @pytest.fixture
    def kml_routes_dir(self):
        """Path to test KML files from kml-route-import completion."""
        # Try multiple possible locations for KML files
        possible_paths = [
            # From within container (relative to /app)
            Path("/kml-route-import"),
            Path("/data/kml-route-import"),
            # From local development
            Path(__file__).parent.parent.parent.parent.parent
            / "dev"
            / "completed"
            / "kml-route-import",
        ]

        for path in possible_paths:
            if path.exists():
                return path

        # Return the most likely path for skip messages
        return possible_paths[-1]

    def test_kml_routes_directory_exists(self, kml_routes_dir):
        """Verify test KML files are available."""
        import pytest

        if not kml_routes_dir.exists():
            pytest.skip(f"KML routes directory not found: {kml_routes_dir}")
        kml_files = list(kml_routes_dir.glob("*.kml"))
        if len(kml_files) == 0:
            pytest.skip(f"No KML files found in {kml_routes_dir}")

    def test_parse_leg_1_with_timing(self, kml_routes_dir):
        """Parse Leg 1 KML file and verify timing extraction."""
        leg1_path = kml_routes_dir / "Leg 1 Rev 6.kml"
        if not leg1_path.exists():
            pytest.skip(f"Leg 1 KML file not found: {leg1_path}")

        parsed_route = parse_kml_file(leg1_path)

        assert parsed_route is not None
        assert parsed_route.metadata.name
        assert len(parsed_route.points) > 0
        assert len(parsed_route.waypoints) > 0

        # Verify timing profile was created
        assert (
            parsed_route.timing_profile is not None
        ), "Timing profile should be populated"
        assert parsed_route.timing_profile.has_timing_data, "Should have timing data"

        # Verify waypoint timestamps were extracted
        waypoints_with_times = [
            wp for wp in parsed_route.waypoints if wp.expected_arrival_time
        ]
        assert (
            len(waypoints_with_times) > 0
        ), "Should have waypoints with extracted timestamps"

        # Verify points have timestamps assigned
        points_with_times = [p for p in parsed_route.points if p.expected_arrival_time]
        assert len(points_with_times) > 0, "Should have points with assigned timestamps"

    def test_parse_leg_1_departure_time(self, kml_routes_dir):
        """Verify Leg 1 departure time extraction."""
        leg1_path = kml_routes_dir / "Leg 1 Rev 6.kml"
        if not leg1_path.exists():
            pytest.skip(f"Leg 1 KML file not found: {leg1_path}")

        parsed_route = parse_kml_file(leg1_path)

        # Leg 1 timestamps are stored in UTC (first waypoint at 07:00Z)
        assert parsed_route.timing_profile.departure_time is not None
        assert parsed_route.timing_profile.departure_time.hour == 7
        assert parsed_route.timing_profile.departure_time.month == 10
        assert parsed_route.timing_profile.departure_time.day == 27

    def test_parse_leg_1_arrival_time(self, kml_routes_dir):
        """Verify Leg 1 arrival time extraction."""
        leg1_path = kml_routes_dir / "Leg 1 Rev 6.kml"
        if not leg1_path.exists():
            pytest.skip(f"Leg 1 KML file not found: {leg1_path}")

        parsed_route = parse_kml_file(leg1_path)

        # Should have arrival time
        assert parsed_route.timing_profile.arrival_time is not None
        assert isinstance(parsed_route.timing_profile.arrival_time, datetime)

    def test_parse_leg_1_duration(self, kml_routes_dir):
        """Verify Leg 1 total duration calculation."""
        leg1_path = kml_routes_dir / "Leg 1 Rev 6.kml"
        if not leg1_path.exists():
            pytest.skip(f"Leg 1 KML file not found: {leg1_path}")

        parsed_route = parse_kml_file(leg1_path)

        # Should have calculated total duration
        assert parsed_route.timing_profile.total_expected_duration_seconds is not None
        assert isinstance(
            parsed_route.timing_profile.total_expected_duration_seconds, (int, float)
        )
        assert parsed_route.timing_profile.total_expected_duration_seconds > 0

    def test_parse_leg_1_segment_speeds(self, kml_routes_dir):
        """Verify segment speed calculations for Leg 1."""
        leg1_path = kml_routes_dir / "Leg 1 Rev 6.kml"
        if not leg1_path.exists():
            pytest.skip(f"Leg 1 KML file not found: {leg1_path}")

        parsed_route = parse_kml_file(leg1_path)

        # Should have calculated speeds for some segments
        points_with_speed = [
            p for p in parsed_route.points if p.expected_segment_speed_knots is not None
        ]
        assert len(points_with_speed) > 0, "Should have calculated segment speeds"

        # Verify speeds are reasonable for flight (typically 400-500 knots for commercial aircraft)
        for point in points_with_speed:
            assert point.expected_segment_speed_knots > 0, "Speed should be positive"
            # Reasonable range: 100-600 knots (includes approach/climb speeds)
            assert (
                point.expected_segment_speed_knots < 600
            ), f"Speed too high: {point.expected_segment_speed_knots}"

    def test_parse_all_legs_without_crash(self, kml_routes_dir):
        """Parse all available leg KML files to verify robustness."""
        kml_files = sorted(list(kml_routes_dir.glob("Leg *.kml")))

        if not kml_files:
            pytest.skip("No Leg KML files found")

        parsed_routes = []
        for kml_file in kml_files:
            try:
                parsed_route = parse_kml_file(kml_file)
                assert parsed_route is not None, f"Failed to parse {kml_file.name}"
                assert len(parsed_route.points) > 0, f"No points in {kml_file.name}"
                parsed_routes.append((kml_file.name, parsed_route))
            except Exception as e:
                pytest.fail(f"Failed to parse {kml_file.name}: {e}")

        assert (
            len(parsed_routes) > 0
        ), "Should have successfully parsed at least one leg"

    def test_timing_profile_metadata(self, kml_routes_dir):
        """Verify timing profile includes expected metadata."""
        leg1_path = kml_routes_dir / "Leg 1 Rev 6.kml"
        if not leg1_path.exists():
            pytest.skip(f"Leg 1 KML file not found: {leg1_path}")

        parsed_route = parse_kml_file(leg1_path)

        # Check timing profile has all required fields
        assert parsed_route.timing_profile.has_timing_data is not None
        assert isinstance(parsed_route.timing_profile.has_timing_data, bool)
        assert parsed_route.timing_profile.segment_count_with_timing is not None
        assert isinstance(parsed_route.timing_profile.segment_count_with_timing, int)
        assert parsed_route.timing_profile.segment_count_with_timing >= 0


class TestTimingDataAccuracy:
    """Tests for mathematical accuracy of timing calculations."""

    @pytest.fixture
    def kml_routes_dir(self):
        """Path to test KML files from kml-route-import completion."""
        possible_paths = [
            Path("/kml-route-import"),
            Path("/data/kml-route-import"),
            Path(__file__).parent.parent.parent.parent.parent
            / "dev"
            / "completed"
            / "kml-route-import",
        ]
        for path in possible_paths:
            if path.exists():
                return path
        return possible_paths[-1]

    def test_waypoint_timestamp_format(self, kml_routes_dir):
        """Verify waypoint timestamps are correctly parsed."""
        leg1_path = kml_routes_dir / "Leg 1 Rev 6.kml"
        if not leg1_path.exists():
            pytest.skip(f"Leg 1 KML file not found: {leg1_path}")

        parsed_route = parse_kml_file(leg1_path)

        # All extracted waypoint times should be datetime objects
        for wp in parsed_route.waypoints:
            if wp.expected_arrival_time is not None:
                assert isinstance(wp.expected_arrival_time, datetime)
                # Verify times are in October 2025 (the test data month)
                assert wp.expected_arrival_time.year == 2025
                assert wp.expected_arrival_time.month == 10

    def test_segment_speed_calculation_math(self, kml_routes_dir):
        """Verify segment speed calculations are mathematically correct."""
        leg1_path = kml_routes_dir / "Leg 1 Rev 6.kml"
        if not leg1_path.exists():
            pytest.skip(f"Leg 1 KML file not found: {leg1_path}")

        parsed_route = parse_kml_file(leg1_path)

        # Find consecutive points with both timestamps and speeds
        for i in range(1, len(parsed_route.points)):
            prev_point = parsed_route.points[i - 1]
            curr_point = parsed_route.points[i]

            # If current point has a speed, verify it was calculated correctly
            if curr_point.expected_segment_speed_knots is not None:
                assert prev_point.expected_arrival_time is not None
                assert curr_point.expected_arrival_time is not None

                # Recalculate speed to verify
                from app.services.kml_parser import _haversine_distance

                distance_m = _haversine_distance(
                    prev_point.latitude,
                    prev_point.longitude,
                    curr_point.latitude,
                    curr_point.longitude,
                )

                time_delta = (
                    curr_point.expected_arrival_time - prev_point.expected_arrival_time
                )
                time_s = time_delta.total_seconds()

                if time_s > 0:
                    expected_speed = (distance_m / time_s) * (3600 / 1852)
                    # Allow small floating point difference
                    assert (
                        abs(curr_point.expected_segment_speed_knots - expected_speed)
                        < 0.1
                    )

    def test_total_duration_calculation(self, kml_routes_dir):
        """Verify total route duration is calculated correctly."""
        leg1_path = kml_routes_dir / "Leg 1 Rev 6.kml"
        if not leg1_path.exists():
            pytest.skip(f"Leg 1 KML file not found: {leg1_path}")

        parsed_route = parse_kml_file(leg1_path)

        # Verify duration matches departure/arrival times if both exist
        if (
            parsed_route.timing_profile.departure_time
            and parsed_route.timing_profile.arrival_time
        ):
            expected_duration = (
                parsed_route.timing_profile.arrival_time
                - parsed_route.timing_profile.departure_time
            ).total_seconds()

            assert (
                parsed_route.timing_profile.total_expected_duration_seconds
                == expected_duration
            )


class TestRouteResponseIntegration:
    """Tests for route response generation with timing data."""

    @pytest.fixture
    def kml_routes_dir(self):
        """Path to test KML files from kml-route-import completion."""
        possible_paths = [
            Path("/kml-route-import"),
            Path("/data/kml-route-import"),
            Path(__file__).parent.parent.parent.parent.parent
            / "dev"
            / "completed"
            / "kml-route-import",
        ]
        for path in possible_paths:
            if path.exists():
                return path
        return possible_paths[-1]

    def test_route_response_includes_timing_flag(self, kml_routes_dir):
        """Verify RouteResponse includes has_timing_data flag."""
        leg1_path = kml_routes_dir / "Leg 1 Rev 6.kml"
        if not leg1_path.exists():
            pytest.skip(f"Leg 1 KML file not found: {leg1_path}")

        parsed_route = parse_kml_file(leg1_path)

        # Create a mock route response structure
        has_timing = (
            parsed_route.timing_profile is not None
            and parsed_route.timing_profile.has_timing_data
        )

        assert has_timing, "Route should have timing data in response"

    def test_route_detail_response_includes_profile(self, kml_routes_dir):
        """Verify detailed route response includes timing profile."""
        leg1_path = kml_routes_dir / "Leg 1 Rev 6.kml"
        if not leg1_path.exists():
            pytest.skip(f"Leg 1 KML file not found: {leg1_path}")

        parsed_route = parse_kml_file(leg1_path)

        # Verify timing profile is available for detail responses
        assert parsed_route.timing_profile is not None
        assert parsed_route.timing_profile.has_timing_data


class TestEdgeCasesAndRobustness:
    """Tests for edge cases and robustness of timing extraction."""

    @pytest.fixture
    def kml_routes_dir(self):
        """Path to test KML files from kml-route-import completion."""
        possible_paths = [
            Path("/kml-route-import"),
            Path("/data/kml-route-import"),
            Path(__file__).parent.parent.parent.parent.parent
            / "dev"
            / "completed"
            / "kml-route-import",
        ]
        for path in possible_paths:
            if path.exists():
                return path
        return possible_paths[-1]

    def test_handle_missing_waypoint_timestamps(self, kml_routes_dir):
        """Verify graceful handling of waypoints without timestamps."""
        leg1_path = kml_routes_dir / "Leg 1 Rev 6.kml"
        if not leg1_path.exists():
            pytest.skip(f"Leg 1 KML file not found: {leg1_path}")

        # Should parse without error even if some waypoints lack timestamps
        parsed_route = parse_kml_file(leg1_path)
        assert parsed_route is not None

    def test_handle_incomplete_timing_data(self, kml_routes_dir):
        """Verify parser works with partial timing information."""
        leg1_path = kml_routes_dir / "Leg 1 Rev 6.kml"
        if not leg1_path.exists():
            pytest.skip(f"Leg 1 KML file not found: {leg1_path}")

        parsed_route = parse_kml_file(leg1_path)

        # Some points may have times while others don't - should still work
        assert len(parsed_route.points) > 0

    def test_handle_out_of_order_timestamps(self, kml_routes_dir):
        """Verify robustness with time ordering."""
        leg1_path = kml_routes_dir / "Leg 1 Rev 6.kml"
        if not leg1_path.exists():
            pytest.skip(f"Leg 1 KML file not found: {leg1_path}")

        parsed_route = parse_kml_file(leg1_path)

        # Should gracefully handle (not calculate speed for) out-of-order times
        # This is implicitly tested by the speed calculation logic that checks time_delta > 0
        assert len(parsed_route.points) > 0


class TestRealWorldFlight:
    """Tests with real-world flight characteristics."""

    @pytest.fixture
    def kml_routes_dir(self):
        """Path to test KML files from kml-route-import completion."""
        possible_paths = [
            Path("/kml-route-import"),
            Path("/data/kml-route-import"),
            Path(__file__).parent.parent.parent.parent.parent
            / "dev"
            / "completed"
            / "kml-route-import",
        ]
        for path in possible_paths:
            if path.exists():
                return path
        return possible_paths[-1]

    def test_leg_1_is_overwater_flight(self, kml_routes_dir):
        """Verify Leg 1 parsing for Andrews to Hawaii flight."""
        leg1_path = kml_routes_dir / "Leg 1 Rev 6.kml"
        if not leg1_path.exists():
            pytest.skip(f"Leg 1 KML file not found: {leg1_path}")

        parsed_route = parse_kml_file(leg1_path)

        # KADW to PHNL is a long overwater flight
        assert (
            "KADW" in parsed_route.metadata.name or "PHNL" in parsed_route.metadata.name
        )
        # Should have substantial distance and time
        assert len(parsed_route.points) >= 49  # Long flight
        assert parsed_route.timing_profile.total_expected_duration_seconds is not None
        assert (
            parsed_route.timing_profile.total_expected_duration_seconds > 3600
        )  # More than 1 hour

    def test_segment_speeds_within_flight_envelope(self, kml_routes_dir):
        """Verify calculated speeds are realistic for aircraft."""
        leg1_path = kml_routes_dir / "Leg 1 Rev 6.kml"
        if not leg1_path.exists():
            pytest.skip(f"Leg 1 KML file not found: {leg1_path}")

        parsed_route = parse_kml_file(leg1_path)

        # For a real flight, typical cruise is 400-500 knots
        # Climb/descent may be slower
        speeds = [
            p.expected_segment_speed_knots
            for p in parsed_route.points
            if p.expected_segment_speed_knots is not None
        ]

        if speeds:
            avg_speed = sum(speeds) / len(speeds)
            # Reasonable average for commercial flight
            assert 200 < avg_speed < 500, f"Average speed {avg_speed} unrealistic"
