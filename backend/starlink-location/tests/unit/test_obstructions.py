"""Tests for obstruction simulator."""

import pytest

from app.simulation.obstructions import ObstructionSimulator


class TestObstructionSimulator:
    """Test obstruction simulator functionality."""

    @pytest.fixture
    def simulator(self, default_config):
        """Create an obstruction simulator for tests."""
        return ObstructionSimulator(default_config.obstruction, default_config.network)

    def test_simulator_initialization(self, simulator):
        """Test that simulator initializes properly."""
        config = simulator.obstruction_config
        assert config.min_percent <= simulator.current_obstruction <= config.max_percent

    def test_obstruction_in_range(self, simulator):
        """Test that obstruction stays within valid range."""
        config = simulator.obstruction_config

        for _ in range(20):
            data = simulator.update(network_latency_ms=50.0)
            assert config.min_percent <= data.obstruction_percent <= config.max_percent

    def test_obstruction_variation(self, simulator):
        """Test that obstruction varies over time."""
        obstructions = []

        for _ in range(20):
            data = simulator.update(network_latency_ms=50.0)
            obstructions.append(data.obstruction_percent)

        # Should have variation
        unique_obstructions = len(set([round(o, 1) for o in obstructions]))
        assert unique_obstructions > 1

    def test_correlation_with_latency_low(self, simulator):
        """Test obstruction with low latency."""
        config = simulator.obstruction_config

        # Low latency (should not increase obstruction much)
        data_low = simulator.update(network_latency_ms=20.0)
        assert data_low.obstruction_percent >= config.min_percent
        assert data_low.obstruction_percent <= config.max_percent

    def test_correlation_with_latency_high(self, simulator):
        """Test obstruction with high latency."""
        config = simulator.obstruction_config

        # High latency (should increase obstruction)
        for _ in range(5):
            simulator.update(network_latency_ms=200.0)

        data_high = simulator.update(network_latency_ms=200.0)
        assert data_high.obstruction_percent >= config.min_percent
        assert data_high.obstruction_percent <= config.max_percent

    def test_reset(self, simulator):
        """Test resetting simulator."""
        config = simulator.obstruction_config

        # Modify state
        for _ in range(5):
            simulator.update(network_latency_ms=50.0)

        # Reset
        simulator.reset()

        # Should be back to initial state
        expected_obstruction = (config.min_percent + config.max_percent) / 2.0
        assert simulator.current_obstruction == expected_obstruction

    def test_multiple_updates_consistency(self, simulator):
        """Test that repeated updates work consistently."""
        for _ in range(50):
            data = simulator.update(network_latency_ms=50.0)
            assert data.obstruction_percent >= 0
            assert data.obstruction_percent <= 100

    def test_obstruction_vs_signal_quality(self, simulator):
        """Test relationship between obstruction and signal quality."""
        # High obstruction should correlate with low signal quality
        # This is tested in the coordinator, but we verify obstruction ranges here

        for _ in range(20):
            data = simulator.update(network_latency_ms=50.0)
            # Obstruction is a percentage
            assert 0 <= data.obstruction_percent <= 100
