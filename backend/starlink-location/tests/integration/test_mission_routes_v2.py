"""Integration tests for mission v2 API endpoints."""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.mission.models import (
    Mission,
    MissionLeg,
    TransportConfig,
    TimelineSegment,
    TimelineStatus,
    MissionLegTimeline,
    Transport,
    TransportState,
)
from app.mission.timeline_service import TimelineSummary
from app.mission.storage import delete_mission, mission_exists, list_missions

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
    from app.mission.storage import delete_mission, list_missions
    # Note: list_missions returns dicts, check keys
    # But wait, list_missions in storage.py lists V1 missions (flat).
    # V2 missions are directories.
    # We should rely on the test to delete, or implement a cleanup that scans directories.
    # For now, we'll try to delete specifically created missions in tests if possible, 
    # or rely on unique IDs to avoid collision.
    pass

class TestMissionV2CreateEndpoint:
    """Tests for POST /api/v2/missions endpoint."""

    def test_create_mission_triggers_timeline_generation(self, client: TestClient, test_mission_v2):
        """Test that creating a mission triggers timeline generation for its legs."""
        
        # Mock build_mission_timeline and save_mission_timeline
        with patch("app.mission.routes_v2.build_mission_timeline") as mock_build, \
             patch("app.mission.routes_v2.save_mission_timeline") as mock_save:
            
            # Setup mock return values
            now = datetime.now(timezone.utc)
            segment = TimelineSegment(
                id="seg-1",
                start_time=now,
                end_time=now + timedelta(hours=1),
                status=TimelineStatus.NOMINAL,
            )
            timeline = MissionLegTimeline(mission_leg_id=test_mission_v2.legs[0].id, segments=[segment])
            summary = TimelineSummary(
                mission_start=now,
                mission_end=now + timedelta(hours=1),
                degraded_seconds=0,
                critical_seconds=0,
                next_conflict_seconds=-1,
                transport_states={},
                sample_count=1,
                sample_interval_seconds=60,
                generation_runtime_ms=10
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
