"""Unit tests for LiveCoordinator.

Tests cover telemetry collection, heading calculation, error handling,
and graceful degradation using mocked StarlinkClient.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

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


class TestLiveCoordinatorInitialization:
    """Test LiveCoordinator initialization."""

    @patch("app.live.coordinator.StarlinkClient")
    def test_init_success(self, mock_client_class):
        """Test successful initialization."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        with patch("app.live.coordinator.time.time", return_value=1000.0):
            config = SimulationConfig()
            coordinator = LiveCoordinator(config)

        assert coordinator.config is config
        assert coordinator.start_time == 1000.0
        assert coordinator.client is mock_client
        assert coordinator.heading_tracker is not None
        assert coordinator.heading_tracker.min_distance_meters == 10.0
        assert coordinator.heading_tracker.max_age_seconds == 30.0

    @patch("app.live.coordinator.StarlinkClient")
    def test_init_with_custom_heading_config(self, mock_client_class):
        """Test initialization with custom heading tracker config."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

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
    def test_init_with_failed_initial_telemetry(self, mock_client_class):
        """Test initialization handles failed initial telemetry collection."""
        mock_client = MagicMock()
        mock_client.get_telemetry.side_effect = Exception("API error")
        mock_client_class.return_value = mock_client

        # Should not raise, just log warning
        config = SimulationConfig()
        coordinator = LiveCoordinator(config)

        assert coordinator._last_valid_telemetry is None


class TestLiveCoordinatorUpdate:
    """Test telemetry update functionality."""

    @patch("app.live.coordinator.StarlinkClient")
    def test_update_success(self, mock_client_class):
        """Test successful telemetry update."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Create mock telemetry response
        mock_telemetry = TelemetryData(
            timestamp=datetime.now(),
            position=PositionData(
                latitude=40.7128,
                longitude=-74.0060,
                altitude=100.0,
                speed=0.0,
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
        mock_telemetry = TelemetryData(
            timestamp=datetime.now(),
            position=PositionData(
                latitude=40.7128,
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

        # First call returns initial position
        mock_client.get_telemetry.side_effect = [
            mock_telemetry,
            TelemetryData(
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
            ),
        ]

        config = SimulationConfig()
        coordinator = LiveCoordinator(config)

        # First update
        coordinator.update()

        # Second update should calculate heading
        result = coordinator.update()
        assert result.position.heading > 0  # Should have calculated heading

    @patch("app.live.coordinator.StarlinkClient")
    def test_update_graceful_degradation(self, mock_client_class):
        """Test graceful degradation when update fails."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # First call succeeds
        good_telemetry = TelemetryData(
            timestamp=datetime.now(),
            position=PositionData(
                latitude=40.7128,
                longitude=-74.0060,
                altitude=100.0,
                speed=0.0,
                heading=0.0,
            ),
            network=NetworkData(
                latency_ms=50.0,
                throughput_down_mbps=100.0,
                throughput_up_mbps=20.0,
                packet_loss_percent=1.0,
            ),
            obstruction=ObstructionData(obstruction_percent=15.0),
            environmental=EnvironmentalData(uptime_seconds=100.0),
        )
        mock_client.get_telemetry.side_effect = [
            good_telemetry,
            Exception("API error"),
        ]

        config = SimulationConfig()
        coordinator = LiveCoordinator(config)

        # First update succeeds
        coordinator.update()

        # Second update fails but returns last good telemetry
        result = coordinator.update()

        assert isinstance(result, TelemetryData)
        assert result.position.latitude == 40.7128
        # Timestamp should be updated even though data is old
        assert result.timestamp > good_telemetry.timestamp

    @patch("app.live.coordinator.StarlinkClient")
    def test_update_fails_without_fallback(self, mock_client_class):
        """Test update raises when no fallback available."""
        mock_client = MagicMock()
        mock_client.get_telemetry.side_effect = Exception("API error")
        mock_client_class.return_value = mock_client

        config = SimulationConfig()
        coordinator = LiveCoordinator(config)

        # Should raise since no valid telemetry exists
        with pytest.raises(Exception):
            coordinator.update()


class TestLiveCoordinatorGetCurrentTelemetry:
    """Test get_current_telemetry functionality."""

    @patch("app.live.coordinator.StarlinkClient")
    def test_get_current_telemetry_success(self, mock_client_class):
        """Test retrieving current telemetry."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_telemetry = TelemetryData(
            timestamp=datetime.now(),
            position=PositionData(
                latitude=40.7128,
                longitude=-74.0060,
                altitude=100.0,
                speed=0.0,
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
        mock_client.get_telemetry.side_effect = Exception("API error")
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

        mock_telemetry = TelemetryData(
            timestamp=datetime.now(),
            position=PositionData(
                latitude=40.7128,
                longitude=-74.0060,
                altitude=100.0,
                speed=0.0,
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
        mock_client.get_telemetry.return_value = mock_telemetry

        with patch("app.live.coordinator.time.time", side_effect=[1000.0, 1100.0]):
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
        mock_client_class.return_value = mock_client

        config = SimulationConfig(mode="live")
        coordinator = LiveCoordinator(config)

        assert coordinator.get_config() is config
        assert coordinator.get_config().mode == "live"

    @patch("app.live.coordinator.StarlinkClient")
    def test_update_config(self, mock_client_class):
        """Test updating configuration."""
        mock_client = MagicMock()
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
        mock_client.test_connection.return_value = True
        mock_client_class.return_value = mock_client

        config = SimulationConfig()
        coordinator = LiveCoordinator(config)

        assert coordinator.is_connected() is True
        mock_client.test_connection.assert_called_once()

    @patch("app.live.coordinator.StarlinkClient")
    def test_is_connected_failure(self, mock_client_class):
        """Test checking connection status when disconnected."""
        mock_client = MagicMock()
        mock_client.test_connection.return_value = False
        mock_client_class.return_value = mock_client

        config = SimulationConfig()
        coordinator = LiveCoordinator(config)

        assert coordinator.is_connected() is False

    @patch("app.live.coordinator.StarlinkClient")
    def test_shutdown(self, mock_client_class):
        """Test coordinator shutdown."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        config = SimulationConfig()
        coordinator = LiveCoordinator(config)

        coordinator.shutdown()

        mock_client.disconnect.assert_called_once()

    @patch("app.live.coordinator.StarlinkClient")
    def test_shutdown_with_error(self, mock_client_class):
        """Test shutdown handles disconnect errors gracefully."""
        mock_client = MagicMock()
        mock_client.disconnect.side_effect = Exception("Disconnect failed")
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
        mock_telemetry = TelemetryData(
            timestamp=datetime.now(),
            position=PositionData(
                latitude=40.7128,
                longitude=-74.0060,
                altitude=100.0,
                speed=0.0,
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

        # Both should return TelemetryData
        sim_telemetry = sim_coordinator.update()
        assert isinstance(sim_telemetry, TelemetryData)

        live_telemetry = live_coordinator.update()
        assert isinstance(live_telemetry, TelemetryData)
