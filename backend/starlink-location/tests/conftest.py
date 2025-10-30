"""Shared test fixtures and configuration."""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

# Ensure /data directories exist for RouteManager
Path("/tmp/test_data/routes").mkdir(parents=True, exist_ok=True)
Path("/tmp/test_data/sim_routes").mkdir(parents=True, exist_ok=True)

# Monkey-patch RouteManager and POIManager before any imports
import app.services.route_manager as route_manager_module
original_route_init = route_manager_module.RouteManager.__init__

def patched_route_init(self, routes_dir="/tmp/test_data/routes"):
    self.routes_dir = Path(routes_dir)
    self.routes_dir.mkdir(parents=True, exist_ok=True)
    self._routes = {}
    self._active_route_id = None
    self._observer = None
    self._errors = {}

route_manager_module.RouteManager.__init__ = patched_route_init

import app.services.poi_manager as poi_manager_module
import json

original_poi_init = poi_manager_module.POIManager.__init__

def patched_poi_init(self, pois_file="/tmp/test_data/pois.json"):
    self.pois_file = Path(pois_file)
    self.pois_file.parent.mkdir(parents=True, exist_ok=True)
    self._pois = {}
    self._logger = poi_manager_module.logger

    # Ensure file exists with initial structure
    if not self.pois_file.exists():
        with open(self.pois_file, "w") as f:
            json.dump({"pois": {}, "routes": {}}, f, indent=2)

    # Call the original _load_pois to properly load from the file
    self._load_pois()

poi_manager_module.POIManager.__init__ = patched_poi_init

import pytest
from fastapi.testclient import TestClient

from app.core.config import ConfigManager
from app.models.config import (
    NetworkConfig,
    ObstructionConfig,
    PositionConfig,
    RouteConfig,
    SimulationConfig,
)
from app.models.telemetry import (
    EnvironmentalData,
    NetworkData,
    ObstructionData,
    PositionData,
    TelemetryData,
)
from app.simulation.coordinator import SimulationCoordinator
from main import app, startup_event, shutdown_event


@pytest.fixture
def default_config():
    """Provide default simulation configuration for tests."""
    return SimulationConfig(
        mode="simulation",
        update_interval_seconds=1.0,
        route=RouteConfig(
            pattern="circular",
            latitude_start=40.7128,
            longitude_start=-74.0060,
            radius_km=100.0,
            distance_km=500.0
        ),
        network=NetworkConfig(
            latency_min_ms=20.0,
            latency_typical_ms=50.0,
            latency_max_ms=80.0,
            latency_spike_max_ms=200.0,
            spike_probability=0.05,
            throughput_down_min_mbps=50.0,
            throughput_down_max_mbps=200.0,
            throughput_up_min_mbps=10.0,
            throughput_up_max_mbps=40.0,
            packet_loss_min_percent=0.0,
            packet_loss_max_percent=5.0
        ),
        obstruction=ObstructionConfig(
            min_percent=0.0,
            max_percent=30.0,
            variation_rate=0.5
        ),
        position=PositionConfig(
            speed_min_knots=0.0,
            speed_max_knots=100.0,
            altitude_min_feet=328.0,
            altitude_max_feet=32808.0,
            heading_variation_rate=5.0
        )
    )


@pytest.fixture
def coordinator(default_config):
    """Provide a simulation coordinator for tests."""
    return SimulationCoordinator(default_config)


@pytest.fixture
def test_client():
    """Provide a FastAPI test client with proper initialization."""
    # Use TestClient which handles the lifespan context
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def reset_config_manager():
    """Reset ConfigManager singleton before each test."""
    ConfigManager.reset()
    yield
    ConfigManager.reset()


def default_mock_telemetry():
    """Create default mock telemetry for tests."""
    return TelemetryData(
        timestamp=datetime.now(),
        position=PositionData(
            latitude=40.7128,
            longitude=-74.0060,
            altitude=328.0,
            speed=0.0,
            heading=0.0,
        ),
        network=NetworkData(
            latency_ms=50.0,
            throughput_down_mbps=100.0,
            throughput_up_mbps=20.0,
            packet_loss_percent=1.0,
        ),
        obstruction=ObstructionData(obstruction_percent=15.0),
        environmental=EnvironmentalData(),
    )


@pytest.fixture
def mock_starlink_client_factory():
    """Factory to create a mocked StarlinkClient with default success behavior.

    This is used by live coordinator tests to mock the gRPC client without
    having actual hardware available.
    """
    def create_mock_client(telemetry=None, fail_on_init=False):
        """Create a mock StarlinkClient.

        Args:
            telemetry: TelemetryData to return, or None for default mock
            fail_on_init: If True, raise Exception on get_telemetry() call

        Returns:
            MagicMock StarlinkClient instance
        """
        mock_client = MagicMock()

        if fail_on_init:
            mock_client.get_telemetry.side_effect = Exception("API error")
        else:
            if telemetry is None:
                telemetry = default_mock_telemetry()
            mock_client.get_telemetry.return_value = telemetry

        return mock_client

    return create_mock_client
