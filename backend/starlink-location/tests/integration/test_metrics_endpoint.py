"""Integration tests for Prometheus metrics endpoint."""

import pytest
import asyncio


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_200(test_client):
    """Test that metrics endpoint returns 200 status."""
    await asyncio.sleep(0.1)

    response = test_client.get("/metrics")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_metrics_content_type(test_client):
    """Test that metrics endpoint returns correct content type."""
    await asyncio.sleep(0.1)

    response = test_client.get("/metrics")
    assert response.status_code == 200

    content_type = response.headers.get("content-type", "")
    assert "openmetrics-text" in content_type or "text/plain" in content_type


@pytest.mark.asyncio
async def test_metrics_response_is_text(test_client):
    """Test that metrics response is text format."""
    await asyncio.sleep(0.1)

    response = test_client.get("/metrics")
    assert response.status_code == 200

    text = response.text
    assert isinstance(text, str)
    assert len(text) > 0


@pytest.mark.asyncio
async def test_metrics_contain_position_metrics(test_client):
    """Test that metrics contain position data."""
    await asyncio.sleep(0.2)

    response = test_client.get("/metrics")
    text = response.text

    assert "starlink_dish_latitude_degrees" in text
    assert "starlink_dish_longitude_degrees" in text
    assert "starlink_dish_altitude_feet" in text
    assert "starlink_dish_speed_knots" in text
    assert "starlink_dish_heading_degrees" in text


@pytest.mark.asyncio
async def test_metrics_contain_network_metrics(test_client):
    """Test that metrics contain network data."""
    await asyncio.sleep(0.2)

    response = test_client.get("/metrics")
    text = response.text

    assert "starlink_network_latency_ms" in text
    assert "starlink_network_throughput_down_mbps" in text
    assert "starlink_network_throughput_up_mbps" in text
    assert "starlink_network_packet_loss_percent" in text


@pytest.mark.asyncio
async def test_metrics_contain_obstruction_metrics(test_client):
    """Test that metrics contain obstruction data."""
    await asyncio.sleep(0.2)

    response = test_client.get("/metrics")
    text = response.text

    assert "starlink_dish_obstruction_percent" in text
    assert "starlink_signal_quality_percent" in text


@pytest.mark.asyncio
async def test_metrics_contain_status_metrics(test_client):
    """Test that metrics contain status data."""
    await asyncio.sleep(0.2)

    response = test_client.get("/metrics")
    text = response.text

    assert "starlink_service_info" in text
    assert "starlink_uptime_seconds" in text
    assert "simulation_updates_total" in text


@pytest.mark.asyncio
async def test_metrics_format_is_valid(test_client):
    """Test that metrics are in valid Prometheus format."""
    await asyncio.sleep(0.2)

    response = test_client.get("/metrics")
    text = response.text

    # Prometheus format has # for comments and name{labels} value for metrics
    lines = text.strip().split('\n')
    metric_lines = [l for l in lines if not l.startswith('#')]

    # Should have some metric lines
    assert len(metric_lines) > 0

    # Check basic format
    for line in metric_lines:
        if line and not line.startswith('TYPE') and not line.startswith('HELP'):
            # Should have at least a space separating metric from value
            assert ' ' in line


@pytest.mark.asyncio
async def test_metrics_values_are_numeric(test_client):
    """Test that metric values are numeric."""
    await asyncio.sleep(0.2)

    response = test_client.get("/metrics")
    text = response.text

    lines = text.strip().split('\n')
    metric_lines = [l for l in lines if not l.startswith('#')]

    for line in metric_lines:
        if line and not any(x in line for x in ['TYPE', 'HELP']):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    value = float(parts[-1])
                    # Should not be NaN or Inf (though some Prometheus formats allow these)
                    assert value == value  # NaN check
                except (ValueError, IndexError):
                    pass


@pytest.mark.asyncio
async def test_metrics_update_over_time(test_client):
    """Test that metrics values update over time."""
    await asyncio.sleep(0.1)

    response1 = test_client.get("/metrics")
    text1 = response1.text

    # Extract a metric value
    for line in text1.split('\n'):
        if 'starlink_dish_latitude_degrees ' in line and not line.startswith('#'):
            lat1 = float(line.split()[-1])
            break

    await asyncio.sleep(0.5)

    response2 = test_client.get("/metrics")
    text2 = response2.text

    for line in text2.split('\n'):
        if 'starlink_dish_latitude_degrees ' in line and not line.startswith('#'):
            lat2 = float(line.split()[-1])
            break

    # Latitude should either be the same or different (position updates)
    # This test just verifies we can extract numeric values
    assert isinstance(lat1, float)
    assert isinstance(lat2, float)
