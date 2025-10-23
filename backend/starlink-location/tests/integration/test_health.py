"""Integration tests for health check endpoint."""

import pytest
import asyncio


@pytest.mark.asyncio
async def test_health_endpoint_returns_200(test_client):
    """Test that health endpoint returns 200 status."""
    # Give app time to initialize
    await asyncio.sleep(0.1)

    response = test_client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_response_structure(test_client):
    """Test that health response has correct structure."""
    await asyncio.sleep(0.1)

    response = test_client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert "uptime_seconds" in data
    assert "mode" in data
    assert "version" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_health_status_is_ok(test_client):
    """Test that health status is 'ok'."""
    await asyncio.sleep(0.1)

    response = test_client.get("/health")
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_health_uptime_increases(test_client):
    """Test that uptime increases over time."""
    await asyncio.sleep(0.1)

    response1 = test_client.get("/health")
    uptime1 = response1.json()["uptime_seconds"]

    await asyncio.sleep(0.5)

    response2 = test_client.get("/health")
    uptime2 = response2.json()["uptime_seconds"]

    assert uptime2 > uptime1


@pytest.mark.asyncio
async def test_health_version_is_present(test_client):
    """Test that version is present in response."""
    await asyncio.sleep(0.1)

    response = test_client.get("/health")
    data = response.json()
    assert "version" in data
    assert len(data["version"]) > 0


@pytest.mark.asyncio
async def test_health_mode_is_simulation(test_client):
    """Test that mode is set correctly."""
    await asyncio.sleep(0.1)

    response = test_client.get("/health")
    data = response.json()
    assert data["mode"] in ["simulation", "live"]


@pytest.mark.asyncio
async def test_health_timestamp_is_iso8601(test_client):
    """Test that timestamp is ISO 8601 formatted."""
    await asyncio.sleep(0.1)

    response = test_client.get("/health")
    data = response.json()

    # ISO 8601 timestamps contain 'T' and have colons
    assert "T" in data["timestamp"]
    assert ":" in data["timestamp"]
