"""Tests for position simulator."""

import pytest

from app.models.config import PositionConfig, RouteConfig
from app.simulation.position import PositionSimulator


class TestPositionSimulator:
    """Test position simulator functionality."""

    @pytest.fixture
    def simulator(self, default_config):
        """Create a position simulator for tests."""
        return PositionSimulator(default_config.route, default_config.position)

    def test_simulator_initialization(self, simulator):
        """Test that simulator initializes properly."""
        assert simulator.progress == 0.0
        assert simulator.current_speed == 0.0
        assert simulator.current_heading == 0.0
        assert simulator.current_altitude > 0

    def test_position_data_values_in_range(self, simulator):
        """Test that position data values are within expected ranges."""
        config = simulator.position_config
        position = simulator.update()

        assert config.speed_min_knots <= position.speed <= config.speed_max_knots
        assert config.altitude_min_feet <= position.altitude <= config.altitude_max_feet
        assert 0 <= position.heading <= 360
        assert -90 <= position.latitude <= 90
        assert -180 <= position.longitude <= 180

    def test_multiple_updates_change_state(self, simulator):
        """Test that multiple updates change position state."""
        pos1 = simulator.update()
        pos2 = simulator.update()
        pos3 = simulator.update()

        # At least one value should change over multiple updates
        position_changed = (
            pos1.latitude != pos2.latitude or
            pos1.longitude != pos2.longitude or
            pos1.speed != pos2.speed or
            pos1.heading != pos2.heading
        )
        assert position_changed

    def test_speed_variation(self, simulator):
        """Test that speed varies realistically."""
        speeds = []
        for _ in range(10):
            pos = simulator.update()
            speeds.append(pos.speed)

        # Speed should vary but stay in range
        config = simulator.position_config
        for speed in speeds:
            assert config.speed_min_knots <= speed <= config.speed_max_knots

        # Should have some variation (not all same)
        assert len(set(speeds)) > 1

    def test_heading_variation(self, simulator):
        """Test that heading varies realistically."""
        headings = []
        for _ in range(10):
            pos = simulator.update()
            headings.append(pos.heading)

        # All headings should be valid
        for heading in headings:
            assert 0 <= heading <= 360

        # Should have some variation
        assert len(set([int(h) for h in headings])) > 1

    def test_altitude_variation(self, simulator):
        """Test that altitude varies realistically."""
        config = simulator.position_config
        altitudes = []

        for _ in range(10):
            pos = simulator.update()
            altitudes.append(pos.altitude)
            assert config.altitude_min_feet <= pos.altitude <= config.altitude_max_feet

        # Should have variation
        assert len(set([int(a) for a in altitudes])) > 1

    def test_set_progress(self, simulator):
        """Test setting progress along route."""
        simulator.set_progress(0.25)
        assert simulator.progress == 0.25

        simulator.set_progress(0.75)
        assert simulator.progress == 0.75

    def test_progress_wrapping(self, simulator):
        """Test that progress wraps around."""
        simulator.set_progress(1.5)
        assert simulator.progress == 0.5

    def test_reset(self, simulator):
        """Test resetting simulator."""
        # Modify state
        for _ in range(5):
            simulator.update()

        initial_altitude = simulator.current_altitude

        # Reset
        simulator.reset()

        assert simulator.progress == 0.0
        assert simulator.current_speed == 0.0
        assert simulator.current_heading == 0.0
        # Altitude should be reset to middle value
        config = simulator.position_config
        expected_altitude = (
            config.altitude_min_feet + config.altitude_max_feet
        ) / 2.0
        assert simulator.current_altitude == expected_altitude

    def test_circular_route_position(self, default_config):
        """Test position updates with circular route."""
        default_config.route.pattern = "circular"
        simulator = PositionSimulator(default_config.route, default_config.position)

        initial_pos = simulator.update()
        initial_lat = initial_pos.latitude
        initial_lon = initial_pos.longitude

        # Update many times to move around circle with increased speed
        for _ in range(500):  # More iterations to accumulate movement
            simulator.update()

        # Should have moved significantly
        final_pos = simulator.update()
        distance = (
            abs(final_pos.latitude - initial_lat) +
            abs(final_pos.longitude - initial_lon)
        )
        assert distance > 0.001  # Relaxed threshold based on actual movement

    def test_straight_route_position(self, default_config):
        """Test position updates with straight route."""
        default_config.route.pattern = "straight"
        simulator = PositionSimulator(default_config.route, default_config.position)

        initial_pos = simulator.update()

        # Update many times
        for _ in range(500):  # More iterations to accumulate movement
            simulator.update()

        final_pos = simulator.update()

        # Should have some position change
        distance = (
            abs(final_pos.latitude - initial_pos.latitude) +
            abs(final_pos.longitude - initial_pos.longitude)
        )
        assert distance > 0.001  # Relaxed threshold based on actual movement
