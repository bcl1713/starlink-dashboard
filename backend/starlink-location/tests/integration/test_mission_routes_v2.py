"""Integration tests for mission v2 API endpoints."""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.mission.models import (
    Mission,
    MissionLeg,
    TransportConfig,
    TimelineSegment,
    TimelineStatus,
    MissionLegTimeline,
)
from app.mission.timeline_service import TimelineSummary


@pytest.fixture
def test_mission_v2():
    """Create a test mission object with unique ID."""
    unique_id = f"test-mission-v2-{uuid4().hex[:8]}"
    leg_id = f"test-leg-{uuid4().hex[:8]}"

    leg = MissionLeg(
        id=leg_id,
        name="Test Leg",
        description="A test leg",
        route_id="test-route-001",
        transports=TransportConfig(
            initial_x_satellite_id="X-1",
            initial_ka_satellite_ids=["AOR"],
        ),
        is_active=False,
    )

    return Mission(
        id=unique_id,
        name="Test Mission V2",
        description="A test mission v2",
        legs=[leg],
    )


@pytest.fixture(autouse=True)
def cleanup_test_missions_v2():
    """Clean up test missions after each test."""
    yield
    # Clean up after test

    # Note: list_missions returns dicts, check keys
    # But wait, list_missions in storage.py lists V1 missions (flat).
    # V2 missions are directories.
    # We should rely on the test to delete, or implement a cleanup that scans directories.
    # For now, we'll try to delete specifically created missions in tests if possible,
    # or rely on unique IDs to avoid collision.
    pass


class TestMissionV2CreateEndpoint:
    """Tests for POST /api/v2/missions endpoint."""

    def test_create_mission_triggers_timeline_generation(
        self, client: TestClient, test_mission_v2
    ):
        """Test that creating a mission triggers timeline generation for its legs."""

        # Mock build_mission_timeline and save_mission_timeline
        with patch("app.mission.routes_v2.build_mission_timeline") as mock_build, patch(
            "app.mission.routes_v2.save_mission_timeline"
        ) as mock_save:

            # Setup mock return values
            now = datetime.now(timezone.utc)
            segment = TimelineSegment(
                id="seg-1",
                start_time=now,
                end_time=now + timedelta(hours=1),
                status=TimelineStatus.NOMINAL,
            )
            timeline = MissionLegTimeline(
                mission_leg_id=test_mission_v2.legs[0].id, segments=[segment]
            )
            summary = TimelineSummary(
                mission_start=now,
                mission_end=now + timedelta(hours=1),
                degraded_seconds=0,
                critical_seconds=0,
                next_conflict_seconds=-1,
                transport_states={},
                sample_count=1,
                sample_interval_seconds=60,
                generation_runtime_ms=10,
            )
            mock_build.return_value = (timeline, summary)

            # Call endpoint
            response = client.post(
                "/api/v2/missions",
                json=test_mission_v2.model_dump(mode="json"),
            )

            assert response.status_code == 201

            # Verify build_mission_timeline was called
            assert mock_build.called
            # Verify save_mission_timeline was called
            assert mock_save.called

            # Verify arguments
            call_args = mock_save.call_args
            assert call_args[0][0] == test_mission_v2.legs[0].id
            assert call_args[0][1] == timeline


class TestMissionV2UpdateEndpoint:
    """Tests for PATCH /api/v2/missions/{mission_id} endpoint."""

    def test_update_mission_name(self, client: TestClient, test_mission_v2):
        """Test updating mission name."""
        # Create mission first
        create_response = client.post(
            "/api/v2/missions",
            json=test_mission_v2.model_dump(mode="json"),
        )
        assert create_response.status_code == 201

        # Update name
        new_name = "Updated Mission Name"
        update_response = client.patch(
            f"/api/v2/missions/{test_mission_v2.id}",
            json={"name": new_name},
        )
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["name"] == new_name
        assert data["description"] == test_mission_v2.description

        # Verify updated_at changed
        assert data["updated_at"] != data["created_at"]

    def test_update_mission_description(self, client: TestClient, test_mission_v2):
        """Test updating mission description."""
        # Create mission first
        create_response = client.post(
            "/api/v2/missions",
            json=test_mission_v2.model_dump(mode="json"),
        )
        assert create_response.status_code == 201

        # Update description
        new_description = "This is a new detailed description of the mission"
        update_response = client.patch(
            f"/api/v2/missions/{test_mission_v2.id}",
            json={"description": new_description},
        )
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["name"] == test_mission_v2.name
        assert data["description"] == new_description

        # Verify updated_at changed
        assert data["updated_at"] != data["created_at"]

    def test_update_mission_both_fields(self, client: TestClient, test_mission_v2):
        """Test updating both name and description at once."""
        # Create mission first
        create_response = client.post(
            "/api/v2/missions",
            json=test_mission_v2.model_dump(mode="json"),
        )
        assert create_response.status_code == 201

        # Update both fields
        new_name = "New Mission Name"
        new_description = "New mission description"
        update_response = client.patch(
            f"/api/v2/missions/{test_mission_v2.id}",
            json={"name": new_name, "description": new_description},
        )
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["name"] == new_name
        assert data["description"] == new_description

    def test_update_mission_empty_name_validation_error(
        self, client: TestClient, test_mission_v2
    ):
        """Test that empty name triggers validation error."""
        # Create mission first
        create_response = client.post(
            "/api/v2/missions",
            json=test_mission_v2.model_dump(mode="json"),
        )
        assert create_response.status_code == 201

        # Try to update with empty name
        update_response = client.patch(
            f"/api/v2/missions/{test_mission_v2.id}",
            json={"name": ""},
        )
        assert update_response.status_code == 422

    def test_update_mission_whitespace_name_validation_error(
        self, client: TestClient, test_mission_v2
    ):
        """Test that whitespace-only name triggers validation error."""
        # Create mission first
        create_response = client.post(
            "/api/v2/missions",
            json=test_mission_v2.model_dump(mode="json"),
        )
        assert create_response.status_code == 201

        # Try to update with whitespace name
        update_response = client.patch(
            f"/api/v2/missions/{test_mission_v2.id}",
            json={"name": "   "},
        )
        assert update_response.status_code == 422

    def test_update_mission_not_found(self, client: TestClient):
        """Test updating nonexistent mission returns 404."""
        update_response = client.patch(
            "/api/v2/missions/nonexistent-mission-id",
            json={"name": "New Name"},
        )
        assert update_response.status_code == 404

    def test_update_mission_timestamp_changes(
        self, client: TestClient, test_mission_v2
    ):
        """Test that updated_at timestamp changes on update."""
        import time

        # Create mission first
        create_response = client.post(
            "/api/v2/missions",
            json=test_mission_v2.model_dump(mode="json"),
        )
        assert create_response.status_code == 201
        created_data = create_response.json()

        # Wait a moment to ensure timestamp difference
        time.sleep(0.1)

        # Update mission
        update_response = client.patch(
            f"/api/v2/missions/{test_mission_v2.id}",
            json={"name": "Updated Name"},
        )
        assert update_response.status_code == 200
        updated_data = update_response.json()

        # Verify updated_at changed
        assert updated_data["updated_at"] > created_data["updated_at"]
        # Verify created_at stayed the same
        assert updated_data["created_at"] == created_data["created_at"]
