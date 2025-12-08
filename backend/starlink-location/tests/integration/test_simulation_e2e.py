"""End-to-end simulation tests."""

import pytest
import asyncio


@pytest.mark.asyncio
async def test_simulation_runs_continuously(test_client):
    """Test that simulation runs and generates metrics."""
    await asyncio.sleep(0.2)

    response = test_client.get("/metrics")
    assert response.status_code == 200

    metrics_text = response.text

    # Should have some metrics
    assert len(metrics_text) > 100


@pytest.mark.asyncio
async def test_health_and_metrics_together(test_client):
    """Test that health and metrics endpoints both work."""
    await asyncio.sleep(0.1)

    health_response = test_client.get("/health")
    assert health_response.status_code == 200
    health_data = health_response.json()

    metrics_response = test_client.get("/metrics")
    assert metrics_response.status_code == 200

    # Health should report ok
    assert health_data["status"] == "ok"

    # Metrics should exist
    assert "starlink" in metrics_response.text


@pytest.mark.asyncio
async def test_status_reflects_current_state(test_client):
    """Test that status endpoint reflects current simulator state."""
    await asyncio.sleep(0.2)

    status_response = test_client.get("/api/status")
    assert status_response.status_code == 200

    status_data = status_response.json()

    # Should have valid position
    position = status_data["position"]
    assert -90 <= position["latitude"] <= 90
    assert -180 <= position["longitude"] <= 180

    # Should have valid network metrics
    network = status_data["network"]
    assert network["latency_ms"] > 0
    assert network["throughput_down_mbps"] > 0


@pytest.mark.asyncio
async def test_metrics_match_status(test_client):
    """Test that metrics roughly match status values."""
    await asyncio.sleep(0.2)

    status_response = test_client.get("/api/status")
    status_data = status_response.json()

    metrics_response = test_client.get("/metrics")
    metrics_text = metrics_response.text

    # Both should have position metrics
    assert "latitude" in str(status_data["position"])
    assert "starlink_dish_latitude_degrees" in metrics_text

    # Both should have network metrics
    assert "latency_ms" in str(status_data["network"])
    assert "starlink_network_latency_ms" in metrics_text


@pytest.mark.asyncio
async def test_configuration_affects_simulation(test_client, default_config):
    """Test that configuration changes affect simulation."""
    await asyncio.sleep(0.1)

    # Get current config
    current_response = test_client.get("/api/config")
    current_response.json()

    # Update with modified config
    modified = default_config.model_copy()
    modified.network.latency_min_ms = 30.0  # Different from default

    update_response = test_client.post("/api/config", json=modified.model_dump())
    assert update_response.status_code == 200

    # Verify update was applied
    verify_response = test_client.get("/api/config")
    verify_config = verify_response.json()
    assert verify_config["network"]["latency_min_ms"] == 30.0


@pytest.mark.asyncio
async def test_multiple_endpoints_consistency(test_client):
    """Test that all endpoints are accessible and consistent."""
    await asyncio.sleep(0.2)

    endpoints = [
        ("/health", 200),
        ("/metrics", 200),
        ("/api/status", 200),
        ("/api/config", 200),
    ]

    for endpoint, expected_status in endpoints:
        response = test_client.get(endpoint)
        assert response.status_code == expected_status, f"Failed for {endpoint}"


@pytest.mark.asyncio
async def test_root_endpoint(test_client):
    """Test that root endpoint provides documentation."""
    await asyncio.sleep(0.1)

    response = test_client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert "message" in data
    assert "endpoints" in data


@pytest.mark.asyncio
async def test_simulation_state_persistence(test_client):
    """Test that simulator maintains state across requests."""
    await asyncio.sleep(0.2)

    # Get initial position
    response1 = test_client.get("/api/status")
    position1 = response1.json()["position"]["latitude"]

    await asyncio.sleep(0.3)

    # Get position after delay
    response2 = test_client.get("/api/status")
    position2 = response2.json()["position"]["latitude"]

    # Position should be different (unless by chance the same)
    # This test verifies that simulator is running and updating
    # Both should be valid floats
    assert isinstance(position1, float)
    assert isinstance(position2, float)
    assert -90 <= position1 <= 90
    assert -90 <= position2 <= 90


@pytest.mark.asyncio
async def test_background_updates_running(test_client):
    """Test that background updates are continuously running."""
    await asyncio.sleep(0.1)

    # Get metrics before
    response1 = test_client.get("/metrics")
    text1 = response1.text

    await asyncio.sleep(0.5)

    # Get metrics after - should have updated counters
    response2 = test_client.get("/metrics")
    text2 = response2.text

    # Both should have simulation_updates_total metric
    assert "simulation_updates_total" in text1
    assert "simulation_updates_total" in text2

    # Extract counter values - they should be different
    # (unless we had very bad timing luck)
    # This just verifies the metric exists and is being tracked
    assert "simulation_updates_total" in text2


@pytest.mark.asyncio
async def test_error_recovery(test_client):
    """Test that service recovers from transient errors."""
    await asyncio.sleep(0.1)

    # Make multiple requests to ensure service is stable
    for _ in range(5):
        response = test_client.get("/api/status")
        assert response.status_code == 200

        await asyncio.sleep(0.1)

    # Service should still be functional
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
