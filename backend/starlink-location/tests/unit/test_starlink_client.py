"""Unit tests for StarlinkClient wrapper.

Tests cover connection management, telemetry collection, and error handling
using mocked gRPC responses.
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.live.client import StarlinkClient
from app.models.telemetry import (
    EnvironmentalData,
    NetworkData,
    ObstructionData,
    PositionData,
    TelemetryData,
)


class TestStarlinkClientInitialization:
    """Test StarlinkClient initialization and configuration."""

    def test_init_default_target(self):
        """Test initialization with default target."""
        client = StarlinkClient()
        assert client.target == "192.168.100.1:9200"
        assert client.timeout == 5.0
        assert client.context is None
        assert client.is_connected is False

    def test_init_custom_target(self):
        """Test initialization with custom target."""
        client = StarlinkClient(target="192.168.1.100:9200")
        assert client.target == "192.168.1.100:9200"

    def test_init_custom_timeout(self):
        """Test initialization with custom timeout."""
        client = StarlinkClient(timeout=10.0)
        assert client.timeout == 10.0

    def test_init_invalid_target_no_port(self):
        """Test initialization fails with invalid target format."""
        with pytest.raises(ValueError, match="Invalid target format"):
            StarlinkClient(target="192.168.100.1")

    def test_init_invalid_target_empty(self):
        """Test initialization fails with empty target."""
        with pytest.raises(ValueError, match="Invalid target format"):
            StarlinkClient(target="")

    def test_init_invalid_timeout_zero(self):
        """Test initialization fails with zero timeout."""
        with pytest.raises(ValueError, match="Timeout must be positive"):
            StarlinkClient(timeout=0.0)

    def test_init_invalid_timeout_negative(self):
        """Test initialization fails with negative timeout."""
        with pytest.raises(ValueError, match="Timeout must be positive"):
            StarlinkClient(timeout=-1.0)


class TestStarlinkClientConnection:
    """Test connection management."""

    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_connect_success(self, mock_context_class):
        """Test successful connection."""
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context

        client = StarlinkClient()
        result = client.connect()

        assert result is True
        assert client.is_connected is True
        assert client.context is mock_context
        mock_context_class.assert_called_once()

    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_connect_already_connected(self, mock_context_class):
        """Test connect() returns True if already connected."""
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context

        client = StarlinkClient()
        client.connect()
        mock_context_class.reset_mock()

        # Second connect should return True without creating new context
        result = client.connect()

        assert result is True
        mock_context_class.assert_not_called()

    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_connect_grpc_error(self, mock_context_class):
        """Test connection failure with gRPC error."""
        import starlink_grpc

        mock_context_class.side_effect = starlink_grpc.GrpcError(
            "Connection failed"
        )

        client = StarlinkClient()
        with pytest.raises(starlink_grpc.GrpcError):
            client.connect()

        assert client.is_connected is False
        assert client.context is None

    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_disconnect_success(self, mock_context_class):
        """Test successful disconnection."""
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context

        client = StarlinkClient()
        client.connect()
        client.disconnect()

        assert client.is_connected is False
        assert client.context is None
        mock_context.close.assert_called_once()

    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_disconnect_not_connected(self, mock_context_class):
        """Test disconnect when not connected."""
        client = StarlinkClient()
        # Should not raise exception
        client.disconnect()

        assert client.is_connected is False
        assert client.context is None

    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_disconnect_close_error(self, mock_context_class):
        """Test disconnect handles close errors gracefully."""
        mock_context = MagicMock()
        mock_context.close.side_effect = Exception("Close failed")
        mock_context_class.return_value = mock_context

        client = StarlinkClient()
        client.connect()
        # Should not raise exception
        client.disconnect()

        assert client.is_connected is False
        assert client.context is None


class TestStarlinkClientConnectionTest:
    """Test connection test method."""

    @patch("app.live.client.starlink_grpc.status_data")
    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_test_connection_success(self, mock_context_class, mock_status):
        """Test successful connection test."""
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context
        mock_status.return_value = ({"uptime": 1000}, {}, {})

        client = StarlinkClient()
        result = client.test_connection()

        assert result is True
        mock_status.assert_called_once()

    @patch("app.live.client.starlink_grpc.status_data")
    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_test_connection_grpc_error(self, mock_context_class, mock_status):
        """Test connection test fails with gRPC error."""
        import starlink_grpc

        mock_context = MagicMock()
        mock_context_class.return_value = mock_context
        mock_status.side_effect = starlink_grpc.GrpcError("Connection failed")

        client = StarlinkClient()
        result = client.test_connection()

        assert result is False
        assert client.is_connected is False

    @patch("app.live.client.starlink_grpc.status_data")
    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_test_connection_unexpected_error(
        self, mock_context_class, mock_status
    ):
        """Test connection test handles unexpected errors."""
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context
        mock_status.side_effect = ValueError("Unexpected error")

        client = StarlinkClient()
        result = client.test_connection()

        assert result is False


class TestStarlinkClientStatusData:
    """Test status data retrieval."""

    @patch("app.live.client.starlink_grpc.status_data")
    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_get_status_data_success(self, mock_context_class, mock_status):
        """Test successful status data retrieval."""
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context

        status_dict = {"uptime": 1000, "pop_ping_latency_ms": 50.0}
        obstruction_dict = {"fraction_obstructed": 0.1}
        alert_dict = {}

        mock_status.return_value = (status_dict, obstruction_dict, alert_dict)

        client = StarlinkClient()
        status, obstruction, alerts = client.get_status_data()

        assert status == status_dict
        assert obstruction == obstruction_dict
        assert alerts == alert_dict

    @patch("app.live.client.starlink_grpc.status_data")
    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_get_status_data_auto_connect(
        self, mock_context_class, mock_status
    ):
        """Test status data retrieval auto-connects if needed."""
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context
        mock_status.return_value = ({}, {}, {})

        client = StarlinkClient()
        assert client.context is None

        client.get_status_data()

        assert client.context is mock_context
        mock_context_class.assert_called_once()

    @patch("app.live.client.starlink_grpc.status_data")
    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_get_status_data_grpc_error(
        self, mock_context_class, mock_status
    ):
        """Test status data retrieval fails gracefully."""
        import starlink_grpc

        mock_context = MagicMock()
        mock_context_class.return_value = mock_context
        mock_status.side_effect = starlink_grpc.GrpcError("API error")

        client = StarlinkClient()
        with pytest.raises(starlink_grpc.GrpcError):
            client.get_status_data()


class TestStarlinkClientLocationData:
    """Test location data retrieval."""

    @patch("app.live.client.starlink_grpc.location_data")
    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_get_location_data_success(
        self, mock_context_class, mock_location
    ):
        """Test successful location data retrieval."""
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context

        location_dict = {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "altitude": 100.0,
        }
        mock_location.return_value = location_dict

        client = StarlinkClient()
        location = client.get_location_data()

        assert location == location_dict

    @patch("app.live.client.starlink_grpc.location_data")
    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_get_location_data_auto_connect(
        self, mock_context_class, mock_location
    ):
        """Test location data retrieval auto-connects if needed."""
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context
        mock_location.return_value = {}

        client = StarlinkClient()
        client.get_location_data()

        mock_context_class.assert_called_once()


class TestStarlinkClientHistoryStats:
    """Test history statistics retrieval."""

    @patch("app.live.client.starlink_grpc.history_stats")
    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_get_history_stats_success(
        self, mock_context_class, mock_history
    ):
        """Test successful history stats retrieval."""
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context

        mock_history.return_value = ({}, {}, {}, {}, {}, {}, {})

        client = StarlinkClient()
        result = client.get_history_stats()

        assert len(result) == 7
        mock_history.assert_called_once_with(
            parse_samples=-1, context=mock_context
        )

    @patch("app.live.client.starlink_grpc.history_stats")
    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_get_history_stats_custom_samples(
        self, mock_context_class, mock_history
    ):
        """Test history stats with custom sample count."""
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context
        mock_history.return_value = ({}, {}, {}, {}, {}, {}, {})

        client = StarlinkClient()
        client.get_history_stats(parse_samples=50)

        mock_history.assert_called_once_with(
            parse_samples=50, context=mock_context
        )


class TestStarlinkClientTelemetry:
    """Test comprehensive telemetry retrieval."""

    @patch("app.live.client.starlink_grpc.history_stats")
    @patch("app.live.client.starlink_grpc.location_data")
    @patch("app.live.client.starlink_grpc.status_data")
    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_get_telemetry_success(
        self,
        mock_context_class,
        mock_status,
        mock_location,
        mock_history,
    ):
        """Test successful comprehensive telemetry retrieval."""
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context

        # Mock status data
        status_dict = {
            "uptime": 3600.0,
            "pop_ping_latency_ms": 50.0,
            "downlink_throughput_bps": 100e6,  # 100 Mbps
            "uplink_throughput_bps": 20e6,  # 20 Mbps
            "pop_ping_drop_rate": 0.01,  # 1%
            "temperature_c": 35.0,
        }
        obstruction_dict = {"fraction_obstructed": 0.15}
        alert_dict = {}
        mock_status.return_value = (status_dict, obstruction_dict, alert_dict)

        # Mock location data
        location_dict = {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "altitude": 100.0,
        }
        mock_location.return_value = location_dict

        # Mock history stats
        mock_history.return_value = ({}, {}, {}, {}, {}, {}, {})

        client = StarlinkClient()
        telemetry = client.get_telemetry()

        assert isinstance(telemetry, TelemetryData)
        assert telemetry.position.latitude == 40.7128
        assert telemetry.position.longitude == -74.0060
        assert telemetry.position.altitude == 100.0
        assert telemetry.network.latency_ms == 50.0
        assert telemetry.network.throughput_down_mbps == 100.0
        assert telemetry.network.throughput_up_mbps == 20.0
        assert telemetry.network.packet_loss_percent == 1.0
        assert telemetry.obstruction.obstruction_percent == 15.0
        assert telemetry.environmental.uptime_seconds == 3600.0
        assert telemetry.environmental.temperature_celsius == 35.0

    @patch("app.live.client.starlink_grpc.history_stats")
    @patch("app.live.client.starlink_grpc.location_data")
    @patch("app.live.client.starlink_grpc.status_data")
    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_get_telemetry_missing_gps(
        self,
        mock_context_class,
        mock_status,
        mock_location,
        mock_history,
    ):
        """Test telemetry retrieval with missing GPS data."""
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context

        status_dict = {
            "uptime": 3600.0,
            "pop_ping_latency_ms": 50.0,
            "downlink_throughput_bps": 100e6,
            "uplink_throughput_bps": 20e6,
            "pop_ping_drop_rate": 0.01,
        }
        mock_status.return_value = (status_dict, {}, {})

        # Location returns None for GPS
        location_dict = {"latitude": None, "longitude": None, "altitude": 0.0}
        mock_location.return_value = location_dict

        mock_history.return_value = ({}, {}, {}, {}, {}, {}, {})

        client = StarlinkClient()
        telemetry = client.get_telemetry()

        assert telemetry.position.latitude == 0.0
        assert telemetry.position.longitude == 0.0

    @patch("app.live.client.starlink_grpc.history_stats")
    @patch("app.live.client.starlink_grpc.location_data")
    @patch("app.live.client.starlink_grpc.status_data")
    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_get_telemetry_grpc_error(
        self,
        mock_context_class,
        mock_status,
        mock_location,
        mock_history,
    ):
        """Test telemetry retrieval fails gracefully on gRPC error."""
        import starlink_grpc

        mock_context = MagicMock()
        mock_context_class.return_value = mock_context
        mock_status.side_effect = starlink_grpc.GrpcError("API error")

        client = StarlinkClient()
        with pytest.raises(starlink_grpc.GrpcError):
            client.get_telemetry()

    @patch("app.live.client.starlink_grpc.history_stats")
    @patch("app.live.client.starlink_grpc.location_data")
    @patch("app.live.client.starlink_grpc.status_data")
    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_get_telemetry_missing_keys(
        self,
        mock_context_class,
        mock_status,
        mock_location,
        mock_history,
    ):
        """Test telemetry retrieval handles missing keys gracefully."""
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context

        # Minimal status dict missing expected keys
        status_dict = {}
        mock_status.return_value = (status_dict, {}, {})
        location_dict = {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "altitude": 100.0,
        }
        mock_location.return_value = location_dict
        mock_history.return_value = ({}, {}, {}, {}, {}, {}, {})

        client = StarlinkClient()
        telemetry = client.get_telemetry()

        # Should use defaults when keys are missing
        assert telemetry.network.latency_ms == 0.0
        assert telemetry.network.throughput_down_mbps == 0.0


class TestStarlinkClientContextManager:
    """Test context manager functionality."""

    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_context_manager_success(self, mock_context_class):
        """Test context manager usage."""
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context

        with StarlinkClient() as client:
            assert client.is_connected is True

        assert client.is_connected is False
        mock_context.close.assert_called_once()

    @patch("app.live.client.starlink_grpc.ChannelContext")
    def test_context_manager_with_exception(self, mock_context_class):
        """Test context manager cleans up on exception."""
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context

        try:
            with StarlinkClient() as client:
                assert client.is_connected is True
                raise ValueError("Test error")
        except ValueError:
            pass

        assert client.is_connected is False
        mock_context.close.assert_called_once()
