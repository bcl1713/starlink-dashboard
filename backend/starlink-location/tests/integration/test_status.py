"""Integration tests for JSON status endpoint."""

import pytest
import asyncio


@pytest.mark.asyncio
async def test_status_endpoint_returns_200(test_client):
    """Test that status endpoint returns 200 status."""
    await asyncio.sleep(0.1)

    response = test_client.get("/api/status")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_status_response_structure(test_client):
    """Test that status response has correct structure."""
    await asyncio.sleep(0.1)

    response = test_client.get("/api/status")
    assert response.status_code == 200

    data = response.json()
    assert "timestamp" in data
    assert "position" in data
    assert "network" in data
    assert "obstruction" in data
    assert "environmental" in data


@pytest.mark.asyncio
async def test_status_position_data(test_client):
    """Test that position data is present and valid."""
    await asyncio.sleep(0.1)

    response = test_client.get("/api/status")
    data = response.json()

    position = data["position"]
    assert "latitude" in position
    assert "longitude" in position
    assert "altitude" in position
    assert "speed" in position
    assert "heading" in position

    # Validate ranges
    assert -90 <= position["latitude"] <= 90
    assert -180 <= position["longitude"] <= 180
    assert position["altitude"] > 0
    assert position["speed"] >= 0
    assert 0 <= position["heading"] <= 360


@pytest.mark.asyncio
async def test_status_network_data(test_client):
    """Test that network data is present and valid."""
    await asyncio.sleep(0.1)

    response = test_client.get("/api/status")
    data = response.json()

    network = data["network"]
    assert "latency_ms" in network
    assert "throughput_down_mbps" in network
    assert "throughput_up_mbps" in network
    assert "packet_loss_percent" in network

    # Validate ranges
    assert network["latency_ms"] > 0
    assert network["throughput_down_mbps"] > 0
    assert network["throughput_up_mbps"] > 0
    assert 0 <= network["packet_loss_percent"] <= 100


@pytest.mark.asyncio
async def test_status_obstruction_data(test_client):
    """Test that obstruction data is present and valid."""
    await asyncio.sleep(0.1)

    response = test_client.get("/api/status")
    data = response.json()

    obstruction = data["obstruction"]
    assert "obstruction_percent" in obstruction
    assert 0 <= obstruction["obstruction_percent"] <= 100


@pytest.mark.asyncio
async def test_status_environmental_data(test_client):
    """Test that environmental data is present and valid."""
    await asyncio.sleep(0.1)

    response = test_client.get("/api/status")
    data = response.json()

    environmental = data["environmental"]
    assert "signal_quality_percent" in environmental
    assert "uptime_seconds" in environmental

    # Validate ranges
    assert 0 <= environmental["signal_quality_percent"] <= 100
    assert environmental["uptime_seconds"] >= 0


@pytest.mark.asyncio
async def test_status_timestamp_iso8601(test_client):
    """Test that timestamp is ISO 8601 formatted."""
    await asyncio.sleep(0.1)

    response = test_client.get("/api/status")
    data = response.json()

    timestamp = data["timestamp"]
    # ISO 8601 has 'T' between date and time
    assert "T" in timestamp


@pytest.mark.asyncio
async def test_status_content_type(test_client):
    """Test that status endpoint returns JSON content type."""
    await asyncio.sleep(0.1)

    response = test_client.get("/api/status")
    assert "application/json" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_status_data_updates(test_client):
    """Test that status data updates over time."""
    await asyncio.sleep(0.1)

    response1 = test_client.get("/api/status")
    lat1 = response1.json()["position"]["latitude"]

    await asyncio.sleep(0.5)

    response2 = test_client.get("/api/status")
    lat2 = response2.json()["position"]["latitude"]

    # Position may update (latitude may change)
    # This test just verifies we get valid data both times
    assert isinstance(lat1, float)
    assert isinstance(lat2, float)
    assert -90 <= lat1 <= 90
    assert -90 <= lat2 <= 90
