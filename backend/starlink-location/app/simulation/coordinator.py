"""Simulation coordinator for orchestrating all simulators."""

import logging
import time
from datetime import datetime
from typing import Optional

from app.models.config import SimulationConfig
from app.models.telemetry import (
    EnvironmentalData,
    TelemetryData,
)
from app.services.speed_tracker import SpeedTracker
from app.simulation.network import NetworkSimulator
from app.simulation.obstructions import ObstructionSimulator
from app.simulation.position import PositionSimulator
from app.simulation.kml_follower import KMLRouteFollower
from app.core.metrics import (
    starlink_route_progress_percent,
    starlink_current_waypoint_index,
)

logger = logging.getLogger(__name__)


class SimulationCoordinator:
    """Orchestrates all simulators and maintains state."""

    def __init__(self, config: SimulationConfig):
        """
        Initialize simulation coordinator.

        Args:
            config: Simulation configuration
        """
        self.config = config
        self.start_time = time.time()

        # Initialize all simulators
        self.position_sim = PositionSimulator(
            config.route,
            config.position
        )
        self.network_sim = NetworkSimulator(config.network)
        self.obstruction_sim = ObstructionSimulator(
            config.obstruction,
            config.network
        )

        # Initialize speed tracker for GPS-based speed calculation
        # Uses 120-second smoothing window to match ETA calculator
        self.speed_tracker = SpeedTracker(smoothing_duration_seconds=120.0)

        # Last known good state for graceful degradation
        self._last_valid_telemetry: Optional[TelemetryData] = None

        # Route Manager for KML route integration (Phase 5 feature)
        self.route_manager = None
        self._previous_active_route_id = None  # Track route changes

        # Get initial telemetry
        self._last_valid_telemetry = self._generate_telemetry()

    def update(self) -> TelemetryData:
        """
        Update all simulators and return current telemetry.

        Uses graceful degradation: returns last known good values on errors.

        Returns:
            TelemetryData with current simulated metrics
        """
        try:
            # Check if route has changed (for KML route following)
            self._update_route_following()

            telemetry = self._generate_telemetry()
            self._last_valid_telemetry = telemetry
            return telemetry
        except Exception as e:
            # Graceful degradation: return last known good state
            if self._last_valid_telemetry:
                # Update timestamp but return old data
                return TelemetryData(
                    timestamp=datetime.now(),
                    position=self._last_valid_telemetry.position,
                    network=self._last_valid_telemetry.network,
                    obstruction=self._last_valid_telemetry.obstruction,
                    environmental=self._last_valid_telemetry.environmental
                )
            else:
                # Re-raise if no fallback available
                raise

    def _update_route_following(self) -> None:
        """
        Check for active route and update position simulator accordingly.

        This is called each update cycle to check if the active route has changed.
        """
        if not self.route_manager:
            return

        active_route = self.route_manager.get_active_route()
        current_route_id = active_route.metadata.file_path if active_route else None

        # Check if route has changed
        if current_route_id != self._previous_active_route_id:
            if active_route:
                # New route activated
                logger.info(f"Route activated in simulator: {active_route.metadata.name}")
                follower = KMLRouteFollower(active_route)
                completion_behavior = self.config.route.completion_behavior
                self.position_sim.set_route_follower(follower, completion_behavior)
                self._previous_active_route_id = current_route_id
            else:
                # Route deactivated
                logger.info("Route deactivated in simulator")
                self.position_sim.set_route_follower(None)
                self._previous_active_route_id = None

    def _update_route_metrics(self) -> None:
        """
        Update route progress metrics in Prometheus.

        Called each cycle if route following is active.
        """
        if not self.position_sim.route_follower:
            # No active route, clear metrics
            return

        # Get active route info
        route_name = self.position_sim.route_follower.get_route_name()
        progress = self.position_sim.progress
        progress_percent = progress * 100.0

        # Update metrics with route name label
        starlink_route_progress_percent.labels(route_name=route_name).set(
            progress_percent
        )

        # Get waypoint index from the route (based on progress and number of points)
        total_points = self.position_sim.route_follower.get_point_count()
        waypoint_index = min(int(progress * (total_points - 1)), total_points - 1)

        starlink_current_waypoint_index.labels(route_name=route_name).set(
            waypoint_index
        )

    def _generate_telemetry(self) -> TelemetryData:
        """
        Generate complete telemetry data from all simulators.

        Returns:
            TelemetryData with all current metrics
        """
        # Update position
        position_data = self.position_sim.update()

        # Update speed tracker with current position (GPS-based speed calculation)
        # This replaces the generated speed from position simulator
        speed = self.speed_tracker.update(
            latitude=position_data.latitude,
            longitude=position_data.longitude,
            timestamp=time.time(),
        )

        # Update network
        network_data = self.network_sim.update()

        # Update obstruction (with network latency correlation)
        obstruction_data = self.obstruction_sim.update(
            network_data.latency_ms
        )

        # Calculate environmental data
        uptime_seconds = time.time() - self.start_time

        # Signal quality inversely correlates with obstruction
        signal_quality = max(0.0, 100.0 - obstruction_data.obstruction_percent)

        environmental_data = EnvironmentalData(
            signal_quality_percent=signal_quality,
            uptime_seconds=uptime_seconds,
            temperature_celsius=None  # Could be added to config
        )

        # Update position with calculated speed (instead of generated speed)
        position_data.speed = speed

        # Update route progress metrics if route following is active
        self._update_route_metrics()

        return TelemetryData(
            timestamp=datetime.now(),
            position=position_data,
            network=network_data,
            obstruction=obstruction_data,
            environmental=environmental_data
        )

    def get_current_telemetry(self) -> TelemetryData:
        """
        Get last generated telemetry without updating.

        Returns:
            Last TelemetryData that was generated
        """
        if self._last_valid_telemetry is None:
            return self._generate_telemetry()
        return self._last_valid_telemetry

    def reset(self) -> None:
        """Reset all simulators to initial state."""
        self.start_time = time.time()
        self.position_sim.reset()
        self.network_sim.reset()
        self.obstruction_sim.reset()
        self.speed_tracker.reset()
        self._last_valid_telemetry = self._generate_telemetry()

    def set_position_progress(self, progress: float) -> None:
        """
        Set position progress along route (0.0 to 1.0).

        Args:
            progress: Progress value
        """
        self.position_sim.set_progress(progress)

    def get_uptime_seconds(self) -> float:
        """
        Get simulation uptime in seconds.

        Returns:
            Uptime in seconds
        """
        return time.time() - self.start_time

    @property
    def mode(self) -> str:
        """
        Get the operating mode of this coordinator.

        Returns:
            String "simulation" indicating this is a simulation coordinator
        """
        return "simulation"

    def get_config(self) -> SimulationConfig:
        """
        Get current simulation configuration.

        Returns:
            SimulationConfig instance
        """
        return self.config

    def update_config(self, new_config: SimulationConfig) -> None:
        """
        Update configuration and reinitialize simulators.

        Args:
            new_config: New simulation configuration
        """
        self.config = new_config

        # Reinitialize simulators with new config
        self.position_sim = PositionSimulator(
            new_config.route,
            new_config.position
        )
        self.network_sim = NetworkSimulator(new_config.network)
        self.obstruction_sim = ObstructionSimulator(
            new_config.obstruction,
            new_config.network
        )

        # Reset start time
        self.start_time = time.time()
        self._last_valid_telemetry = self._generate_telemetry()

    def set_route_manager(self, manager) -> None:
        """
        Set the RouteManager instance for KML route following.

        Args:
            manager: RouteManager instance for accessing active routes
        """
        self.route_manager = manager
        logger.info("RouteManager injected into SimulationCoordinator")
        # Update route following if manager is set and route is active
        self._update_route_following()
