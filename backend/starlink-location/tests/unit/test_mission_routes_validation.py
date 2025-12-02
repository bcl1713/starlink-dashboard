"""Unit tests for mission route validation logic."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException, status
from app.mission.models import MissionLeg, TransportConfig
from app.mission.routes import create_mission, update_mission


@pytest.mark.asyncio
async def test_create_mission_invalid_route():
    """Test creating a mission with a non-existent route ID."""
    # Setup mock dependencies
    mock_route_manager = MagicMock()
    mock_route_manager.get_route.return_value = None  # Simulate route not found

    mock_poi_manager = MagicMock()

    mission = MissionLeg(
        id="mission-test-1",
        name="Test Mission",
        route_id="invalid-route-id",
        transports=TransportConfig(initial_x_satellite_id="X-1"),
    )

    # Expect HTTPException 422
    with pytest.raises(HTTPException) as exc_info:
        await create_mission(
            mission=mission,
            route_manager=mock_route_manager,
            poi_manager=mock_poi_manager,
        )

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "Route invalid-route-id not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_update_mission_invalid_route():
    """Test updating a mission with a non-existent route ID."""
    # Setup mock dependencies
    mock_route_manager = MagicMock()
    mock_route_manager.get_route.return_value = None  # Simulate route not found

    mock_poi_manager = MagicMock()

    # We need to mock mission_exists and load_mission since update_mission calls them
    with patch("app.mission.routes.mission_exists", return_value=True), patch(
        "app.mission.routes.load_mission"
    ) as mock_load:

        # Setup existing mission return
        existing_mission = MissionLeg(
            id="mission-test-1",
            name="Old Name",
            route_id="old-route",
            transports=TransportConfig(initial_x_satellite_id="X-1"),
        )
        mock_load.return_value = existing_mission

        mission_update = MissionLeg(
            id="mission-test-1",
            name="New Name",
            route_id="invalid-route-id",
            transports=TransportConfig(initial_x_satellite_id="X-1"),
        )

        # Expect HTTPException 422
        with pytest.raises(HTTPException) as exc_info:
            await update_mission(
                mission_id="mission-test-1",
                mission_update=mission_update,
                route_manager=mock_route_manager,
                poi_manager=mock_poi_manager,
            )

        assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Route invalid-route-id not found" in exc_info.value.detail
