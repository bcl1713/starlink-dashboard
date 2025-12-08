from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from main import app
import pytest


@pytest.fixture
def client():
    # Mock dependencies to avoid startup complexity/errors
    app.state.route_manager = MagicMock()
    app.state.poi_manager = MagicMock()

    # Use context manager to trigger startup/shutdown events (though we mocked the state mostly)
    with TestClient(app) as c:
        yield c


def test_router_ordering_missions_v1_priority(client):
    """
    Verify that /api/missions is handled by the v1 router.
    """
    response = client.get("/api/missions")
    assert response.status_code != 404


def test_router_ordering_missions_v2_priority(client):
    """
    Verify that /api/v2/missions is handled by the v2 router.
    """
    response = client.get("/api/v2/missions")
    assert response.status_code != 404


def test_router_overlap_check(client):
    """
    Ensure that specific paths aren't shadowed.
    """
    paths = ["/api/missions", "/api/v2/missions", "/health", "/metrics", "/api/routes/"]
    for path in paths:
        response = client.get(path)
        if response.status_code == 404:
            print(f"\nFailed path: {path}")
            # print(app.routes) # Too noisy
        assert response.status_code != 404, f"Path {path} returned 404"
