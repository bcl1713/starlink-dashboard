"""Starlink gRPC client wrapper for live terminal data collection."""

import logging
import os
from datetime import datetime
from typing import Dict, Optional, Tuple

import starlink_grpc
from grpc import RpcError

from app.models.telemetry import (
    EnvironmentalData,
    NetworkData,
    ObstructionData,
    PositionData,
    TelemetryData,
)

logger = logging.getLogger(__name__)


def _get_dish_target() -> str:
    """Get Starlink dish gRPC target from environment variables.

    Returns:
        Target string in format "host:port"
    """
    host = os.getenv("STARLINK_DISH_HOST", "192.168.100.1")
    port = os.getenv("STARLINK_DISH_PORT", "9200")
    return f"{host}:{port}"


class StarlinkClient:
    """Wrapper for starlink-grpc-tools library for real-time dish communication.

    Handles connection management, telemetry collection, and error handling
    for Starlink dish gRPC API.
    """

    def __init__(
        self,
        target: Optional[str] = None,
        timeout: float = 5.0,
        connect_immediately: bool = False,
    ):
        """Initialize Starlink client.

        Args:
            target: gRPC endpoint address and port (default: from STARLINK_DISH_HOST and STARLINK_DISH_PORT env vars)
            timeout: Connection timeout in seconds (default: 5.0)
            connect_immediately: If True, immediately connect and raise on failure (default: False)

        Raises:
            ValueError: If target or timeout are invalid
            RpcError: If connection to dish fails and connect_immediately is True
        """
        # Use provided target or get from environment variables
        if target is None:
            target = _get_dish_target()

        if not target or ":" not in target:
            raise ValueError(f"Invalid target format: {target}")
        if timeout <= 0:
            raise ValueError(f"Timeout must be positive: {timeout}")

        self.target = target
        self.timeout = timeout
        self.context: Optional[starlink_grpc.ChannelContext] = None
        self._connected = False
        self.logger = logger
        self.connect_immediately = connect_immediately

        # Connect immediately if requested (will raise on failure)
        if connect_immediately:
            self.connect()

    def is_connected(self) -> bool:
        """Check if currently connected to Starlink dish.

        Returns:
            True if connected, False otherwise
        """
        return self._connected

    def connect(self) -> bool:
        """Establish gRPC connection to Starlink dish.

        Returns:
            True if connection successful, False otherwise

        Raises:
            starlink_grpc.GrpcError: If gRPC error occurs and connect_immediately is True
            RpcError: If low-level gRPC error occurs and connect_immediately is True
        """
        if self._connected and self.context:
            return True

        try:
            self.context = starlink_grpc.ChannelContext(target=self.target)
            self._connected = True
            self.logger.info(f"Connected to Starlink dish at {self.target}")
            return True
        except (starlink_grpc.GrpcError, RpcError) as e:
            self.logger.error(
                f"Failed to connect to Starlink dish at {self.target}: {e}"
            )
            self._connected = False
            self.context = None
            # Only raise if immediate connection was required
            if self.connect_immediately:
                raise
            return False

    def disconnect(self) -> None:
        """Close gRPC connection to Starlink dish."""
        if self.context:
            try:
                self.context.close()
                self.logger.info("Disconnected from Starlink dish")
            except Exception as e:
                self.logger.warning(f"Error closing connection: {e}")
            finally:
                self.context = None
                self._connected = False

    def test_connection(self) -> bool:
        """Test connection to Starlink dish.

        This method attempts to retrieve basic status data to verify
        connectivity and dish reachability.

        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            if not self.context:
                self.connect()

            # Try to get status data as a simple health check
            starlink_grpc.status_data(context=self.context)
            self.logger.debug("Connection test successful")
            return True

        except (starlink_grpc.GrpcError, RpcError) as e:
            self.logger.warning(f"Connection test failed: {type(e).__name__}: {e}")
            self._connected = False
            return False
        except Exception as e:
            self.logger.error(
                f"Unexpected error during connection test: {type(e).__name__}: {e}"
            )
            return False

    def get_status_data(self) -> Tuple[Dict, Dict, Dict]:
        """Get device status, obstruction, and alerts from Starlink dish.

        Returns:
            Tuple of (status_dict, obstruction_dict, alert_dict)

        Raises:
            starlink_grpc.GrpcError: If gRPC error occurs
            RpcError: If low-level gRPC error occurs
        """
        if not self.context:
            self.connect()

        try:
            status, obstruction, alerts = starlink_grpc.status_data(
                context=self.context
            )
            return status, obstruction, alerts
        except (starlink_grpc.GrpcError, RpcError) as e:
            self.logger.error(f"Failed to get status data: {e}")
            raise

    def get_location_data(self) -> Dict:
        """Get GPS location data from Starlink dish.

        Returns:
            Dictionary with latitude, longitude, altitude keys

        Raises:
            starlink_grpc.GrpcError: If gRPC error occurs
            RpcError: If low-level gRPC error occurs
        """
        if not self.context:
            self.connect()

        try:
            location = starlink_grpc.location_data(context=self.context)
            return location
        except (starlink_grpc.GrpcError, RpcError) as e:
            self.logger.error(f"Failed to get location data: {e}")
            raise

    def get_history_stats(
        self, parse_samples: int = -1
    ) -> Tuple[Dict, Dict, Dict, Dict, Dict, Dict, Dict]:
        """Get historical statistics from Starlink dish.

        Args:
            parse_samples: Number of samples to parse (-1 for all)

        Returns:
            Tuple of 7 dictionaries:
            (general_dict, ping_drop_dict, ping_run_length_dict,
             ping_latency_dict, loaded_ping_latency_dict, usage_dict, power_dict)

        Raises:
            starlink_grpc.GrpcError: If gRPC error occurs
            RpcError: If low-level gRPC error occurs
        """
        if not self.context:
            self.connect()

        try:
            general, drop, run, latency, loaded, usage, power = (
                starlink_grpc.history_stats(
                    parse_samples=parse_samples,
                    context=self.context,
                )
            )
            return general, drop, run, latency, loaded, usage, power
        except (starlink_grpc.GrpcError, RpcError) as e:
            self.logger.error(f"Failed to get history stats: {e}")
            raise

    def get_telemetry(self) -> TelemetryData:
        """Get comprehensive telemetry data from Starlink dish.

        Collects position, network metrics, and obstruction data and
        packages them into a TelemetryData object.

        Returns:
            TelemetryData object with all available metrics

        Raises:
            starlink_grpc.GrpcError: If gRPC error occurs
            RpcError: If low-level gRPC error occurs
            KeyError: If expected keys are missing from API responses
        """
        if not self.context:
            self.connect()

        try:
            # Get all required data
            status, obstruction, alerts = self.get_status_data()
            location = self.get_location_data()
            general, drop, run, latency, loaded, usage, power = self.get_history_stats(
                parse_samples=10
            )

            # Extract position data
            lat = location.get("latitude")
            lon = location.get("longitude")
            alt = location.get("altitude", 0.0)

            # Handle missing GPS data
            if lat is None or lon is None:
                self.logger.warning("GPS location data not available from dish")
                lat = lat or 0.0
                lon = lon or 0.0

            # Convert altitude from meters to feet (1 meter = 3.28084 feet)
            alt_feet = float(alt) * 3.28084 if alt else 0.0

            position = PositionData(
                latitude=float(lat),
                longitude=float(lon),
                altitude=alt_feet,
                speed=0.0,  # Not available from Starlink API
                heading=0.0,  # Will be populated by HeadingTracker
            )

            # Extract network metrics
            latency_ms = status.get("pop_ping_latency_ms", 0.0)
            downlink_bps = status.get("downlink_throughput_bps", 0.0)
            uplink_bps = status.get("uplink_throughput_bps", 0.0)
            packet_loss = (
                status.get("pop_ping_drop_rate", 0.0) * 100
            )  # Convert to percentage

            network = NetworkData(
                latency_ms=float(latency_ms),
                throughput_down_mbps=float(downlink_bps / 1e6),
                throughput_up_mbps=float(uplink_bps / 1e6),
                packet_loss_percent=float(packet_loss),
            )

            # Extract obstruction data
            obstruction_fraction = obstruction.get("fraction_obstructed", 0.0)
            obstruction_pct = ObstructionData(
                obstruction_percent=float(obstruction_fraction * 100)
            )

            # Extract environmental data
            uptime = status.get("uptime", 0.0)
            temp = status.get("temperature_c")  # May not be available

            environmental = EnvironmentalData(
                signal_quality_percent=100.0,  # Not directly available
                uptime_seconds=float(uptime),
                temperature_celsius=float(temp) if temp else None,
            )

            return TelemetryData(
                timestamp=datetime.now(),
                position=position,
                network=network,
                obstruction=obstruction_pct,
                environmental=environmental,
            )

        except (starlink_grpc.GrpcError, RpcError) as e:
            self.logger.error(f"Failed to get telemetry: {e}")
            raise
        except (KeyError, TypeError, ValueError) as e:
            self.logger.error(f"Error parsing telemetry data: {e}")
            raise

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False

    def __del__(self):
        """Ensure connection is closed on garbage collection."""
        try:
            self.disconnect()
        except Exception:
            pass
