"""Integration tests for mission router retirement."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    """Use the real application router registration with lightweight state."""
    app.state.route_manager = MagicMock()
    app.state.poi_manager = MagicMock()
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize(
    "path",
    [
        "/api/missions",
        "/api/missions/active",
        "/api/missions/active/timeline",
        "/api/missions/example/activate",
        "/api/missions/example/export/pdf",
    ],
)
def test_legacy_mission_routes_are_not_registered(client, path):
    """Former v1 mission endpoints must be absent rather than redirected."""
    assert client.get(path).status_code == 404


def test_v2_route_remains_registered(client):
    """Retiring v1 must not remove the scoped v2 API."""
    assert client.get("/api/v2/missions").status_code != 404
