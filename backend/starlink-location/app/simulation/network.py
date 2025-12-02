"""Network metrics simulator for realistic network performance."""

import random

from app.models.config import NetworkConfig
from app.models.telemetry import NetworkData


class NetworkSimulator:
    """Simulator for network metrics (latency, throughput, packet loss)."""

    def __init__(self, config: NetworkConfig):
        """
        Initialize network simulator.

        Args:
            config: Network configuration parameters
        """
        self.config = config

        # Initialize state
        self.current_latency = config.latency_typical_ms
        self.current_throughput_down = (
            config.throughput_down_min_mbps + config.throughput_down_max_mbps
        ) / 2.0
        self.current_throughput_up = (
            config.throughput_up_min_mbps + config.throughput_up_max_mbps
        ) / 2.0
        self.current_packet_loss = (
            config.packet_loss_min_percent + config.packet_loss_max_percent
        ) / 2.0

    def update(self) -> NetworkData:
        """
        Update network simulator and return current metrics.

        Returns:
            NetworkData with current network metrics
        """
        self._update_latency()
        self._update_throughput_down()
        self._update_throughput_up()
        self._update_packet_loss()

        return NetworkData(
            latency_ms=self.current_latency,
            throughput_down_mbps=self.current_throughput_down,
            throughput_up_mbps=self.current_throughput_up,
            packet_loss_percent=self.current_packet_loss,
        )

    def _update_latency(self) -> None:
        """Update latency with occasional spikes."""
        config = self.config

        # Check for spike
        if random.random() < config.spike_probability:
            # Spike to higher latency
            self.current_latency = random.uniform(
                config.latency_max_ms, config.latency_spike_max_ms
            )
        else:
            # Normal latency with some variation
            latency_range = config.latency_max_ms - config.latency_min_ms
            variation = random.gauss(0, latency_range * 0.1)
            self.current_latency = config.latency_typical_ms + variation

            # Clamp to normal range
            self.current_latency = max(
                config.latency_min_ms, min(config.latency_max_ms, self.current_latency)
            )

    def _update_throughput_down(self) -> None:
        """Update download throughput with realistic variation."""
        config = self.config

        # Random walk
        throughput_change = random.uniform(-10.0, 10.0)
        self.current_throughput_down += throughput_change

        # Clamp to valid range
        self.current_throughput_down = max(
            config.throughput_down_min_mbps,
            min(config.throughput_down_max_mbps, self.current_throughput_down),
        )

    def _update_throughput_up(self) -> None:
        """Update upload throughput with realistic variation."""
        config = self.config

        # Random walk
        throughput_change = random.uniform(-2.0, 2.0)
        self.current_throughput_up += throughput_change

        # Clamp to valid range
        self.current_throughput_up = max(
            config.throughput_up_min_mbps,
            min(config.throughput_up_max_mbps, self.current_throughput_up),
        )

    def _update_packet_loss(self) -> None:
        """Update packet loss percentage."""
        config = self.config

        # Packet loss tends to vary slowly
        packet_loss_change = random.uniform(-0.5, 0.5)
        self.current_packet_loss += packet_loss_change

        # Clamp to valid range
        self.current_packet_loss = max(
            config.packet_loss_min_percent,
            min(config.packet_loss_max_percent, self.current_packet_loss),
        )

    def reset(self) -> None:
        """Reset simulator to initial state."""
        self.current_latency = self.config.latency_typical_ms
        self.current_throughput_down = (
            self.config.throughput_down_min_mbps + self.config.throughput_down_max_mbps
        ) / 2.0
        self.current_throughput_up = (
            self.config.throughput_up_min_mbps + self.config.throughput_up_max_mbps
        ) / 2.0
        self.current_packet_loss = (
            self.config.packet_loss_min_percent + self.config.packet_loss_max_percent
        ) / 2.0
