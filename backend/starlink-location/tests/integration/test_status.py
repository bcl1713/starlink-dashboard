"""Integration tests for JSON status endpoint."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from app.api import status as status_api
from app.models.telemetry import TelemetryData
from app.services.ground_entry_point import GroundEntryPoint
from tests.conftest import default_mock_telemetry

METRICS = [
    "latency_ms",
    "throughput_down_mbps",
    "throughput_up_mbps",
    "packet_loss_percent",
    "obstruction_percent",
]


@pytest.mark.parametrize("unavailable", [None, *METRICS, "legacy"])
def test_status_projects_availability_without_mutating_batch(
    test_client, monkeypatch, unavailable
):
    payload = default_mock_telemetry().model_dump()
    payload["timestamp"] = datetime(2020, 1, 2, tzinfo=timezone.utc)
    payload["network"] = {
        "latency_ms": 0.0,
        "throughput_down_mbps": 100.0,
        "throughput_up_mbps": 20.0,
        "packet_loss_percent": 0.0,
    }
    payload["obstruction"] = {"obstruction_percent": 0.0}
    payload.pop("metric_availability", None)
    if unavailable != "legacy":
        payload["metric_availability"] = {
            metric: metric != unavailable for metric in METRICS
        }
    telemetry = TelemetryData(**payload)
    before = telemetry.model_dump()
    monkeypatch.setattr(
        status_api, "_coordinator", Mock(get_current_telemetry=lambda: telemetry)
    )
    response = test_client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["timestamp"] == "2020-01-02T00:00:00+00:00"
    assert data["position"] == payload["position"]
    assert data["environmental"] == payload["environmental"]
    for metric in METRICS:
        available = unavailable != "legacy" and metric != unavailable
        assert data["metric_availability"][metric] is available
        group = "obstruction" if metric == "obstruction_percent" else "network"
        assert data[group][metric] == (payload[group][metric] if available else None)
    assert telemetry.model_dump() == before


@pytest.mark.asyncio
async def test_status_exposes_current_cached_ground_entry_point(
    test_client, monkeypatch
):
    monkeypatch.setattr(
        status_api,
        "get_cached_ground_entry_point",
        lambda: GroundEntryPoint(
            ip="203.0.113.10",
            city="Omaha",
            region="NE",
            country="US",
            latitude=41.2565,
            longitude=-95.9345,
        ),
        raising=False,
    )

    response = test_client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["ground_entry_point"] == {
        "latitude": 41.2565,
        "longitude": -95.9345,
    }


@pytest.mark.asyncio
async def test_status_marks_unavailable_ground_entry_point_as_null(
    test_client, monkeypatch
):
    monkeypatch.setattr(
        status_api,
        "get_cached_ground_entry_point",
        lambda: None,
        raising=False,
    )

    response = test_client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["ground_entry_point"] is None


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
