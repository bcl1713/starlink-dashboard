"""Tests for synthetic route generator."""

import pytest
import math

from app.simulation.route import (
    CircularRoute,
    StraightRoute,
    calculate_destination,
    degrees_to_radians,
    radians_to_degrees,
    create_route,
)


class TestDegreeRadianConversion:
    """Test degree and radian conversion utilities."""

    def test_degrees_to_radians(self):
        """Test converting degrees to radians."""
        assert degrees_to_radians(0) == 0
        assert degrees_to_radians(180) == pytest.approx(math.pi)
        assert degrees_to_radians(90) == pytest.approx(math.pi / 2)

    def test_radians_to_degrees(self):
        """Test converting radians to degrees."""
        assert radians_to_degrees(0) == 0
        assert radians_to_degrees(math.pi) == pytest.approx(180)
        assert radians_to_degrees(math.pi / 2) == pytest.approx(90)


class TestCalculateDestination:
    """Test great-circle distance calculation."""

    def test_calculate_destination_north(self):
        """Test calculating destination to the north."""
        lat, lon = calculate_destination(40.0, -74.0, 0, 111.2)  # ~111.2 km per degree
        assert lat == pytest.approx(41.0, abs=0.01)
        assert lon == pytest.approx(-74.0, abs=0.01)

    def test_calculate_destination_east(self):
        """Test calculating destination to the east."""
        lat, lon = calculate_destination(0.0, 0.0, 90, 111.2)
        assert lat == pytest.approx(0.0, abs=0.01)
        # Longitude varies with latitude, but should be positive
        assert lon > 0

    def test_calculate_destination_zero_distance(self):
        """Test destination with zero distance."""
        lat, lon = calculate_destination(40.0, -74.0, 45, 0)
        assert lat == pytest.approx(40.0)
        assert lon == pytest.approx(-74.0)


class TestCircularRoute:
    """Test circular route generation."""

    def test_circular_route_creation(self):
        """Test creating a circular route."""
        route = CircularRoute(40.0, -74.0, 100.0)
        assert route.center_lat == 40.0
        assert route.center_lon == -74.0
        assert route.radius_km == 100.0
        assert len(route.points) == 360

    def test_circular_route_points_structure(self):
        """Test that circular route generates correct point structure."""
        route = CircularRoute(40.0, -74.0, 50.0)
        point = route.points[0]
        assert len(point) == 3  # (lat, lon, bearing)
        assert isinstance(point[0], float)  # latitude
        assert isinstance(point[1], float)  # longitude
        assert isinstance(point[2], float)  # bearing

    def test_circular_route_get_point(self):
        """Test getting points from circular route."""
        route = CircularRoute(40.0, -74.0, 100.0)

        # Progress 0 should give first point
        lat1, lon1, head1 = route.get_point(0.0)
        assert lat1 == pytest.approx(route.points[0][0])
        assert lon1 == pytest.approx(route.points[0][1])

        # Progress 0.25 should give point ~90 degrees around
        lat_quarter, lon_quarter, _ = route.get_point(0.25)
        # Should be significantly different location
        assert abs(lat_quarter - lat1) > 0.1 or abs(lon_quarter - lon1) > 0.1

    def test_circular_route_progress_wrap(self):
        """Test that progress wraps around properly."""
        route = CircularRoute(40.0, -74.0, 100.0)

        # Progress 1.0 and 0.0 should give same point
        lat_0, lon_0, head_0 = route.get_point(0.0)
        lat_1, lon_1, head_1 = route.get_point(1.0)

        assert lat_0 == pytest.approx(lat_1)
        assert lon_0 == pytest.approx(lon_1)

    def test_circular_route_interpolation(self):
        """Test that interpolation works smoothly."""
        route = CircularRoute(40.0, -74.0, 100.0)

        lat1, lon1, _ = route.get_segment(0.0)
        lat2, lon2, _ = route.get_segment(0.01)

        # Should be close but not identical
        assert abs(lat2 - lat1) < 1.0
        assert abs(lon2 - lon1) < 1.0


class TestStraightRoute:
    """Test straight line route generation."""

    def test_straight_route_creation(self):
        """Test creating a straight route."""
        route = StraightRoute(40.0, -74.0, 41.0, -73.0)
        assert route.start_lat == 40.0
        assert route.start_lon == -74.0
        assert route.end_lat == 41.0
        assert route.end_lon == -73.0
        assert route.distance_km > 0
        assert 0 <= route.bearing < 360

    def test_straight_route_get_segment_start(self):
        """Test getting start of straight route."""
        route = StraightRoute(40.0, -74.0, 41.0, -73.0)
        lat, lon, bearing = route.get_segment(0.0)

        assert lat == pytest.approx(40.0, abs=0.01)
        assert lon == pytest.approx(-74.0, abs=0.01)
        assert bearing == pytest.approx(route.bearing)

    def test_straight_route_get_segment_end(self):
        """Test getting near-end of straight route."""
        route = StraightRoute(40.0, -74.0, 41.0, -73.0)
        # Use 0.99 instead of 1.0 because progress wraps at 1.0 in circular behavior
        lat, lon, bearing = route.get_segment(0.99)

        # Should be very close to end point
        assert lat == pytest.approx(41.0, abs=0.05)
        assert lon == pytest.approx(-73.0, abs=0.05)
        assert bearing == pytest.approx(route.bearing)

    def test_straight_route_get_segment_middle(self):
        """Test getting midpoint of straight route."""
        route = StraightRoute(40.0, -74.0, 42.0, -72.0)
        lat_mid, lon_mid, bearing = route.get_segment(0.5)

        # Should be roughly between start and end
        assert 40.0 < lat_mid < 42.0
        assert -74.0 < lon_mid < -72.0


class TestCreateRoute:
    """Test route factory function."""

    def test_create_circular_route(self):
        """Test creating circular route via factory."""
        route = create_route("circular", 40.0, -74.0, radius_km=100.0)
        assert isinstance(route, CircularRoute)
        assert route.radius_km == 100.0

    def test_create_straight_route(self):
        """Test creating straight route via factory."""
        route = create_route("straight", 40.0, -74.0, distance_km=500.0)
        assert isinstance(route, StraightRoute)
        assert route.distance_km == pytest.approx(500.0, abs=50)

    def test_create_invalid_route(self):
        """Test that invalid pattern raises error."""
        with pytest.raises(ValueError):
            create_route("invalid", 40.0, -74.0)

    def test_default_parameters(self):
        """Test factory with default parameters."""
        route = create_route("circular", 40.0, -74.0)
        assert isinstance(route, CircularRoute)
        assert route.radius_km == 100.0
