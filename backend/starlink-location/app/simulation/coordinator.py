"""Simulation coordinator for orchestrating all simulators."""

import time
from datetime import datetime
from typing import Optional

from app.models.config import SimulationConfig
from app.models.telemetry import (
    EnvironmentalData,
    TelemetryData,
)
from app.simulation.network import NetworkSimulator
from app.simulation.obstructions import ObstructionSimulator
from app.simulation.position import PositionSimulator


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

        # Last known good state for graceful degradation
        self._last_valid_telemetry: Optional[TelemetryData] = None

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

    def _generate_telemetry(self) -> TelemetryData:
        """
        Generate complete telemetry data from all simulators.

        Returns:
            TelemetryData with all current metrics
        """
        # Update position
        position_data = self.position_sim.update()

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
