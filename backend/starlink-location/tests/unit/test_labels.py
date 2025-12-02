"""Unit tests for label helper functions."""

import pytest
from datetime import datetime
from app.core.labels import (
    get_mode_label,
    get_status_label,
    get_geographic_labels,
    apply_common_labels,
)
from app.models.telemetry import (
    TelemetryData,
    PositionData,
    NetworkData,
    ObstructionData,
    EnvironmentalData,
)


class TestGetModeLabel:
    """Tests for get_mode_label function."""

    def test_simulation_mode(self):
        """Test mode label for simulation config."""

        class MockConfig:
            mode = "simulation"

        assert get_mode_label(MockConfig()) == "simulation"

    def test_live_mode(self):
        """Test mode label for live config."""

        class MockConfig:
            mode = "live"

        assert get_mode_label(MockConfig()) == "live"


class TestGetStatusLabel:
    """Tests for get_status_label function."""

    def test_excellent_status(self):
        """Test excellent status (low latency, no packet loss)."""
        assert get_status_label(latency_ms=30.0, packet_loss_percent=0.5) == "excellent"

    def test_good_status(self):
        """Test good status (moderate latency, low packet loss)."""
        assert get_status_label(latency_ms=75.0, packet_loss_percent=2.0) == "good"

    def test_degraded_status(self):
        """Test degraded status (elevated latency or packet loss)."""
        assert get_status_label(latency_ms=120.0, packet_loss_percent=5.0) == "degraded"

    def test_poor_status_high_latency(self):
        """Test poor status from high latency."""
        assert get_status_label(latency_ms=200.0, packet_loss_percent=0.5) == "poor"

    def test_poor_status_high_packet_loss(self):
        """Test poor status from high packet loss."""
        assert get_status_label(latency_ms=30.0, packet_loss_percent=15.0) == "poor"

    def test_status_boundaries(self):
        """Test status classification at boundaries."""
        # Boundary: 50ms, <1% loss = excellent
        assert get_status_label(latency_ms=49.9, packet_loss_percent=0.9) == "excellent"
        # Boundary: 50ms, 1% loss = good (latency still <100)
        assert get_status_label(latency_ms=50.0, packet_loss_percent=1.0) == "good"


class TestGetGeographicLabels:
    """Tests for get_geographic_labels function."""

    def test_northern_eastern_hemisphere(self):
        """Test labels for northern eastern hemisphere."""
        labels = get_geographic_labels(latitude=40.7128, longitude=-74.0060)
        assert "region" in labels
        assert "zone" in labels
        assert labels["region"] == "north-west"  # Negative longitude = west

    def test_southern_eastern_hemisphere(self):
        """Test labels for southern eastern hemisphere."""
        labels = get_geographic_labels(latitude=-33.8688, longitude=151.2093)
        assert labels["region"] == "south-east"

    def test_equator_and_prime_meridian(self):
        """Test labels at equator and prime meridian."""
        labels = get_geographic_labels(latitude=0.0, longitude=0.0)
        assert "region" in labels
        assert "zone" in labels

    def test_zone_includes_coordinates(self):
        """Test that zone label includes coordinate information."""
        lat, lon = 40.7128, -74.0060
        labels = get_geographic_labels(latitude=lat, longitude=lon)
        # Zone should contain coordinate information
        assert "lat:" in labels["zone"] or "lon:" in labels["zone"]


class TestApplyCommonLabels:
    """Tests for apply_common_labels function."""

    @pytest.fixture
    def mock_telemetry(self):
        """Create a mock telemetry object."""
        return TelemetryData(
            timestamp=datetime.now(),
            position=PositionData(
                latitude=40.7128,
                longitude=-74.0060,
                altitude=100.0,
                speed=10.0,
                heading=90.0,
            ),
            network=NetworkData(
                latency_ms=50.0,
                throughput_down_mbps=100.0,
                throughput_up_mbps=20.0,
                packet_loss_percent=1.0,
            ),
            obstruction=ObstructionData(
                obstruction_percent=0.0, potential_obstructions=0
            ),
            environmental=EnvironmentalData(
                signal_quality_percent=90.0, uptime_seconds=3600.0
            ),
        )

    @pytest.fixture
    def mock_config(self):
        """Create a mock config object."""

        class MockConfig:
            mode = "simulation"

        return MockConfig()

    def test_labels_structure(self, mock_telemetry, mock_config):
        """Test that all expected labels are present."""
        labels = apply_common_labels(mock_telemetry, mock_config)

        assert "mode" in labels
        assert "status" in labels
        assert "region" in labels
        assert "zone" in labels

    def test_mode_label_included(self, mock_telemetry, mock_config):
        """Test that mode label is correct."""
        labels = apply_common_labels(mock_telemetry, mock_config)
        assert labels["mode"] == "simulation"

    def test_status_label_computed(self, mock_telemetry, mock_config):
        """Test that status label is computed from telemetry."""
        labels = apply_common_labels(mock_telemetry, mock_config)
        # With latency=50ms and packet_loss=1%, should be "good"
        assert labels["status"] == "good"

    def test_labels_with_poor_network(self, mock_telemetry, mock_config):
        """Test labels with poor network conditions."""
        # Modify telemetry to have poor conditions
        mock_telemetry.network.latency_ms = 200.0
        mock_telemetry.network.packet_loss_percent = 20.0

        labels = apply_common_labels(mock_telemetry, mock_config)
        assert labels["status"] == "poor"
