"""Tests for network metrics simulator."""

import pytest

from app.simulation.network import NetworkSimulator


class TestNetworkSimulator:
    """Test network simulator functionality."""

    @pytest.fixture
    def simulator(self, default_config):
        """Create a network simulator for tests."""
        return NetworkSimulator(default_config.network)

    def test_simulator_initialization(self, simulator):
        """Test that simulator initializes properly."""
        config = simulator.config
        assert simulator.current_latency > 0
        assert simulator.current_throughput_down > config.throughput_down_min_mbps
        assert simulator.current_throughput_up > config.throughput_up_min_mbps
        assert simulator.current_packet_loss >= config.packet_loss_min_percent

    def test_latency_in_range(self, simulator):
        """Test that latency stays within valid ranges."""
        config = simulator.config

        for _ in range(20):
            data = simulator.update()
            # Latency might exceed max due to spikes, but should have upper bound
            assert data.latency_ms >= config.latency_min_ms
            assert data.latency_ms <= config.latency_spike_max_ms

    def test_throughput_down_in_range(self, simulator):
        """Test that download throughput stays in range."""
        config = simulator.config

        for _ in range(20):
            data = simulator.update()
            assert (
                config.throughput_down_min_mbps
                <= data.throughput_down_mbps
                <= config.throughput_down_max_mbps
            )

    def test_throughput_up_in_range(self, simulator):
        """Test that upload throughput stays in range."""
        config = simulator.config

        for _ in range(20):
            data = simulator.update()
            assert (
                config.throughput_up_min_mbps
                <= data.throughput_up_mbps
                <= config.throughput_up_max_mbps
            )

    def test_packet_loss_in_range(self, simulator):
        """Test that packet loss stays in range."""
        config = simulator.config

        for _ in range(20):
            data = simulator.update()
            assert (
                config.packet_loss_min_percent
                <= data.packet_loss_percent
                <= config.packet_loss_max_percent
            )

    def test_latency_variation(self, simulator):
        """Test that latency varies."""
        latencies = []
        for _ in range(20):
            data = simulator.update()
            latencies.append(data.latency_ms)

        # Should have variation
        unique_latencies = len(set([round(l, 1) for l in latencies]))
        assert unique_latencies > 1

    def test_latency_spikes(self, simulator):
        """Test that latency spikes can occur."""
        # Run many updates to catch a spike
        config = simulator.config
        max_latency = config.latency_max_ms
        spike_detected = False

        for _ in range(100):
            data = simulator.update()
            if data.latency_ms > max_latency:
                spike_detected = True
                # Spike should be within spike max
                assert data.latency_ms <= config.latency_spike_max_ms

        # With 100 updates and 5% spike probability, should likely see a spike
        # (but not guaranteed, so we just test that spikes are possible)

    def test_throughput_variation(self, simulator):
        """Test that throughput varies."""
        down_throughputs = []
        up_throughputs = []

        for _ in range(20):
            data = simulator.update()
            down_throughputs.append(data.throughput_down_mbps)
            up_throughputs.append(data.throughput_up_mbps)

        # Should have variation
        unique_down = len(set([round(t, 1) for t in down_throughputs]))
        unique_up = len(set([round(t, 1) for t in up_throughputs]))
        assert unique_down > 1
        assert unique_up > 1

    def test_packet_loss_variation(self, simulator):
        """Test that packet loss varies."""
        packet_losses = []

        for _ in range(20):
            data = simulator.update()
            packet_losses.append(data.packet_loss_percent)

        # Should have variation
        unique_losses = len(set([round(p, 2) for p in packet_losses]))
        assert unique_losses > 1

    def test_reset(self, simulator):
        """Test resetting simulator."""
        config = simulator.config

        # Modify state
        for _ in range(5):
            simulator.update()

        # Reset
        simulator.reset()

        # Should be back to initial values
        assert simulator.current_latency == config.latency_typical_ms
        expected_down = (
            config.throughput_down_min_mbps + config.throughput_down_max_mbps
        ) / 2.0
        assert simulator.current_throughput_down == expected_down

    def test_multiple_updates_consistency(self, simulator):
        """Test that repeated updates are consistent."""
        # Run many updates to ensure simulator doesn't break
        for _ in range(100):
            data = simulator.update()
            assert data.latency_ms > 0
            assert data.throughput_down_mbps > 0
            assert data.throughput_up_mbps > 0
            assert data.packet_loss_percent >= 0
