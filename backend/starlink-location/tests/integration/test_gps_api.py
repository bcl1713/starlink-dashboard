"""Integration tests for GPS configuration API endpoint."""

import pytest
from unittest.mock import MagicMock, patch


class TestGPSConfigAPI:
    """Test GPS configuration API endpoints."""

    @pytest.mark.asyncio
    async def test_gps_config_get_simulation_mode_returns_503(self, test_client):
        """Test GET GPS config returns 503 in simulation mode (no client)."""
        response = test_client.get("/api/v2/gps/config")
        assert response.status_code == 503
        assert "simulation mode" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_gps_config_post_simulation_mode_returns_503(self, test_client):
        """Test POST GPS config returns 503 in simulation mode (no client)."""
        response = test_client.post("/api/v2/gps/config", json={"enabled": True})
        assert response.status_code == 503
        assert "simulation mode" in response.json()["detail"].lower()


class TestGPSConfigAPIWithClient:
    """Test GPS configuration API endpoints with mocked client."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Starlink client."""
        client = MagicMock()
        client.get_gps_config.return_value = {
            "enabled": True,
            "ready": True,
            "satellites": 12,
        }
        client.set_gps_config.return_value = {
            "enabled": False,
            "ready": True,
            "satellites": 12,
        }
        return client

    @pytest.mark.asyncio
    async def test_gps_config_get_success(self, test_client, mock_client):
        """Test GET GPS config returns config when client is available."""
        with patch("app.api.gps._starlink_client", mock_client):
            response = test_client.get("/api/v2/gps/config")

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["ready"] is True
        assert data["satellites"] == 12

    @pytest.mark.asyncio
    async def test_gps_config_post_enable(self, test_client, mock_client):
        """Test POST GPS config enables GPS."""
        mock_client.set_gps_config.return_value = {
            "enabled": True,
            "ready": True,
            "satellites": 10,
        }

        with patch("app.api.gps._starlink_client", mock_client):
            response = test_client.post("/api/v2/gps/config", json={"enabled": True})

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        mock_client.set_gps_config.assert_called_once_with(enable=True)

    @pytest.mark.asyncio
    async def test_gps_config_post_disable(self, test_client, mock_client):
        """Test POST GPS config disables GPS."""
        mock_client.set_gps_config.return_value = {
            "enabled": False,
            "ready": True,
            "satellites": 10,
        }

        with patch("app.api.gps._starlink_client", mock_client):
            response = test_client.post("/api/v2/gps/config", json={"enabled": False})

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        mock_client.set_gps_config.assert_called_once_with(enable=False)

    @pytest.mark.asyncio
    async def test_gps_config_post_permission_denied(self, test_client, mock_client):
        """Test POST GPS config returns 403 on permission denied."""
        mock_client.set_gps_config.side_effect = PermissionError(
            "GPS configuration change not permitted"
        )

        with patch("app.api.gps._starlink_client", mock_client):
            response = test_client.post("/api/v2/gps/config", json={"enabled": True})

        assert response.status_code == 403
        assert "not permitted" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_gps_config_get_dish_unavailable(self, test_client, mock_client):
        """Test GET GPS config returns 503 when dish is unavailable."""
        mock_client.get_gps_config.side_effect = Exception("Connection failed")

        with patch("app.api.gps._starlink_client", mock_client):
            response = test_client.get("/api/v2/gps/config")

        assert response.status_code == 503
        assert "starlink dish" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_gps_config_post_invalid_body(self, test_client, mock_client):
        """Test POST GPS config returns 422 for invalid request body."""
        with patch("app.api.gps._starlink_client", mock_client):
            response = test_client.post("/api/v2/gps/config", json={"invalid": "field"})

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_gps_config_post_invalid_type(self, test_client, mock_client):
        """Test POST GPS config returns 422 for invalid enabled type."""
        with patch("app.api.gps._starlink_client", mock_client):
            response = test_client.post(
                "/api/v2/gps/config", json={"enabled": "not_a_bool"}
            )

        assert response.status_code == 422
