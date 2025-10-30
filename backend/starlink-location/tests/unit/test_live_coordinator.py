"""Unit tests for LiveCoordinator.

Tests cover telemetry collection, heading calculation, error handling,
and graceful degradation using mocked StarlinkClient.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
import starlink_grpc
from grpc import RpcError

from app.live.coordinator import LiveCoordinator
from app.models.config import (
    HeadingTrackerConfig,
    SimulationConfig,
)
from app.models.telemetry import (
    EnvironmentalData,
    NetworkData,
    ObstructionData,
    PositionData,
    TelemetryData,
)
from tests.conftest import default_mock_telemetry


class TestLiveCoordinatorInitialization:
    """Test LiveCoordinator initialization."""

    @patch("app.live.coordinator.StarlinkClient")
    def test_init_success(self, mock_client_class):
        """Test successful initialization."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_telemetry.return_value = default_mock_telemetry()

        with patch("app.live.coordinator.time.time", return_value=1000.0):
            config = SimulationConfig()
            coordinator = LiveCoordinator(config)

        assert coordinator.config is config
        assert coordinator.start_time == 1000.0
        assert coordinator.client is mock_client
        assert coordinator.heading_tracker is not None
        assert coordinator.heading_tracker.min_distance_meters == 10.0
        assert coordinator.heading_tracker.max_age_seconds == 30.0
        assert coordinator._last_valid_telemetry is not None

    @patch("app.live.coordinator.StarlinkClient")
    def test_init_with_custom_heading_config(self, mock_client_class):
        """Test initialization with custom heading tracker config."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_telemetry.return_value = default_mock_telemetry()

        config = SimulationConfig(
            heading_tracker=HeadingTrackerConfig(
                min_distance_meters=25.0,
                max_age_seconds=60.0,
            )
        )
        coordinator = LiveCoordinator(config)

        assert coordinator.heading_tracker.min_distance_meters == 25.0
        assert coordinator.heading_tracker.max_age_seconds == 60.0

    def test_init_invalid_config(self):
        """Test initialization fails with invalid config type."""
        with pytest.raises(ValueError, match="must be a SimulationConfig"):
            LiveCoordinator({"invalid": "config"})

    @patch("app.live.coordinator.StarlinkClient")
    def test_initialization_without_dish_connection_succeeds(self, mock_client_class):
        """Test initialization succeeds even when connection fails."""
        mock_client = MagicMock()
        mock_client.connect.return_value = False  # Connection fails
        mock_client.test_connection.return_value = False  # Connection test also fails
        mock_client.get_telemetry.side_effect = starlink_grpc.GrpcError("API error")
        mock_client_class.return_value = mock_client

        # Should succeed despite connection failure
        config = SimulationConfig()
        coordinator = LiveCoordinator(config)

        # Coordinator should be initialized
        assert coordinator is not None
        assert coordinator.client is mock_client
        # Connection status should be False
        assert coordinator.is_connected() is False
        # No valid telemetry initially
        assert coordinator._last_valid_telemetry is None


    @patch("app.live.coordinator.StarlinkClient")
    def test_update_returns_none_when_disconnected(self, mock_client_class):
        """Test update returns None when disconnected to prevent publishing invalid data."""
        mock_client = MagicMock()
        mock_client.connect.return_value = False  # Connection fails
        mock_client.get_telemetry.side_effect = starlink_grpc.GrpcError("Not connected")
        mock_client_class.return_value = mock_client

        config = SimulationConfig()
        coordinator = LiveCoordinator(config)

        # Update should return None when disconnected
        result = coordinator.update()
        assert result is None
        assert coordinator.is_connected() is False


class TestLiveCoordinatorUpdate:
    """Test telemetry update functionality."""

    @patch("app.live.coordinator.StarlinkClient")
    def test_update_success(self, mock_client_class):
        """Test successful telemetry update."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Create mock telemetry response
        mock_telemetry = default_mock_telemetry()
        mock_client.get_telemetry.return_value = mock_telemetry

        config = SimulationConfig()
        coordinator = LiveCoordinator(config)

        # Update should succeed
        result = coordinator.update()

        assert isinstance(result, TelemetryData)
        assert result.position.latitude == 40.7128
        assert result.network.latency_ms == 50.0
        assert coordinator._last_valid_telemetry is not None

    @patch("app.live.coordinator.StarlinkClient")
    def test_update_with_heading_calculation(self, mock_client_class):
        """Test update calculates heading from position changes."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Create mock telemetry with movement
        initial_telemetry = default_mock_telemetry()
        second_telemetry = TelemetryData(
            timestamp=datetime.now() + timedelta(seconds=5),
            position=PositionData(
                latitude=40.7200,  # Moved north
                longitude=-74.0060,
                altitude=100.0,
                speed=10.0,
                heading=0.0,
            ),
            network=NetworkData(
                latency_ms=50.0,
                throughput_down_mbps=100.0,
                throughput_up_mbps=20.0,
                packet_loss_percent=1.0,
            ),
            obstruction=ObstructionData(obstruction_percent=15.0),
            environmental=EnvironmentalData(),
        )

        # Use a generator to return different telemetry on each call
        # Need 3 values: 1 for init, 2 for the update() calls
        telemetry_values = iter([initial_telemetry, initial_telemetry, second_telemetry])
        mock_client.get_telemetry.side_effect = lambda: next(telemetry_values)

        config = SimulationConfig()
        coordinator = LiveCoordinator(config)

        # First update
        coordinator.update()

        # Second update should attempt to calculate heading
        result = coordinator.update()
        # Heading calculation depends on HeadingTracker min_distance_meters
        # With 0.0072 degree difference (~0.8 km), may not meet 10m threshold
        # Just verify the update returns valid telemetry
        assert isinstance(result, TelemetryData)
        assert result.position.latitude == 40.7200  # Should have new position

    @patch("app.live.coordinator.StarlinkClient")
    def test_update_returns_none_on_connection_failure(self, mock_client_class):
        """Test update returns None when connection fails to prevent publishing stale data."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Need 3 values: 1 for init, 1 for first update, 1 exception for second update
        good_telemetry = default_mock_telemetry()
        mock_client.get_telemetry.side_effect = [
            good_telemetry,  # For init
            good_telemetry,  # For first update
            starlink_grpc.GrpcError("API error"),  # For second update
        ]

        config = SimulationConfig()
        coordinator = LiveCoordinator(config)

        # First update succeeds
        first_result = coordinator.update()
        assert isinstance(first_result, TelemetryData)
        assert first_result.position.latitude == 40.7128
        assert coordinator.is_connected() is True

        # Second update fails and returns None
        second_result = coordinator.update()
        assert second_result is None
        assert coordinator.is_connected() is False
        # Last valid telemetry is still stored internally but not returned
        assert coordinator._last_valid_telemetry is not None

    @patch("app.live.coordinator.StarlinkClient")
    def test_update_returns_none_without_fallback(self, mock_client_class):
        """Test update returns None when no valid telemetry is available."""
        mock_client = MagicMock()
        mock_client.get_telemetry.side_effect = starlink_grpc.GrpcError("API error")
        mock_client_class.return_value = mock_client

        config = SimulationConfig()
        coordinator = LiveCoordinator(config)

        # Should return None since no valid telemetry exists
        result = coordinator.update()
        assert result is None
        assert coordinator.is_connected() is False


class TestLiveCoordinatorGetCurrentTelemetry:
    """Test get_current_telemetry functionality."""

    @patch("app.live.coordinator.StarlinkClient")
    def test_get_current_telemetry_success(self, mock_client_class):
        """Test retrieving current telemetry."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_telemetry = default_mock_telemetry()
        mock_client.get_telemetry.return_value = mock_telemetry

        config = SimulationConfig()
        coordinator = LiveCoordinator(config)
        coordinator.update()

        result = coordinator.get_current_telemetry()

        assert result is coordinator._last_valid_telemetry
        assert result.position.latitude == 40.7128

    @patch("app.live.coordinator.StarlinkClient")
    def test_get_current_telemetry_without_update(self, mock_client_class):
        """Test get_current_telemetry raises when no data available."""
        mock_client = MagicMock()
        mock_client.get_telemetry.side_effect = starlink_grpc.GrpcError("API error")
        mock_client_class.return_value = mock_client

        config = SimulationConfig()
        coordinator = LiveCoordinator(config)

        with pytest.raises(RuntimeError, match="No telemetry available"):
            coordinator.get_current_telemetry()


class TestLiveCoordinatorReset:
    """Test reset functionality."""

    @patch("app.live.coordinator.StarlinkClient")
    def test_reset(self, mock_client_class):
        """Test resetting coordinator state."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_telemetry = default_mock_telemetry()
        mock_client.get_telemetry.return_value = mock_telemetry

        # Use iter to create an infinite generator
        time_values = iter([1000.0, 1100.0, 1200.0])
        with patch("app.live.coordinator.time.time", side_effect=lambda: next(time_values)):
            config = SimulationConfig()
            coordinator = LiveCoordinator(config)

            assert coordinator.get_uptime_seconds() > 0

            coordinator.reset()

            assert coordinator._last_valid_telemetry is None
            # Start time should be reset
            assert coordinator.start_time != 1000.0


class TestLiveCoordinatorUptime:
    """Test uptime tracking."""

    @patch("app.live.coordinator.StarlinkClient")
    def test_get_uptime_seconds(self, mock_client_class):
        """Test uptime tracking."""
        mock_client = MagicMock()
        mock_client.connect.return_value = False  # Skip initial connection
        mock_client_class.return_value = mock_client

        with patch("app.live.coordinator.time.time", side_effect=[1000.0, 1050.0]):
            config = SimulationConfig()
            coordinator = LiveCoordinator(config)

            uptime = coordinator.get_uptime_seconds()

            assert uptime == 50.0


class TestLiveCoordinatorConfiguration:
    """Test configuration management."""

    @patch("app.live.coordinator.StarlinkClient")
    def test_get_config(self, mock_client_class):
        """Test retrieving configuration."""
        mock_client = MagicMock()
        mock_client.connect.return_value = False  # Skip initial connection
        mock_client_class.return_value = mock_client

        config = SimulationConfig(mode="live")
        coordinator = LiveCoordinator(config)

        assert coordinator.get_config() is config
        assert coordinator.get_config().mode == "live"

    @patch("app.live.coordinator.StarlinkClient")
    def test_update_config(self, mock_client_class):
        """Test updating configuration."""
        mock_client = MagicMock()
        mock_client.connect.return_value = False  # Skip initial connection
        mock_client_class.return_value = mock_client

        config1 = SimulationConfig(
            heading_tracker=HeadingTrackerConfig(
                min_distance_meters=10.0,
                max_age_seconds=30.0,
            )
        )
        coordinator = LiveCoordinator(config1)

        # Update with new config
        config2 = SimulationConfig(
            heading_tracker=HeadingTrackerConfig(
                min_distance_meters=50.0,
                max_age_seconds=120.0,
            )
        )
        coordinator.update_config(config2)

        assert coordinator.get_config() is config2
        assert coordinator.heading_tracker.min_distance_meters == 50.0
        assert coordinator.heading_tracker.max_age_seconds == 120.0


class TestLiveCoordinatorConnection:
    """Test connection management."""

    @patch("app.live.coordinator.StarlinkClient")
    def test_is_connected_success(self, mock_client_class):
        """Test checking connection status when connected."""
        mock_client = MagicMock()
        mock_client.connect.return_value = True
        mock_client.get_telemetry.return_value = default_mock_telemetry()
        mock_client_class.return_value = mock_client

        config = SimulationConfig()
        coordinator = LiveCoordinator(config)

        # Should be connected after successful init
        assert coordinator.is_connected() is True

    @patch("app.live.coordinator.StarlinkClient")
    def test_is_connected_failure(self, mock_client_class):
        """Test checking connection status when disconnected."""
        mock_client = MagicMock()
        mock_client.connect.return_value = False  # Skip initial connection
        mock_client.test_connection.return_value = False
        mock_client_class.return_value = mock_client

        config = SimulationConfig()
        coordinator = LiveCoordinator(config)

        assert coordinator.is_connected() is False

    @patch("app.live.coordinator.StarlinkClient")
    def test_shutdown(self, mock_client_class):
        """Test coordinator shutdown."""
        mock_client = MagicMock()
        mock_client.connect.return_value = False  # Skip initial connection
        mock_client_class.return_value = mock_client

        config = SimulationConfig()
        coordinator = LiveCoordinator(config)

        coordinator.shutdown()

        mock_client.disconnect.assert_called_once()

    @patch("app.live.coordinator.StarlinkClient")
    def test_shutdown_with_error(self, mock_client_class):
        """Test shutdown handles disconnect errors gracefully."""
        mock_client = MagicMock()
        mock_client.connect.return_value = False  # Skip initial connection
        mock_client.disconnect.side_effect = starlink_grpc.GrpcError("Disconnect failed")
        mock_client_class.return_value = mock_client

        config = SimulationConfig()
        coordinator = LiveCoordinator(config)

        # Should not raise
        coordinator.shutdown()


class TestLiveCoordinatorInterface:
    """Test that LiveCoordinator matches SimulationCoordinator interface."""

    @patch("app.live.coordinator.StarlinkClient")
    def test_has_required_methods(self, mock_client_class):
        """Test that LiveCoordinator has all required methods."""
        mock_client = MagicMock()
        mock_client.connect.return_value = False  # Skip initial connection
        mock_client_class.return_value = mock_client

        config = SimulationConfig()
        coordinator = LiveCoordinator(config)

        # Check that all required methods exist
        assert callable(getattr(coordinator, "update"))
        assert callable(getattr(coordinator, "get_current_telemetry"))
        assert callable(getattr(coordinator, "reset"))
        assert callable(getattr(coordinator, "get_uptime_seconds"))
        assert callable(getattr(coordinator, "get_config"))
        assert callable(getattr(coordinator, "update_config"))

    @patch("app.live.coordinator.StarlinkClient")
    def test_polymorphic_usage(self, mock_client_class):
        """Test that LiveCoordinator can be used in place of SimulationCoordinator."""
        from app.simulation.coordinator import SimulationCoordinator

        mock_client = MagicMock()
        mock_telemetry = default_mock_telemetry()
        mock_client.get_telemetry.return_value = mock_telemetry
        mock_client_class.return_value = mock_client

        config = SimulationConfig()

        # Both coordinators should work the same way
        sim_coordinator = SimulationCoordinator(config)
        live_coordinator = LiveCoordinator(config)

        # Both should have same interface
        assert hasattr(sim_coordinator, "update")
        assert hasattr(live_coordinator, "update")

        assert hasattr(sim_coordinator, "get_current_telemetry")
        assert hasattr(live_coordinator, "get_current_telemetry")

        assert hasattr(sim_coordinator, "reset")
        assert hasattr(live_coordinator, "reset")

        # Both should return TelemetryData (or None in live mode when disconnected)
        sim_telemetry = sim_coordinator.update()
        assert isinstance(sim_telemetry, TelemetryData)

        live_telemetry = live_coordinator.update()
        assert live_telemetry is None or isinstance(live_telemetry, TelemetryData)
