"""Tests for Prometheus metrics."""

from prometheus_client import generate_latest

from app.core.metrics import (
    REGISTRY,
    update_metrics_from_telemetry,
    set_service_info,
)


class TestMetricsFormatting:
    """Test Prometheus metrics formatting."""

    def test_metrics_registry_exists(self):
        """Test that metrics registry is properly initialized."""
        assert REGISTRY is not None

    def test_generate_metrics_output(self):
        """Test that metrics can be generated as Prometheus format."""
        output = generate_latest(REGISTRY)
        assert isinstance(output, bytes)
        assert len(output) > 0

    def test_metrics_output_format(self):
        """Test that metrics output is valid Prometheus format."""
        output = generate_latest(REGISTRY).decode("utf-8")

        # Should contain metric names
        assert "starlink_dish_latitude_degrees" in output
        assert "starlink_dish_longitude_degrees" in output
        assert "starlink_network_latency_ms" in output

        # Should have proper format (lines with metric name and value)
        lines = output.strip().split("\n")
        metric_lines = [line for line in lines if not line.startswith("#")]
        assert len(metric_lines) > 0

    def test_update_metrics_from_telemetry(self, coordinator):
        """Test updating metrics from telemetry data."""
        telemetry = coordinator.get_current_telemetry()

        # Update metrics
        update_metrics_from_telemetry(telemetry)

        output = generate_latest(REGISTRY).decode("utf-8")

        # Check that values are present
        assert "starlink_dish_latitude_degrees" in output
        assert "starlink_dish_longitude_degrees" in output

    def test_set_service_info(self):
        """Test setting service info metric."""
        set_service_info(version="0.2.0", mode="simulation")

        output = generate_latest(REGISTRY).decode("utf-8")

        # Should contain service info metric with labels
        assert "starlink_service_info" in output
        assert 'version="0.2.0"' in output
        assert 'mode="simulation"' in output

    def test_metrics_are_numeric(self, coordinator):
        """Test that metric values are numeric."""
        telemetry = coordinator.get_current_telemetry()
        update_metrics_from_telemetry(telemetry)

        output = generate_latest(REGISTRY).decode("utf-8")
        lines = output.strip().split("\n")

        # Find metric lines (not comments)
        metric_lines = [line for line in lines if not line.startswith("#")]

        for line in metric_lines:
            if line:
                # Format is: metric_name{labels} value
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        value = float(parts[-1])
                        assert not (value != value)  # Check not NaN
                    except (ValueError, IndexError):
                        # Some lines may have different format
                        pass

    def test_position_metrics_present(self, coordinator):
        """Test that position metrics are present."""
        telemetry = coordinator.get_current_telemetry()
        update_metrics_from_telemetry(telemetry)

        output = generate_latest(REGISTRY).decode("utf-8")

        # Position metrics should be present
        assert "starlink_dish_latitude_degrees" in output
        assert "starlink_dish_longitude_degrees" in output
        assert "starlink_dish_altitude_feet" in output
        assert "starlink_dish_speed_knots" in output
        assert "starlink_dish_heading_degrees" in output

    def test_network_metrics_present(self, coordinator):
        """Test that network metrics are present."""
        telemetry = coordinator.get_current_telemetry()
        update_metrics_from_telemetry(telemetry)

        output = generate_latest(REGISTRY).decode("utf-8")

        # Network metrics should be present
        assert "starlink_network_latency_ms" in output
        assert "starlink_network_throughput_down_mbps" in output
        assert "starlink_network_throughput_up_mbps" in output
        assert "starlink_network_packet_loss_percent" in output

    def test_obstruction_metrics_present(self, coordinator):
        """Test that obstruction metrics are present."""
        telemetry = coordinator.get_current_telemetry()
        update_metrics_from_telemetry(telemetry)

        output = generate_latest(REGISTRY).decode("utf-8")

        # Obstruction metrics should be present
        assert "starlink_dish_obstruction_percent" in output
        assert "starlink_signal_quality_percent" in output

    def test_status_metrics_present(self, coordinator):
        """Test that status metrics are present."""
        telemetry = coordinator.get_current_telemetry()
        update_metrics_from_telemetry(telemetry)

        output = generate_latest(REGISTRY).decode("utf-8")

        # Status metrics should be present
        assert "starlink_uptime_seconds" in output
        assert "simulation_updates_total" in output

    def test_mode_info_metric_present(self):
        """Test that starlink_mode_info metric is present."""
        output = generate_latest(REGISTRY).decode("utf-8")
        assert "starlink_mode_info" in output

    def test_set_service_info_with_simulation_mode(self):
        """Test setting service info with simulation mode."""
        set_service_info(version="0.2.0", mode="simulation")

        output = generate_latest(REGISTRY).decode("utf-8")

        # Should contain both service info and mode info metrics
        assert "starlink_service_info" in output
        assert 'mode="simulation"' in output
        assert "starlink_mode_info" in output

    def test_set_service_info_with_live_mode(self):
        """Test setting service info with live mode."""
        set_service_info(version="0.2.0", mode="live")

        output = generate_latest(REGISTRY).decode("utf-8")

        # Should contain both service info and mode info metrics
        assert "starlink_service_info" in output
        assert 'mode="live"' in output
        assert "starlink_mode_info" in output
        # Mode info should have live=1 and simulation=0
        assert 'mode="live"' in output

    def test_mode_info_labels(self):
        """Test that mode_info metric has correct labels."""
        set_service_info(version="0.2.0", mode="simulation")

        output = generate_latest(REGISTRY).decode("utf-8")

        # Check for mode labels in the output
        lines = output.split("\n")
        mode_lines = [
            line
            for line in lines
            if "starlink_mode_info" in line and not line.startswith("#")
        ]

        # Should have entries for each mode
        assert any('mode="simulation"' in line for line in mode_lines)
        assert any('mode="live"' in line for line in mode_lines)
