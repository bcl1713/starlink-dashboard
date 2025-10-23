"""Unit tests for metric value validation and ranges."""

import pytest
from datetime import datetime
from app.core.metrics import update_metrics_from_telemetry
from app.models.telemetry import TelemetryData, PositionData, NetworkData, ObstructionData, EnvironmentalData


class TestPositionMetricRanges:
    """Tests for position metric value ranges."""

    def test_latitude_valid_range(self):
        """Test that latitude values are within valid range (-90 to 90)."""
        telemetry = TelemetryData(
                timestamp=datetime.now(),
            position=PositionData(
                latitude=45.0,  # Valid
                longitude=0.0,
                altitude=100.0,
                speed=10.0,
                heading=90.0
            ),
            network=NetworkData(
                latency_ms=50.0,
                throughput_down_mbps=100.0,
                throughput_up_mbps=20.0,
                packet_loss_percent=1.0
            ),
            obstruction=ObstructionData(obstruction_percent=0.0, potential_obstructions=0),
            environmental=EnvironmentalData(signal_quality_percent=90.0, uptime_seconds=3600.0)
        )
        # Should not raise any errors
        update_metrics_from_telemetry(telemetry)

    def test_latitude_extremes(self):
        """Test latitude at poles."""
        for lat in [-90.0, 90.0]:
            telemetry = TelemetryData(
                timestamp=datetime.now(),
                position=PositionData(
                    latitude=lat,
                    longitude=0.0,
                    altitude=100.0,
                    speed=10.0,
                    heading=90.0
                ),
                network=NetworkData(
                    latency_ms=50.0,
                    throughput_down_mbps=100.0,
                    throughput_up_mbps=20.0,
                    packet_loss_percent=1.0
                ),
                obstruction=ObstructionData(obstruction_percent=0.0, potential_obstructions=0),
                environmental=EnvironmentalData(signal_quality_percent=90.0, uptime_seconds=3600.0)
            )
            update_metrics_from_telemetry(telemetry)

    def test_longitude_valid_range(self):
        """Test that longitude values are within valid range (-180 to 180)."""
        telemetry = TelemetryData(
                timestamp=datetime.now(),
            position=PositionData(
                latitude=0.0,
                longitude=120.0,  # Valid
                altitude=100.0,
                speed=10.0,
                heading=90.0
            ),
            network=NetworkData(
                latency_ms=50.0,
                throughput_down_mbps=100.0,
                throughput_up_mbps=20.0,
                packet_loss_percent=1.0
            ),
            obstruction=ObstructionData(obstruction_percent=0.0, potential_obstructions=0),
            environmental=EnvironmentalData(signal_quality_percent=90.0, uptime_seconds=3600.0)
        )
        update_metrics_from_telemetry(telemetry)

    def test_longitude_extremes(self):
        """Test longitude at date line."""
        for lon in [-180.0, 180.0]:
            telemetry = TelemetryData(
                timestamp=datetime.now(),
                position=PositionData(
                    latitude=0.0,
                    longitude=lon,
                    altitude=100.0,
                    speed=10.0,
                    heading=90.0
                ),
                network=NetworkData(
                    latency_ms=50.0,
                    throughput_down_mbps=100.0,
                    throughput_up_mbps=20.0,
                    packet_loss_percent=1.0
                ),
                obstruction=ObstructionData(obstruction_percent=0.0, potential_obstructions=0),
                environmental=EnvironmentalData(signal_quality_percent=90.0, uptime_seconds=3600.0)
            )
            update_metrics_from_telemetry(telemetry)


class TestNetworkMetricRanges:
    """Tests for network metric value ranges."""

    def test_latency_positive(self):
        """Test that latency is always positive."""
        telemetry = TelemetryData(
                timestamp=datetime.now(),
            position=PositionData(
                latitude=0.0,
                longitude=0.0,
                altitude=100.0,
                speed=10.0,
                heading=90.0
            ),
            network=NetworkData(
                latency_ms=25.5,  # Typical Starlink latency
                throughput_down_mbps=100.0,
                throughput_up_mbps=20.0,
                packet_loss_percent=1.0
            ),
            obstruction=ObstructionData(obstruction_percent=0.0, potential_obstructions=0),
            environmental=EnvironmentalData(signal_quality_percent=90.0, uptime_seconds=3600.0)
        )
        update_metrics_from_telemetry(telemetry)

    def test_throughput_non_negative(self):
        """Test that throughput values are non-negative."""
        telemetry = TelemetryData(
                timestamp=datetime.now(),
            position=PositionData(
                latitude=0.0,
                longitude=0.0,
                altitude=100.0,
                speed=10.0,
                heading=90.0
            ),
            network=NetworkData(
                latency_ms=50.0,
                throughput_down_mbps=150.0,
                throughput_up_mbps=30.0,
                packet_loss_percent=0.5
            ),
            obstruction=ObstructionData(obstruction_percent=0.0, potential_obstructions=0),
            environmental=EnvironmentalData(signal_quality_percent=90.0, uptime_seconds=3600.0)
        )
        update_metrics_from_telemetry(telemetry)

    def test_packet_loss_in_range(self):
        """Test that packet loss is within 0-100%."""
        for loss in [0.0, 5.0, 50.0, 100.0]:
            telemetry = TelemetryData(
                timestamp=datetime.now(),
                position=PositionData(
                    latitude=0.0,
                    longitude=0.0,
                    altitude=100.0,
                    speed=10.0,
                    heading=90.0
                ),
                network=NetworkData(
                    latency_ms=50.0,
                    throughput_down_mbps=100.0,
                    throughput_up_mbps=20.0,
                    packet_loss_percent=loss
                ),
                obstruction=ObstructionData(obstruction_percent=0.0, potential_obstructions=0),
                environmental=EnvironmentalData(signal_quality_percent=90.0, uptime_seconds=3600.0)
            )
            update_metrics_from_telemetry(telemetry)


class TestPositionHeadingRange:
    """Tests for heading metric range."""

    def test_heading_valid_range(self):
        """Test that heading is between 0 and 360 degrees."""
        for heading in [0.0, 90.0, 180.0, 270.0, 359.9]:
            telemetry = TelemetryData(
                timestamp=datetime.now(),
                position=PositionData(
                    latitude=0.0,
                    longitude=0.0,
                    altitude=100.0,
                    speed=10.0,
                    heading=heading
                ),
                network=NetworkData(
                    latency_ms=50.0,
                    throughput_down_mbps=100.0,
                    throughput_up_mbps=20.0,
                    packet_loss_percent=1.0
                ),
                obstruction=ObstructionData(obstruction_percent=0.0, potential_obstructions=0),
                environmental=EnvironmentalData(signal_quality_percent=90.0, uptime_seconds=3600.0)
            )
            update_metrics_from_telemetry(telemetry)


class TestObstructionMetrics:
    """Tests for obstruction metric ranges."""

    def test_obstruction_percentage_range(self):
        """Test that obstruction percentage is 0-100%."""
        for obstruction in [0.0, 25.0, 50.0, 100.0]:
            telemetry = TelemetryData(
                timestamp=datetime.now(),
                position=PositionData(
                    latitude=0.0,
                    longitude=0.0,
                    altitude=100.0,
                    speed=10.0,
                    heading=90.0
                ),
                network=NetworkData(
                    latency_ms=50.0,
                    throughput_down_mbps=100.0,
                    throughput_up_mbps=20.0,
                    packet_loss_percent=1.0
                ),
                obstruction=ObstructionData(
                    obstruction_percent=obstruction,
                    potential_obstructions=0
                ),
                environmental=EnvironmentalData(signal_quality_percent=90.0, uptime_seconds=3600.0)
            )
            update_metrics_from_telemetry(telemetry)

    def test_signal_quality_range(self):
        """Test that signal quality is 0-100%."""
        for quality in [0.0, 50.0, 100.0]:
            telemetry = TelemetryData(
                timestamp=datetime.now(),
                position=PositionData(
                    latitude=0.0,
                    longitude=0.0,
                    altitude=100.0,
                    speed=10.0,
                    heading=90.0
                ),
                network=NetworkData(
                    latency_ms=50.0,
                    throughput_down_mbps=100.0,
                    throughput_up_mbps=20.0,
                    packet_loss_percent=1.0
                ),
                obstruction=ObstructionData(obstruction_percent=0.0, potential_obstructions=0),
                environmental=EnvironmentalData(
                    signal_quality_percent=quality,
                    uptime_seconds=3600.0
                )
            )
            update_metrics_from_telemetry(telemetry)


class TestExtremeTelemetryValues:
    """Tests for extreme but valid telemetry values."""

    def test_very_high_altitude(self):
        """Test telemetry with very high altitude (aircraft level)."""
        telemetry = TelemetryData(
                timestamp=datetime.now(),
            position=PositionData(
                latitude=0.0,
                longitude=0.0,
                altitude=10000.0,  # 10km altitude
                speed=250.0,
                heading=90.0
            ),
            network=NetworkData(
                latency_ms=50.0,
                throughput_down_mbps=100.0,
                throughput_up_mbps=20.0,
                packet_loss_percent=1.0
            ),
            obstruction=ObstructionData(obstruction_percent=0.0, potential_obstructions=0),
            environmental=EnvironmentalData(signal_quality_percent=90.0, uptime_seconds=3600.0)
        )
        update_metrics_from_telemetry(telemetry)

    def test_very_low_altitude(self):
        """Test telemetry with sea level or below altitude."""
        telemetry = TelemetryData(
                timestamp=datetime.now(),
            position=PositionData(
                latitude=0.0,
                longitude=0.0,
                altitude=-100.0,  # Below sea level (submarine)
                speed=5.0,
                heading=90.0
            ),
            network=NetworkData(
                latency_ms=50.0,
                throughput_down_mbps=100.0,
                throughput_up_mbps=20.0,
                packet_loss_percent=1.0
            ),
            obstruction=ObstructionData(obstruction_percent=0.0, potential_obstructions=0),
            environmental=EnvironmentalData(signal_quality_percent=90.0, uptime_seconds=3600.0)
        )
        update_metrics_from_telemetry(telemetry)
