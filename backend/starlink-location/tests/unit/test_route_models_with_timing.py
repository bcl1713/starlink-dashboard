"""Tests for route models with timing extensions (Phase 1 - ETA Route Timing)."""

import pytest
from datetime import datetime, timezone

from app.models.route import (
    RoutePoint,
    RouteWaypoint,
    RouteMetadata,
    RouteTimingProfile,
    ParsedRoute,
    RouteResponse,
    RouteDetailResponse,
)


class TestRoutePointWithTiming:
    """Test RoutePoint model with timing fields."""

    def test_route_point_creation_without_timing(self):
        """Test that existing RoutePoint creation still works (backward compat)."""
        point = RoutePoint(
            latitude=40.7128, longitude=-74.0060, altitude=100, sequence=0
        )
        assert point.latitude == 40.7128
        assert point.longitude == -74.0060
        assert point.altitude == 100
        assert point.sequence == 0
        assert point.expected_arrival_time is None
        assert point.expected_segment_speed_knots is None

    def test_route_point_creation_with_timing(self):
        """Test RoutePoint with timing fields."""
        arrival_time = datetime(2025, 10, 27, 16, 57, 55, tzinfo=timezone.utc)
        point = RoutePoint(
            latitude=40.7128,
            longitude=-74.0060,
            altitude=100,
            sequence=0,
            expected_arrival_time=arrival_time,
            expected_segment_speed_knots=598.0,
        )
        assert point.latitude == 40.7128
        assert point.expected_arrival_time == arrival_time
        assert point.expected_segment_speed_knots == 598.0

    def test_route_point_partial_timing(self):
        """Test RoutePoint with only arrival time, no speed."""
        arrival_time = datetime(2025, 10, 27, 16, 57, 55, tzinfo=timezone.utc)
        point = RoutePoint(
            latitude=40.7128,
            longitude=-74.0060,
            expected_arrival_time=arrival_time,
        )
        assert point.expected_arrival_time == arrival_time
        assert point.expected_segment_speed_knots is None

    def test_route_point_json_serialization_with_timing(self):
        """Test that RoutePoint serializes/deserializes with timing."""
        arrival_time = datetime(2025, 10, 27, 16, 57, 55, tzinfo=timezone.utc)
        point = RoutePoint(
            latitude=40.7128,
            longitude=-74.0060,
            expected_arrival_time=arrival_time,
            expected_segment_speed_knots=598.0,
        )
        json_data = point.model_dump(mode="json")
        assert json_data["latitude"] == 40.7128
        assert json_data["expected_arrival_time"] == "2025-10-27T16:57:55Z"
        assert json_data["expected_segment_speed_knots"] == 598.0

    def test_route_point_from_dict_with_timing(self):
        """Test creating RoutePoint from dict with timing."""
        data = {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "altitude": 100,
            "sequence": 0,
            "expected_arrival_time": "2025-10-27T16:57:55Z",
            "expected_segment_speed_knots": 598.0,
        }
        point = RoutePoint(**data)
        assert point.expected_arrival_time.year == 2025
        assert point.expected_segment_speed_knots == 598.0


class TestRouteWaypointWithTiming:
    """Test RouteWaypoint model with timing field."""

    def test_route_waypoint_without_timing(self):
        """Test that existing RouteWaypoint creation still works."""
        wp = RouteWaypoint(
            name="WMSA",
            description="Sultan Abdul Aziz Shah",
            latitude=3.132222,
            longitude=101.55028,
            order=42,
            role="departure",
        )
        assert wp.name == "WMSA"
        assert wp.expected_arrival_time is None

    def test_route_waypoint_with_timing(self):
        """Test RouteWaypoint with arrival time."""
        arrival_time = datetime(2025, 10, 27, 16, 57, 55, tzinfo=timezone.utc)
        wp = RouteWaypoint(
            name="APPCH",
            description="Approach waypoint\nTime Over Waypoint: 2025-10-27 16:57:55Z",
            latitude=3.132222,
            longitude=101.55028,
            order=2,
            role="waypoint",
            expected_arrival_time=arrival_time,
        )
        assert wp.name == "APPCH"
        assert wp.expected_arrival_time == arrival_time

    def test_route_waypoint_json_serialization(self):
        """Test RouteWaypoint serialization with timing."""
        arrival_time = datetime(2025, 10, 27, 16, 57, 55, tzinfo=timezone.utc)
        wp = RouteWaypoint(
            name="APPCH",
            latitude=3.132222,
            longitude=101.55028,
            order=2,
            expected_arrival_time=arrival_time,
        )
        json_data = wp.model_dump(mode="json")
        assert json_data["name"] == "APPCH"
        assert json_data["expected_arrival_time"] == "2025-10-27T16:57:55Z"


class TestRouteTimingProfile:
    """Test RouteTimingProfile model."""

    def test_timing_profile_creation_minimal(self):
        """Test creating minimal RouteTimingProfile."""
        profile = RouteTimingProfile()
        assert profile.has_timing_data is False
        assert profile.segment_count_with_timing == 0
        assert profile.departure_time is None
        assert profile.arrival_time is None

    def test_timing_profile_creation_full(self):
        """Test creating full RouteTimingProfile."""
        departure = datetime(2025, 10, 27, 15, 45, 0, tzinfo=timezone.utc)
        arrival = datetime(2025, 10, 27, 16, 57, 55, tzinfo=timezone.utc)
        profile = RouteTimingProfile(
            departure_time=departure,
            arrival_time=arrival,
            total_expected_duration_seconds=4575.0,
            has_timing_data=True,
            segment_count_with_timing=42,
            actual_departure_time=departure,
            actual_arrival_time=None,
            flight_status="in_flight",
        )
        assert profile.departure_time == departure
        assert profile.arrival_time == arrival
        assert profile.has_timing_data is True
        assert profile.segment_count_with_timing == 42
        assert profile.actual_departure_time == departure
        assert profile.actual_arrival_time is None
        assert profile.flight_status == "in_flight"
        assert profile.is_departed() is True
        assert profile.is_in_flight() is True

    def test_timing_profile_get_total_duration_from_times(self):
        """Test calculating duration from departure/arrival times."""
        departure = datetime(2025, 10, 27, 15, 45, 0, tzinfo=timezone.utc)
        arrival = datetime(2025, 10, 27, 16, 57, 55, tzinfo=timezone.utc)
        profile = RouteTimingProfile(
            departure_time=departure,
            arrival_time=arrival,
        )
        duration = profile.get_total_duration()
        # 15:45:00 to 16:57:55 = 1h 12m 55s = 4375 seconds
        assert duration == pytest.approx(4375.0, abs=1.0)

    def test_timing_profile_get_total_duration_from_explicit(self):
        """Test getting duration from explicit field."""
        profile = RouteTimingProfile(
            total_expected_duration_seconds=4575.0,
        )
        duration = profile.get_total_duration()
        assert duration == pytest.approx(4575.0)

    def test_timing_profile_get_total_duration_priority(self):
        """Test that calculated duration takes priority over explicit."""
        departure = datetime(2025, 10, 27, 15, 45, 0, tzinfo=timezone.utc)
        arrival = datetime(2025, 10, 27, 16, 57, 55, tzinfo=timezone.utc)
        profile = RouteTimingProfile(
            departure_time=departure,
            arrival_time=arrival,
            total_expected_duration_seconds=9999.0,  # This should be ignored
        )
        duration = profile.get_total_duration()
        # Should use calculated (4375s), not explicit (9999s)
        assert duration == pytest.approx(4375.0, abs=1.0)

    def test_timing_profile_json_serialization(self):
        """Test RouteTimingProfile serialization."""
        departure = datetime(2025, 10, 27, 15, 45, 0, tzinfo=timezone.utc)
        arrival = datetime(2025, 10, 27, 16, 57, 55, tzinfo=timezone.utc)
        profile = RouteTimingProfile(
            departure_time=departure,
            arrival_time=arrival,
            has_timing_data=True,
            segment_count_with_timing=42,
        )
        json_data = profile.model_dump(mode="json")
        assert json_data["departure_time"] == "2025-10-27T15:45:00Z"
        assert json_data["arrival_time"] == "2025-10-27T16:57:55Z"
        assert json_data["has_timing_data"] is True
        assert json_data["actual_departure_time"] is None
        assert json_data["flight_status"] == "pre_departure"

    def test_timing_profile_status_helpers(self):
        """is_departed/is_in_flight should respect status text and timestamps."""
        profile = RouteTimingProfile(
            flight_status="pre_departure",
            actual_departure_time=None,
        )
        assert profile.is_departed() is False
        assert profile.is_in_flight() is False

        profile.flight_status = "in_flight"
        assert profile.is_departed() is True
        assert profile.is_in_flight() is True

        profile.flight_status = "post_arrival"
        assert profile.is_departed() is True
        assert profile.is_in_flight() is False

        profile.flight_status = "pre_departure"
        profile.actual_departure_time = datetime(
            2025, 10, 27, 15, 45, 0, tzinfo=timezone.utc
        )
        assert profile.is_departed() is True
        assert profile.is_in_flight() is False

    def test_timing_profile_serialization_includes_actual_times(self):
        """Ensure model_dump exposes actual timing metadata when populated."""
        departure = datetime(2025, 10, 27, 15, 45, 0, tzinfo=timezone.utc)
        arrival = datetime(2025, 10, 27, 16, 50, 0, tzinfo=timezone.utc)
        profile = RouteTimingProfile(
            departure_time=departure,
            arrival_time=arrival,
            actual_departure_time=departure,
            actual_arrival_time=arrival,
            flight_status="post_arrival",
            has_timing_data=True,
            segment_count_with_timing=10,
        )

        serialized = profile.model_dump(mode="json")
        assert serialized["actual_departure_time"] == "2025-10-27T15:45:00Z"
        assert serialized["actual_arrival_time"] == "2025-10-27T16:50:00Z"
        assert serialized["flight_status"] == "post_arrival"


class TestParsedRouteWithTiming:
    """Test ParsedRoute model with timing profile."""

    def test_parsed_route_without_timing(self):
        """Test ParsedRoute still works without timing."""
        metadata = RouteMetadata(
            name="Test Route",
            file_path="/data/test.kml",
            point_count=5,
        )
        points = [
            RoutePoint(latitude=40.0, longitude=-74.0, sequence=0),
            RoutePoint(latitude=41.0, longitude=-73.0, sequence=1),
        ]
        route = ParsedRoute(metadata=metadata, points=points)
        assert route.timing_profile is None

    def test_parsed_route_with_timing_profile(self):
        """Test ParsedRoute with timing profile."""
        metadata = RouteMetadata(
            name="Test Route",
            file_path="/data/test.kml",
            point_count=5,
        )
        departure = datetime(2025, 10, 27, 15, 45, 0, tzinfo=timezone.utc)
        arrival = datetime(2025, 10, 27, 16, 57, 55, tzinfo=timezone.utc)
        timing_profile = RouteTimingProfile(
            departure_time=departure,
            arrival_time=arrival,
            has_timing_data=True,
        )
        points = [
            RoutePoint(
                latitude=40.0,
                longitude=-74.0,
                sequence=0,
                expected_arrival_time=departure,
            ),
            RoutePoint(
                latitude=41.0,
                longitude=-73.0,
                sequence=1,
                expected_arrival_time=arrival,
            ),
        ]
        route = ParsedRoute(
            metadata=metadata,
            points=points,
            timing_profile=timing_profile,
        )
        assert route.timing_profile is not None
        assert route.timing_profile.has_timing_data is True


class TestRouteResponseWithTiming:
    """Test RouteResponse model with timing fields."""

    def test_route_response_without_timing(self):
        """Test RouteResponse backward compatibility."""
        response = RouteResponse(
            id="route-1",
            name="Test Route",
            point_count=5,
            is_active=False,
            imported_at=datetime.now(timezone.utc),
        )
        assert response.has_timing_data is False

    def test_route_response_with_timing(self):
        """Test RouteResponse with timing flag."""
        response = RouteResponse(
            id="route-1",
            name="Test Route",
            point_count=5,
            is_active=False,
            imported_at=datetime.now(timezone.utc),
            has_timing_data=True,
        )
        assert response.has_timing_data is True

    def test_route_response_json_serialization(self):
        """Test RouteResponse serialization includes timing."""
        response = RouteResponse(
            id="route-1",
            name="Test Route",
            point_count=5,
            is_active=True,
            imported_at=datetime(2025, 10, 27, 15, 45, 0, tzinfo=timezone.utc),
            has_timing_data=True,
        )
        json_data = response.model_dump(mode="json")
        assert json_data["has_timing_data"] is True
        assert json_data["id"] == "route-1"


class TestRouteDetailResponseWithTiming:
    """Test RouteDetailResponse model with timing profile."""

    def test_route_detail_response_without_timing(self):
        """Test RouteDetailResponse backward compatibility."""
        metadata = RouteMetadata(
            name="Test Route",
            file_path="/data/test.kml",
            point_count=5,
        )
        points = [
            RoutePoint(latitude=40.0, longitude=-74.0, sequence=0),
        ]
        response = RouteDetailResponse(
            id="route-1",
            name="Test Route",
            point_count=5,
            is_active=False,
            imported_at=datetime.now(timezone.utc),
            file_path="/data/test.kml",
            points=points,
            statistics={},
        )
        assert response.timing_profile is None

    def test_route_detail_response_with_timing_profile(self):
        """Test RouteDetailResponse with timing profile."""
        metadata = RouteMetadata(
            name="Test Route",
            file_path="/data/test.kml",
            point_count=5,
        )
        departure = datetime(2025, 10, 27, 15, 45, 0, tzinfo=timezone.utc)
        arrival = datetime(2025, 10, 27, 16, 57, 55, tzinfo=timezone.utc)
        timing_profile = RouteTimingProfile(
            departure_time=departure,
            arrival_time=arrival,
            has_timing_data=True,
        )
        points = [
            RoutePoint(latitude=40.0, longitude=-74.0, sequence=0),
        ]
        response = RouteDetailResponse(
            id="route-1",
            name="Test Route",
            point_count=5,
            is_active=False,
            imported_at=datetime.now(timezone.utc),
            file_path="/data/test.kml",
            points=points,
            statistics={},
            timing_profile=timing_profile,
        )
        assert response.timing_profile is not None
        assert response.timing_profile.has_timing_data is True


class TestBackwardCompatibility:
    """Test that all models remain backward compatible."""

    def test_route_point_from_old_json(self):
        """Test deserializing RoutePoint from old JSON (no timing fields)."""
        old_json = {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "altitude": 100,
            "sequence": 0,
        }
        point = RoutePoint(**old_json)
        assert point.expected_arrival_time is None
        assert point.expected_segment_speed_knots is None

    def test_route_response_from_old_json(self):
        """Test deserializing RouteResponse from old JSON."""
        old_json = {
            "id": "route-1",
            "name": "Test",
            "point_count": 5,
            "is_active": False,
            "imported_at": datetime.now(timezone.utc),
        }
        response = RouteResponse(**old_json)
        assert response.has_timing_data is False  # Should default to False

    def test_parsed_route_from_old_json_style(self):
        """Test ParsedRoute without timing_profile."""
        metadata = RouteMetadata(
            name="Test",
            file_path="/data/test.kml",
            point_count=2,
        )
        points = [
            RoutePoint(latitude=40.0, longitude=-74.0, sequence=0),
            RoutePoint(latitude=41.0, longitude=-73.0, sequence=1),
        ]
        # Omit timing_profile - should default to None
        route = ParsedRoute(metadata=metadata, points=points)
        assert route.timing_profile is None
        assert len(route.points) == 2


class TestTimingFieldTypes:
    """Test that timing fields are properly typed."""

    def test_arrival_time_is_optional_datetime(self):
        """Test that expected_arrival_time is Optional[datetime]."""
        point1 = RoutePoint(latitude=40.0, longitude=-74.0)
        assert point1.expected_arrival_time is None

        point2 = RoutePoint(
            latitude=40.0,
            longitude=-74.0,
            expected_arrival_time=datetime(
                2025, 10, 27, 16, 57, 55, tzinfo=timezone.utc
            ),
        )
        assert isinstance(point2.expected_arrival_time, datetime)

    def test_segment_speed_is_optional_float(self):
        """Test that expected_segment_speed_knots is Optional[float]."""
        point1 = RoutePoint(latitude=40.0, longitude=-74.0)
        assert point1.expected_segment_speed_knots is None

        point2 = RoutePoint(
            latitude=40.0,
            longitude=-74.0,
            expected_segment_speed_knots=598.5,
        )
        assert isinstance(point2.expected_segment_speed_knots, float)


class TestModelExamples:
    """Test that example schemas work."""

    def test_route_point_example_valid(self):
        """Test that RoutePoint example schema is valid."""
        example_data = {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "altitude": 100,
            "sequence": 0,
            "expected_arrival_time": "2025-10-27T16:57:55Z",
            "expected_segment_speed_knots": 598.0,
        }
        point = RoutePoint(**example_data)
        assert point.latitude == 40.7128
        assert point.expected_segment_speed_knots == 598.0

    def test_route_waypoint_example_valid(self):
        """Test that RouteWaypoint example schema is valid."""
        example_data = {
            "name": "WMSA",
            "description": "Sultan Abdul Aziz Shah\nTime Over Waypoint: 2025-10-27 16:57:55Z",
            "style_url": "#destWaypointIcon",
            "latitude": 3.132222,
            "longitude": 101.55028,
            "altitude": None,
            "order": 42,
            "role": "departure",
            "expected_arrival_time": "2025-10-27T16:57:55Z",
        }
        waypoint = RouteWaypoint(**example_data)
        assert waypoint.name == "WMSA"
        assert waypoint.expected_arrival_time is not None
