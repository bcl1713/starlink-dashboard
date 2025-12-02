"""Obstruction simulator for realistic signal blockage."""

import random

from app.models.config import ObstructionConfig, NetworkConfig
from app.models.telemetry import ObstructionData


class ObstructionSimulator:
    """Simulator for obstruction percentage with correlation to network metrics."""

    def __init__(
        self, obstruction_config: ObstructionConfig, network_config: NetworkConfig
    ):
        """
        Initialize obstruction simulator.

        Args:
            obstruction_config: Obstruction configuration
            network_config: Network configuration (for correlation)
        """
        self.obstruction_config = obstruction_config
        self.network_config = network_config

        # Initialize state
        self.current_obstruction = (
            obstruction_config.min_percent + obstruction_config.max_percent
        ) / 2.0

    def update(self, network_latency_ms: float) -> ObstructionData:
        """
        Update obstruction simulator with correlation to network latency.

        Higher obstructions correlate with higher latency.

        Args:
            network_latency_ms: Current network latency in milliseconds

        Returns:
            ObstructionData with current obstruction percentage
        """
        self._update_obstruction(network_latency_ms)

        return ObstructionData(obstruction_percent=self.current_obstruction)

    def _update_obstruction(self, network_latency_ms: float) -> None:
        """
        Update obstruction with time-based variation and correlation.

        Args:
            network_latency_ms: Current network latency for correlation
        """
        config = self.obstruction_config

        # Base variation
        variation = random.uniform(-config.variation_rate, config.variation_rate)
        self.current_obstruction += variation

        # Correlation with network latency (higher latency -> higher obstruction)
        # Map latency to obstruction impact (0 to 1 scale)
        network_config = self.network_config
        latency_range = network_config.latency_max_ms - network_config.latency_min_ms
        latency_normalized = (
            ((network_latency_ms - network_config.latency_min_ms) / latency_range)
            if latency_range > 0
            else 0.0
        )

        # Add correlation (up to 5% of obstruction range)
        obstruction_range = config.max_percent - config.min_percent
        correlation_impact = obstruction_range * 0.05 * latency_normalized
        self.current_obstruction += correlation_impact

        # Clamp to valid range
        self.current_obstruction = max(
            config.min_percent, min(config.max_percent, self.current_obstruction)
        )

    def reset(self) -> None:
        """Reset simulator to initial state."""
        self.current_obstruction = (
            self.obstruction_config.min_percent + self.obstruction_config.max_percent
        ) / 2.0
