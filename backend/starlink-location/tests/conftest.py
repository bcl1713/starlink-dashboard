"""Shared test fixtures and configuration."""

import asyncio
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
            altitude_min_meters=100.0,
            altitude_max_meters=10000.0,
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
