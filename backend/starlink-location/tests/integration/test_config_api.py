"""Integration tests for configuration API endpoint."""

import pytest
import asyncio


@pytest.mark.asyncio
async def test_config_get_returns_200(test_client):
    """Test that GET config endpoint returns 200."""
    await asyncio.sleep(0.1)

    response = test_client.get("/api/config")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_config_get_structure(test_client):
    """Test that GET config response has correct structure."""
    await asyncio.sleep(0.1)

    response = test_client.get("/api/config")
    data = response.json()

    assert "mode" in data
    assert "update_interval_seconds" in data
    assert "route" in data
    assert "network" in data
    assert "obstruction" in data
    assert "position" in data


@pytest.mark.asyncio
async def test_config_get_route_config(test_client):
    """Test that route configuration is present."""
    await asyncio.sleep(0.1)

    response = test_client.get("/api/config")
    data = response.json()

    route = data["route"]
    assert "pattern" in route
    assert "latitude_start" in route
    assert "longitude_start" in route
    assert "radius_km" in route or "distance_km" in route


@pytest.mark.asyncio
async def test_config_get_network_config(test_client):
    """Test that network configuration is present."""
    await asyncio.sleep(0.1)

    response = test_client.get("/api/config")
    data = response.json()

    network = data["network"]
    assert "latency_min_ms" in network
    assert "latency_typical_ms" in network
    assert "throughput_down_min_mbps" in network


@pytest.mark.asyncio
async def test_config_post_returns_200(test_client, default_config):
    """Test that POST config endpoint returns 200."""
    await asyncio.sleep(0.1)

    response = test_client.post("/api/config", json=default_config.model_dump())
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_config_post_updates_config(test_client, default_config):
    """Test that POST config actually updates configuration."""
    await asyncio.sleep(0.1)

    # Create modified config
    new_config = default_config.model_copy()
    new_config.mode = "live"

    response = test_client.post("/api/config", json=new_config.model_dump())
    assert response.status_code == 200

    # Verify the update
    data = response.json()
    assert data["mode"] == "live"


@pytest.mark.asyncio
async def test_config_put_returns_200(test_client, default_config):
    """Test that PUT config endpoint returns 200."""
    await asyncio.sleep(0.1)

    response = test_client.put("/api/config", json=default_config.model_dump())
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_config_put_updates_config(test_client, default_config):
    """Test that PUT config updates configuration."""
    await asyncio.sleep(0.1)

    # Create modified config
    new_config = default_config.model_copy()
    new_config.update_interval_seconds = 2.0

    response = test_client.put("/api/config", json=new_config.model_dump())
    assert response.status_code == 200

    data = response.json()
    assert data["update_interval_seconds"] == 2.0


@pytest.mark.asyncio
async def test_config_post_invalid_data_returns_400(test_client):
    """Test that POST with invalid data returns 400."""
    await asyncio.sleep(0.1)

    invalid_config = {
        "mode": "invalid_mode",  # Invalid mode
        "update_interval_seconds": 1.0,
    }

    response = test_client.post("/api/config", json=invalid_config)
    # Should return 400 or 422 for validation error
    assert response.status_code >= 400


@pytest.mark.asyncio
async def test_config_content_type(test_client):
    """Test that config endpoint returns JSON content type."""
    await asyncio.sleep(0.1)

    response = test_client.get("/api/config")
    assert "application/json" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_config_preserves_all_sections(test_client, default_config):
    """Test that all config sections are preserved on update."""
    await asyncio.sleep(0.1)

    response = test_client.post("/api/config", json=default_config.model_dump())
    data = response.json()

    # All sections should be present
    assert "route" in data
    assert "network" in data
    assert "obstruction" in data
    assert "position" in data

    # Values should be preserved
    assert data["route"]["radius_km"] == default_config.route.radius_km
    assert (
        data["network"]["latency_typical_ms"]
        == default_config.network.latency_typical_ms
    )
