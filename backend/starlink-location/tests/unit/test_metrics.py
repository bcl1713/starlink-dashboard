"""Tests for Prometheus metrics."""

import math
from types import SimpleNamespace

import pytest
from prometheus_client import generate_latest
from prometheus_client.parser import text_string_to_metric_families

from app.core.labels import apply_common_labels
from app.core.metrics import (
    REGISTRY,
    set_service_info,
    update_metrics_from_telemetry,
)
from app.models.telemetry import MetricAvailability

FIVE_METRICS = [
    (
        "latency_ms",
        "starlink_network_latency_ms_current",
        "starlink_network_latency_ms",
    ),
    (
        "throughput_down_mbps",
        "starlink_network_throughput_down_mbps_current",
        "starlink_network_throughput_down_mbps",
    ),
    (
        "throughput_up_mbps",
        "starlink_network_throughput_up_mbps_current",
        "starlink_network_throughput_up_mbps",
    ),
    ("packet_loss_percent", "starlink_network_packet_loss_percent", None),
    ("obstruction_percent", "starlink_dish_obstruction_percent", None),
]


def exported_samples():
    """Read actual exporter output, including histogram labels and counts."""
    return [
        sample
        for family in text_string_to_metric_families(
            generate_latest(REGISTRY).decode("utf-8")
        )
        for sample in family.samples
    ]


def histogram_count(samples, histogram):
    return sum(
        sample.value for sample in samples if sample.name == histogram + "_count"
    )


@pytest.mark.parametrize(("field", "gauge", "histogram"), FIVE_METRICS)
@pytest.mark.parametrize("recovered_value", [0.0, 17.0])
def test_partial_loss_clears_only_its_gauge_and_skips_histogram_then_recovers(
    coordinator, field, gauge, histogram, recovered_value
):
    # Catches unconditional publication of compatibility zeros or blanket clearing.
    telemetry = coordinator.get_current_telemetry().model_copy(deep=True)
    for name, _, _ in FIVE_METRICS:
        target = (
            telemetry.obstruction
            if name == "obstruction_percent"
            else telemetry.network
        )
        setattr(target, name, 0.0)
    update_metrics_from_telemetry(telemetry)
    before = exported_samples()
    telemetry.metric_availability = MetricAvailability(
        **{name: name != field for name, _, _ in FIVE_METRICS}
    )
    update_metrics_from_telemetry(telemetry)
    missing = exported_samples()
    gauges = {s.name: s.value for s in missing if not s.labels}
    assert math.isnan(gauges[gauge])
    for name, other_gauge, other_histogram in FIVE_METRICS:
        if name != field:
            assert gauges[other_gauge] == 0.0
        if other_histogram:
            assert histogram_count(missing, other_histogram) == histogram_count(
                before, other_histogram
            ) + (name != field)
    assert gauges["starlink_dish_latitude_degrees"] == telemetry.position.latitude
    assert (
        gauges["starlink_signal_quality_percent"]
        == telemetry.environmental.signal_quality_percent
    )
    assert gauges["starlink_uptime_seconds"] == telemetry.environmental.uptime_seconds
    expected_status = (
        "unknown" if field in ("latency_ms", "packet_loss_percent") else "excellent"
    )
    assert (
        apply_common_labels(telemetry, SimpleNamespace(mode="simulation"))["status"]
        == expected_status
    )
    for name, _, other_histogram in FIVE_METRICS:
        if other_histogram and name != field:
            count = next(
                s.value
                for s in missing
                if s.name == other_histogram + "_count"
                and s.labels == {"mode": "unknown", "status": expected_status}
            )
            old_count = sum(
                s.value
                for s in before
                if s.name == other_histogram + "_count"
                and s.labels == {"mode": "unknown", "status": expected_status}
            )
            assert count == old_count + 1
    target = (
        telemetry.obstruction if field == "obstruction_percent" else telemetry.network
    )
    setattr(target, field, recovered_value)
    setattr(telemetry.metric_availability, field, True)
    update_metrics_from_telemetry(telemetry)
    recovered = exported_samples()
    assert next(s.value for s in recovered if s.name == gauge) == recovered_value
    if histogram:
        assert (
            histogram_count(recovered, histogram)
            == histogram_count(missing, histogram) + 1
        )


@pytest.mark.parametrize("missing_field", ["latency_ms", "packet_loss_percent"])
def test_missing_health_input_labels_available_throughput_unknown(
    coordinator, missing_field
):
    telemetry = coordinator.get_current_telemetry().model_copy(deep=True)
    telemetry.network.latency_ms = 0.0
    telemetry.network.packet_loss_percent = 0.0
    setattr(telemetry.metric_availability, missing_field, False)
    before = exported_samples()
    update_metrics_from_telemetry(telemetry)
    after = exported_samples()
    assert (
        apply_common_labels(telemetry, SimpleNamespace(mode="live"))["status"]
        == "unknown"
    )
    for histogram in (
        "starlink_network_throughput_down_mbps",
        "starlink_network_throughput_up_mbps",
    ):
        labels = {"mode": "unknown", "status": "unknown"}
        old = sum(
            s.value
            for s in before
            if s.name == histogram + "_count" and s.labels == labels
        )
        new = sum(
            s.value
            for s in after
            if s.name == histogram + "_count" and s.labels == labels
        )
        assert new == old + 1


@pytest.mark.parametrize("legacy_kind", ["model_default", "no_sidecar"])
def test_legacy_numeric_telemetry_fails_closed_in_exporter_and_health(
    coordinator, legacy_kind
):
    telemetry = coordinator.get_current_telemetry().model_copy(deep=True)
    if legacy_kind == "model_default":
        payload = telemetry.model_dump()
        payload.pop("metric_availability")
        telemetry = type(telemetry).model_validate(payload)
    else:
        telemetry = SimpleNamespace(
            **{
                name: getattr(telemetry, name)
                for name in (
                    "timestamp",
                    "position",
                    "network",
                    "obstruction",
                    "environmental",
                )
            }
        )
    before = exported_samples()
    update_metrics_from_telemetry(telemetry)
    after = exported_samples()
    for _, gauge, histogram in FIVE_METRICS:
        assert math.isnan(next(s.value for s in after if s.name == gauge))
        if histogram:
            assert histogram_count(after, histogram) == histogram_count(
                before, histogram
            )
    assert (
        apply_common_labels(telemetry, SimpleNamespace(mode="live"))["status"]
        == "unknown"
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
                        assert not math.isnan(value)
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
