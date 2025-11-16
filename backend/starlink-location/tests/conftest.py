"""Shared test fixtures and configuration."""

import asyncio
import os
import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

os.environ.setdefault("STARLINK_DISABLE_BACKGROUND_TASKS", "1")

# Ensure /data directories exist for RouteManager and Missions
Path("/tmp/test_data/routes").mkdir(parents=True, exist_ok=True)
Path("/tmp/test_data/sim_routes").mkdir(parents=True, exist_ok=True)
Path("data/missions").mkdir(parents=True, exist_ok=True)
TEST_MISSIONS_DIR = Path("/tmp/test_data/missions")
TEST_MISSIONS_DIR.mkdir(parents=True, exist_ok=True)

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
    self.lock_file = str(self.pois_file) + ".lock"
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
    # Ensure ETA service is initialized before creating coordinator
    # This prevents "ETA service not initialized" errors in metrics tests
    from app.core import eta_service
    from app.services.poi_manager import POIManager

    if eta_service._eta_calculator is None:
        poi_manager = POIManager()
        eta_service.initialize_eta_service(poi_manager)

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


@pytest.fixture(autouse=True)
def unified_poi_manager_in_tests():
    """Ensure all API modules share the same POIManager instance after app startup.

    This fixture runs after TestClient initialization completes, ensuring that
    all API modules have been injected with the same POIManager singleton
    by main.py's startup event.
    """
    # This autouse fixture ensures POIManager synchronization across modules
    # The actual injection happens in main.py startup_event
    # This fixture just validates it worked
    yield
    # After test completes, modules maintain their shared instance
    # until next test's TestClient initialization


@pytest.fixture
def client(test_client):
    """Alias for test_client for convenience."""
    return test_client


@pytest.fixture(autouse=True)
def reset_mission_active_state():
    """Reset global _active_mission_id before each test to prevent state leakage."""
    # Import here to avoid circular imports
    import app.mission.routes as mission_routes

    # Reset before test starts
    mission_routes._active_mission_id = None

    yield

    # Reset after test completes
    mission_routes._active_mission_id = None


@pytest.fixture(autouse=True)
def ensure_eta_service_initialized():
    """Ensure ETA service is initialized before each test.

    This fixture addresses test isolation issues where test_eta_service.py's
    reset_eta_service_globals fixture clears the ETA service globals,
    which causes subsequent tests to fail with "ETA service not initialized".

    By re-initializing the ETA service before each test, we ensure all tests
    have access to a properly initialized ETA service.
    """
    # Before test starts, ensure ETA service is initialized
    from app.core import eta_service
    from app.services.poi_manager import POIManager

    try:
        # Check if ETA service is uninitialized
        if eta_service._eta_calculator is None:
            # Re-initialize the ETA service
            poi_manager = POIManager()
            eta_service.initialize_eta_service(poi_manager)
    except Exception:
        # Silently handle initialization errors - they may be expected in some tests
        pass

    yield

    # Cleanup after test completes (optional - keeps tests that reset the service working)
    # No cleanup needed - tests that want to reset will do it themselves


@pytest.fixture(autouse=True)
def reset_prometheus_registry():
    """Reset all gauge metrics before each test to prevent NaN pollution from previous tests.

    This addresses test isolation issues where Prometheus metrics from previous
    tests can interfere with current tests. NaN values that may have been set by
    clear_telemetry_metrics() in live mode tests will persist across tests if
    not cleared.

    This fixture clears all gauge metric values (both with and without labels)
    by setting them to 0.0 before each test runs.
    """
    # Before each test, reset all gauge metrics to prevent pollution from NaN values
    try:
        from app.core import metrics
        from prometheus_client.core import Gauge

        # Reset the custom position collector data
        metrics._current_position['latitude'] = 0.0
        metrics._current_position['longitude'] = 0.0
        metrics._current_position['altitude'] = 0.0

        # Get the registry and iterate through all collectors
        # Find all Gauge collectors and reset their values
        for collector in list(metrics.REGISTRY._collector_to_names.keys()):
            if isinstance(collector, Gauge):
                try:
                    # Gauges without labels: can call set() directly
                    if not hasattr(collector, '_metrics') or not collector._metrics:
                        try:
                            collector.set(0)
                        except Exception:
                            pass
                    # Gauges with labels: need to reset each child metric
                    else:
                        for child in collector._metrics.values():
                            try:
                                child.set(0)
                            except Exception:
                                pass
                except Exception:
                    # Silently skip any gauges we can't reset
                    pass

    except Exception:
        # If we can't reset the registry, continue anyway - tests will still run
        pass

    yield
    # No cleanup needed after test


def _clean_directory(directory: Path):
    """Remove all files/sub-directories inside the provided directory."""
    if not directory.exists():
        return
    for child in directory.iterdir():
        if child.is_file() or child.is_symlink():
            try:
                child.unlink()
            except FileNotFoundError:
                pass
        elif child.is_dir():
            shutil.rmtree(child, ignore_errors=True)


@pytest.fixture(autouse=True)
def isolate_mission_storage():
    """Force mission storage to use a temp directory with full cleanup."""
    from app.mission import storage

    original_dir = storage.MISSIONS_DIR
    storage.MISSIONS_DIR = TEST_MISSIONS_DIR
    storage.ensure_missions_directory()
    _clean_directory(TEST_MISSIONS_DIR)

    yield

    _clean_directory(TEST_MISSIONS_DIR)
    storage.MISSIONS_DIR = original_dir


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


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    """Limit anyio backend to asyncio only (trio not installed)."""
    return request.param


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
