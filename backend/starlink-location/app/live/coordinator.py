"""Coordinator for live Starlink terminal data collection."""

import logging
import time
from datetime import datetime
from typing import Optional

from app.live.client import StarlinkClient
from app.models.config import SimulationConfig
from app.models.telemetry import TelemetryData
from app.services.heading_tracker import HeadingTracker

logger = logging.getLogger(__name__)


class LiveCoordinator:
    """Orchestrates live data collection from Starlink dish via gRPC.

    Mirrors the SimulationCoordinator interface but collects real telemetry
    from a Starlink terminal instead of generating simulated data.
    """

    def __init__(self, config: SimulationConfig):
        """
        Initialize live coordinator.

        Args:
            config: Simulation configuration (used for heading tracker config)

        Raises:
            ValueError: If configuration is invalid
        """
        if not isinstance(config, SimulationConfig):
            raise ValueError("config must be a SimulationConfig instance")

        self.config = config
        self.start_time = time.time()

        # Initialize Starlink client with deferred connection
        self.client = StarlinkClient(connect_immediately=False)

        # Initialize heading tracker with config values
        heading_config = config.heading_tracker
        self.heading_tracker = HeadingTracker(
            min_distance_meters=heading_config.min_distance_meters,
            max_age_seconds=heading_config.max_age_seconds,
        )

        # Last known good state for graceful degradation
        self._last_valid_telemetry: Optional[TelemetryData] = None
        self._connection_status: bool = False

        logger.info(
            "LiveCoordinator initialized with heading tracker config: "
            f"min_distance={heading_config.min_distance_meters}m, "
            f"max_age={heading_config.max_age_seconds}s"
        )

        # Try to get initial telemetry to verify connection
        try:
            if self.client.connect():
                self._last_valid_telemetry = self._collect_telemetry()
                self._connection_status = True
                logger.info("Initial telemetry collected from Starlink dish")
            else:
                logger.warning(
                    "Failed to connect to Starlink dish during initialization, "
                    "but service will continue with graceful degradation"
                )
                self._connection_status = False
        except Exception as e:
            logger.warning(
                f"Error during initial connection attempt: {type(e).__name__}: {e}, "
                "but service will continue with graceful degradation"
            )
            self._connection_status = False

    def update(self) -> Optional[TelemetryData]:
        """
        Update telemetry from Starlink dish.

        Polls the gRPC API and returns current telemetry. Returns None when
        disconnected to prevent publishing invalid data to Prometheus.

        Returns:
            TelemetryData with current metrics from dish, or None if disconnected

        Raises:
            Exception: Only on first connection attempt if it fails
        """
        try:
            telemetry = self._collect_telemetry()
            self._last_valid_telemetry = telemetry
            self._connection_status = True
            return telemetry
        except Exception as e:
            logger.warning(
                f"Failed to collect telemetry: {type(e).__name__}: {e}"
            )
            self._connection_status = False

            # Return None when disconnected to prevent publishing stale/invalid data
            # This ensures Prometheus doesn't get polluted with zeros or old values
            return None

    def _collect_telemetry(self) -> TelemetryData:
        """
        Collect complete telemetry data from Starlink dish.

        Retrieves position, network metrics, and obstruction data from the
        dish via gRPC API and packages them into TelemetryData.

        Returns:
            TelemetryData with all current metrics

        Raises:
            Exception: If gRPC communication fails
        """
        # Get comprehensive telemetry from client
        # This calls status_data, location_data, and history_stats internally
        telemetry = self.client.get_telemetry()

        # Update heading tracker with current position
        heading = self.heading_tracker.update(
            latitude=telemetry.position.latitude,
            longitude=telemetry.position.longitude,
            timestamp=telemetry.timestamp,
        )

        # Update position with calculated heading
        telemetry.position.heading = heading

        logger.debug(
            f"Telemetry collected: "
            f"lat={telemetry.position.latitude:.4f}, "
            f"lon={telemetry.position.longitude:.4f}, "
            f"heading={heading:.1f}°, "
            f"latency={telemetry.network.latency_ms:.1f}ms, "
            f"obstruction={telemetry.obstruction.obstruction_percent:.1f}%"
        )

        return telemetry

    def get_current_telemetry(self) -> TelemetryData:
        """
        Get last collected telemetry without updating.

        Returns:
            Last TelemetryData that was collected

        Raises:
            RuntimeError: If no telemetry has been collected yet
        """
        if self._last_valid_telemetry is None:
            raise RuntimeError(
                "No telemetry available. Call update() first."
            )
        return self._last_valid_telemetry

    def reset(self) -> None:
        """Reset coordinator to initial state.

        Resets heading tracker and timestamps, but maintains connection
        to Starlink dish.
        """
        self.start_time = time.time()
        self.heading_tracker.reset()
        self._last_valid_telemetry = None

        logger.info("LiveCoordinator reset to initial state")

    def get_uptime_seconds(self) -> float:
        """
        Get coordinator uptime in seconds.

        Returns:
            Uptime since coordinator was created
        """
        return time.time() - self.start_time

    @property
    def mode(self) -> str:
        """
        Get the operating mode of this coordinator.

        Returns:
            String "live" indicating this is a live coordinator
        """
        return "live"

    def get_config(self) -> SimulationConfig:
        """
        Get current configuration.

        Returns:
            SimulationConfig instance
        """
        return self.config

    def update_config(self, new_config: SimulationConfig) -> None:
        """
        Update configuration and reinitialize services.

        Updates heading tracker with new configuration values.

        Args:
            new_config: New simulation configuration
        """
        self.config = new_config

        # Reinitialize heading tracker with new config
        heading_config = new_config.heading_tracker
        self.heading_tracker = HeadingTracker(
            min_distance_meters=heading_config.min_distance_meters,
            max_age_seconds=heading_config.max_age_seconds,
        )

        logger.info(
            f"LiveCoordinator configuration updated: "
            f"heading_tracker min_distance={heading_config.min_distance_meters}m, "
            f"max_age={heading_config.max_age_seconds}s"
        )

    def is_connected(self) -> bool:
        """
        Check if connected to Starlink dish.

        Returns cached connection status updated by the background update loop.
        This is fast and non-blocking, suitable for health checks.

        Returns:
            True if connection is healthy, False otherwise
        """
        # Return cached status - updated by background update() calls
        # Don't call test_connection() here as it can block for ~10 seconds
        return self._connection_status

    def shutdown(self) -> None:
        """Shutdown coordinator and close connections.

        Closes gRPC connection to Starlink dish.
        """
        try:
            self.client.disconnect()
            logger.info("LiveCoordinator shut down successfully")
        except Exception as e:
            logger.warning(f"Error during shutdown: {e}")
