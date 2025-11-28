"""Integration tests for mission planning CRUD endpoints."""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi.testclient import TestClient

from app.mission.models import (
    MissionLeg,
    Transport,
    TransportConfig,
    TransportState,
    TimelineSegment,
    TimelineStatus,
    MissionLegTimeline,
    XTransition,
    MissionPhase,
)
from app.mission.storage import delete_mission, delete_mission_timeline, mission_exists
from app.mission.timeline_service import TimelineSummary


# Fixtures for test missions
@pytest.fixture
def test_mission():
    """Create a test mission object with unique ID."""
    unique_id = f"test-mission-{uuid4().hex[:8]}"
    return MissionLeg(
        id=unique_id,
        name="Test Mission",
        description="A test mission for unit tests",
        route_id="test-route-001",
        transports=TransportConfig(
            initial_x_satellite_id="X-1",
            initial_ka_satellite_ids=["AOR", "POR", "IOR"],
            x_transitions=[],
            ka_outages=[],
            aar_windows=[],
            ku_overrides=[],
        ),
        is_active=False,
        notes="Test notes",
    )


@pytest.fixture
def test_mission_with_transitions():
    """Create a test mission with satellite transitions and unique ID."""
    unique_id = f"test-mission-transitions-{uuid4().hex[:8]}"
    return MissionLeg(
        id=unique_id,
        name="Mission with Transitions",
        description="Test mission with X transitions",
        route_id="test-route-001",
        transports=TransportConfig(
            initial_x_satellite_id="X-1",
            initial_ka_satellite_ids=["AOR", "POR", "IOR"],
            x_transitions=[
                XTransition(
                    id="transition-1",
                    latitude=35.5,
                    longitude=-120.3,
                    target_satellite_id="X-2",
                    target_beam_id=None,
                    is_same_satellite_transition=False,
                )
            ],
            ka_outages=[],
            aar_windows=[],
            ku_overrides=[],
        ),
        is_active=False,
    )


@pytest.fixture(autouse=True)
def cleanup_test_missions():
    """Clean up test missions after each test."""
    yield
    # Clean up after test - delete all missions that start with our test prefixes
    from app.mission.storage import list_missions
    missions_to_delete = []
    for m in list_missions():
        mission_id = m.get("id", "")
        if mission_id.startswith("test-mission"):
            missions_to_delete.append(mission_id)

    for mission_id in missions_to_delete:
        if mission_exists(mission_id):
            delete_mission(mission_id)


@pytest.fixture(autouse=True)
def stub_timeline_builder(monkeypatch):
    """Stub mission timeline computation to avoid heavy dependencies."""

    def _builder(mission, route_manager, poi_manager=None):
        now = datetime.now(timezone.utc)
        segment = TimelineSegment(
            id=f"{mission.id}-segment",
            start_time=now,
            end_time=now + timedelta(hours=1),
            status=TimelineStatus.NOMINAL,
        )
        timeline = MissionLegTimeline(mission_leg_id=mission.id, segments=[segment])
        summary = TimelineSummary(
            mission_start=now,
            mission_end=now + timedelta(hours=1),
            degraded_seconds=0.0,
            critical_seconds=0.0,
            next_conflict_seconds=-1.0,
            transport_states={
                Transport.X: TransportState.AVAILABLE,
                Transport.KA: TransportState.AVAILABLE,
                Transport.KU: TransportState.AVAILABLE,
            },
            sample_count=2,
            sample_interval_seconds=60,
            generation_runtime_ms=0.0,
        )
        return timeline, summary

    monkeypatch.setattr("app.mission.routes.build_mission_timeline", _builder)


class TestMissionCreateEndpoint:
    """Tests for POST /api/missions endpoint."""

    def test_create_mission_returns_201(self, client: TestClient, test_mission):
        """Test creating a new mission returns 201."""
        response = client.post(
            "/api/missions",
            json=test_mission.model_dump(mode="json"),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == test_mission.id
        assert data["name"] == test_mission.name
        assert data["route_id"] == test_mission.route_id
        assert data["is_active"] is False

    def test_create_mission_persists_to_storage(
        self, client: TestClient, test_mission
    ):
        """Test that created mission is saved to storage."""
        response = client.post(
            "/api/missions",
            json=test_mission.model_dump(mode="json"),
        )
        assert response.status_code == 201

        # Verify mission is in storage
        stored_response = client.get(f"/api/missions/{test_mission.id}")
        assert stored_response.status_code == 200
        assert stored_response.json()["id"] == test_mission.id

    def test_create_mission_sets_timestamps(
        self, client: TestClient, test_mission
    ):
        """Test that created_at and updated_at are set."""
        response = client.post(
            "/api/missions",
            json=test_mission.model_dump(mode="json"),
        )
        assert response.status_code == 201
        data = response.json()
        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_at"] is not None
        assert data["updated_at"] is not None

    def test_create_mission_with_transitions(
        self, client: TestClient, test_mission_with_transitions
    ):
        """Test creating mission with X transitions."""
        response = client.post(
            "/api/missions",
            json=test_mission_with_transitions.model_dump(mode="json"),
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["transports"]["x_transitions"]) == 1
        assert data["transports"]["x_transitions"][0]["id"] == "transition-1"

    def test_create_mission_invalid_data_returns_422(
        self, client: TestClient
    ):
        """Test that invalid mission data returns 422."""
        invalid_mission = {
            "id": "invalid-mission",
            "name": "",  # Empty name is invalid
            "route_id": "test-route",
            "transports": {
                "initial_x_satellite_id": "X-1",
                "initial_ka_satellite_ids": ["AOR"],
                "x_transitions": [],
                "ka_outages": [],
                "aar_windows": [],
                "ku_overrides": [],
            },
        }
        response = client.post("/api/missions", json=invalid_mission)
        assert response.status_code == 422


class TestMissionListEndpoint:
    """Tests for GET /api/missions endpoint."""

    def test_list_missions_empty(self, client: TestClient):
        """Test listing missions when none exist."""
        response = client.get("/api/missions")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["missions"] == []

    def test_list_missions_with_pagination(
        self, client: TestClient, test_mission, test_mission_with_transitions
    ):
        """Test mission listing with pagination."""
        # Create two missions
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))
        client.post(
            "/api/missions",
            json=test_mission_with_transitions.model_dump(mode="json"),
        )

        # Test pagination
        response = client.get("/api/missions?limit=1&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["missions"]) == 1
        assert data["limit"] == 1
        assert data["offset"] == 0

        # Get second page
        response = client.get("/api/missions?limit=1&offset=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["missions"]) == 1

    def test_list_missions_filter_by_route(
        self, client: TestClient, test_mission, test_mission_with_transitions
    ):
        """Test filtering missions by route_id."""
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))
        client.post(
            "/api/missions",
            json=test_mission_with_transitions.model_dump(mode="json"),
        )

        # Filter by route
        response = client.get(f"/api/missions?route_id={test_mission.route_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    def test_list_missions_includes_metadata(
        self, client: TestClient, test_mission
    ):
        """Test that list returns mission metadata."""
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))

        response = client.get("/api/missions")
        assert response.status_code == 200
        data = response.json()
        assert len(data["missions"]) > 0
        mission_meta = data["missions"][0]
        assert mission_meta["id"] == test_mission.id
        assert mission_meta["name"] == test_mission.name


class TestMissionGetEndpoint:
    """Tests for GET /api/missions/{id} endpoint."""

    def test_get_mission_returns_200(self, client: TestClient, test_mission):
        """Test getting an existing mission."""
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))

        response = client.get(f"/api/missions/{test_mission.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_mission.id
        assert data["name"] == test_mission.name

    def test_get_mission_not_found_returns_404(self, client: TestClient):
        """Test getting non-existent mission returns 404."""
        response = client.get("/api/missions/nonexistent-mission")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_get_mission_returns_full_object(
        self, client: TestClient, test_mission_with_transitions
    ):
        """Test that get returns complete mission object."""
        client.post(
            "/api/missions",
            json=test_mission_with_transitions.model_dump(mode="json"),
        )

        response = client.get(f"/api/missions/{test_mission_with_transitions.id}")
        assert response.status_code == 200
        data = response.json()
        assert "transports" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert len(data["transports"]["x_transitions"]) == 1


class TestMissionUpdateEndpoint:
    """Tests for PUT /api/missions/{id} endpoint."""

    def test_update_mission_returns_200(self, client: TestClient, test_mission):
        """Test updating a mission."""
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))

        # Update mission
        updated_data = test_mission.model_dump(mode="json")
        updated_data["name"] = "Updated Mission Name"
        updated_data["description"] = "Updated description"

        response = client.put(
            f"/api/missions/{test_mission.id}",
            json=updated_data,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Mission Name"
        assert data["description"] == "Updated description"

    def test_update_mission_not_found_returns_404(
        self, client: TestClient, test_mission
    ):
        """Test updating non-existent mission returns 404."""
        response = client.put(
            "/api/missions/nonexistent-mission",
            json=test_mission.model_dump(mode="json"),
        )
        assert response.status_code == 404

    def test_update_mission_preserves_created_at(
        self, client: TestClient, test_mission
    ):
        """Test that update preserves original created_at."""
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))

        # Get original created_at
        get_response = client.get(f"/api/missions/{test_mission.id}")
        original_created_at = get_response.json()["created_at"]

        # Update mission
        updated_data = test_mission.model_dump(mode="json")
        updated_data["name"] = "Updated Name"

        update_response = client.put(
            f"/api/missions/{test_mission.id}",
            json=updated_data,
        )
        assert update_response.status_code == 200
        assert update_response.json()["created_at"] == original_created_at

    def test_update_mission_updates_updated_at(
        self, client: TestClient, test_mission
    ):
        """Test that update changes updated_at timestamp."""
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))

        # Get original updated_at
        get_response = client.get(f"/api/missions/{test_mission.id}")
        original_updated_at = get_response.json()["updated_at"]

        # Update mission
        updated_data = test_mission.model_dump(mode="json")
        updated_data["name"] = "Updated Name"

        update_response = client.put(
            f"/api/missions/{test_mission.id}",
            json=updated_data,
        )
        assert update_response.status_code == 200
        # Updated_at should be different (newer)
        new_updated_at = update_response.json()["updated_at"]
        assert new_updated_at != original_updated_at

    def test_update_mission_preserves_active_status(
        self, client: TestClient, test_mission
    ):
        """Test that update doesn't change is_active via PUT."""
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))

        # Update mission with is_active=True (should be ignored)
        updated_data = test_mission.model_dump(mode="json")
        updated_data["is_active"] = True
        updated_data["name"] = "Updated Name"

        response = client.put(
            f"/api/missions/{test_mission.id}",
            json=updated_data,
        )
        assert response.status_code == 200
        # is_active should still be False (preserved from original)
        assert response.json()["is_active"] is False


class TestMissionDeleteEndpoint:
    """Tests for DELETE /api/missions/{id} endpoint."""

    def test_delete_mission_returns_204(self, client: TestClient, test_mission):
        """Test deleting a mission returns 204."""
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))

        response = client.delete(f"/api/missions/{test_mission.id}")
        assert response.status_code == 204

    def test_delete_mission_removes_from_storage(
        self, client: TestClient, test_mission
    ):
        """Test that deleted mission is removed from storage."""
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))

        # Delete mission
        client.delete(f"/api/missions/{test_mission.id}")

        # Verify it's gone
        response = client.get(f"/api/missions/{test_mission.id}")
        assert response.status_code == 404

    def test_delete_nonexistent_mission_returns_404(self, client: TestClient):
        """Test deleting non-existent mission returns 404."""
        response = client.delete("/api/missions/nonexistent-mission")
        assert response.status_code == 404

    def test_delete_active_mission_clears_active_status(
        self, client: TestClient, test_mission
    ):
        """Test that deleting active mission clears active status."""
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))

        # Activate mission
        client.post(f"/api/missions/{test_mission.id}/activate")

        # Delete active mission
        client.delete(f"/api/missions/{test_mission.id}")

        # Try to get active mission
        response = client.get("/api/missions/active")
        assert response.status_code == 404


class TestMissionActivateEndpoint:
    """Tests for POST /api/missions/{id}/activate endpoint."""

    def test_activate_mission_returns_200(self, client: TestClient, test_mission):
        """Test activating a mission."""
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))

        response = client.post(f"/api/missions/{test_mission.id}/activate")
        assert response.status_code == 200
        data = response.json()
        assert data["mission_id"] == test_mission.id
        assert data["is_active"] is True
        assert data["flight_phase"] == MissionPhase.PRE_DEPARTURE.value

    def test_activate_nonexistent_mission_returns_404(self, client: TestClient):
        """Test activating non-existent mission returns 404."""
        response = client.post("/api/missions/nonexistent/activate")
        assert response.status_code == 404

    def test_activate_already_active_mission_returns_409(
        self, client: TestClient, test_mission
    ):
        """Test activating already-active mission returns 409."""
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))

        # Activate first time
        response1 = client.post(f"/api/missions/{test_mission.id}/activate")
        assert response1.status_code == 200

        # Try to activate again
        response2 = client.post(f"/api/missions/{test_mission.id}/activate")
        assert response2.status_code == 409

    def test_activate_deactivates_other_missions(
        self, client: TestClient, test_mission, test_mission_with_transitions
    ):
        """Test that activating one mission deactivates others."""
        # Create and activate first mission
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))
        client.post(f"/api/missions/{test_mission.id}/activate")

        # Create second mission
        client.post(
            "/api/missions",
            json=test_mission_with_transitions.model_dump(mode="json"),
        )

        # Activate second mission
        client.post(
            f"/api/missions/{test_mission_with_transitions.id}/activate"
        )

        # Verify first mission is no longer active
        response = client.get(f"/api/missions/{test_mission.id}")
        assert response.status_code == 200
        assert response.json()["is_active"] is False

        # Verify second mission is active
        response = client.get(
            f"/api/missions/{test_mission_with_transitions.id}"
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is True

    def test_activate_resets_flight_state(self, client: TestClient, test_mission):
        """Test that activation resets flight state to pre_departure."""
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))

        response = client.post(f"/api/missions/{test_mission.id}/activate")
        assert response.status_code == 200
        data = response.json()
        assert data["flight_phase"] == MissionPhase.PRE_DEPARTURE.value

    def test_activate_updates_mission_timestamp(
        self, client: TestClient, test_mission
    ):
        """Test that activation updates mission updated_at."""
        create_response = client.post(
            "/api/missions", json=test_mission.model_dump(mode="json")
        )
        created_updated_at = create_response.json()["updated_at"]

        # Activate mission
        activate_response = client.post(
            f"/api/missions/{test_mission.id}/activate"
        )
        assert activate_response.status_code == 200

        # Verify updated_at was changed
        get_response = client.get(f"/api/missions/{test_mission.id}")
        new_updated_at = get_response.json()["updated_at"]
        assert new_updated_at != created_updated_at


class TestMissionGetActiveEndpoint:
    """Tests for GET /api/missions/active endpoint."""

    def test_get_active_mission_when_none_active_returns_404(
        self, client: TestClient
    ):
        """Test getting active mission when none is active returns 404."""
        response = client.get("/api/missions/active")
        assert response.status_code == 404

    def test_get_active_mission_returns_200(
        self, client: TestClient, test_mission
    ):
        """Test getting active mission returns 200."""
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))
        client.post(f"/api/missions/{test_mission.id}/activate")

        response = client.get("/api/missions/active")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_mission.id
        assert data["is_active"] is True

    def test_get_active_mission_returns_full_object(
        self, client: TestClient, test_mission_with_transitions
    ):
        """Test that get active returns complete mission object."""
        client.post(
            "/api/missions",
            json=test_mission_with_transitions.model_dump(mode="json"),
        )
        client.post(
            f"/api/missions/{test_mission_with_transitions.id}/activate"
        )

        response = client.get("/api/missions/active")
        assert response.status_code == 200
        data = response.json()
        assert "transports" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert len(data["transports"]["x_transitions"]) == 1


class TestMissionRoundtrip:
    """Integration tests for mission export/import workflows."""

    def test_create_get_roundtrip(self, client: TestClient, test_mission):
        """Test creating and getting mission returns same data."""
        # Create mission
        create_response = client.post(
            "/api/missions", json=test_mission.model_dump(mode="json")
        )
        assert create_response.status_code == 201
        created_data = create_response.json()

        # Get mission
        get_response = client.get(f"/api/missions/{test_mission.id}")
        assert get_response.status_code == 200
        retrieved_data = get_response.json()

        # Data should match
        assert created_data["id"] == retrieved_data["id"]
        assert created_data["name"] == retrieved_data["name"]
        assert created_data["route_id"] == retrieved_data["route_id"]

    def test_create_update_get_roundtrip(
        self, client: TestClient, test_mission
    ):
        """Test create, update, get returns updated data."""
        # Create
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))

        # Update
        updated_data = test_mission.model_dump(mode="json")
        updated_data["name"] = "New Name"
        updated_data["notes"] = "New notes"

        update_response = client.put(
            f"/api/missions/{test_mission.id}",
            json=updated_data,
        )
        assert update_response.status_code == 200

        # Get and verify
        get_response = client.get(f"/api/missions/{test_mission.id}")
        assert get_response.status_code == 200
        final_data = get_response.json()
        assert final_data["name"] == "New Name"
        assert final_data["notes"] == "New notes"

    def test_full_mission_lifecycle(
        self, client: TestClient, test_mission_with_transitions
    ):
        """Test complete mission lifecycle: create, list, activate, get active, deactivate (delete)."""
        # Create mission
        create_response = client.post(
            "/api/missions",
            json=test_mission_with_transitions.model_dump(mode="json"),
        )
        assert create_response.status_code == 201

        # List missions
        list_response = client.get("/api/missions")
        assert list_response.status_code == 200
        assert list_response.json()["total"] >= 1

        # Activate mission
        activate_response = client.post(
            f"/api/missions/{test_mission_with_transitions.id}/activate"
        )
        assert activate_response.status_code == 200

        # Get active mission
        active_response = client.get("/api/missions/active")
        assert active_response.status_code == 200
        assert (
            active_response.json()["id"]
            == test_mission_with_transitions.id
        )

        # Delete mission
        delete_response = client.delete(
            f"/api/missions/{test_mission_with_transitions.id}"
        )
        assert delete_response.status_code == 204

        # Verify deleted
        get_response = client.get(
            f"/api/missions/{test_mission_with_transitions.id}"
        )
        assert get_response.status_code == 404


class TestMissionTimelineEndpoints:
    """Tests for mission timeline retrieval APIs."""

    def test_timeline_available_immediately_after_save(
        self, client: TestClient, test_mission
    ):
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))

        response = client.get(f"/api/missions/{test_mission.id}/timeline")
        assert response.status_code == 200
        data = response.json()
        assert data["mission_leg_id"] == test_mission.id
        assert len(data["segments"]) == 1

    def test_timeline_available_after_activation(
        self, client: TestClient, test_mission
    ):
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))
        activate = client.post(f"/api/missions/{test_mission.id}/activate")
        assert activate.status_code == 200

        timeline_response = client.get(f"/api/missions/{test_mission.id}/timeline")
        assert timeline_response.status_code == 200
        data = timeline_response.json()
        assert data["mission_leg_id"] == test_mission.id
        assert len(data["segments"]) == 1

        active_timeline = client.get("/api/missions/active/timeline")
        assert active_timeline.status_code == 200
        assert active_timeline.json()["mission_leg_id"] == test_mission.id

    def test_recompute_requires_existing_mission(self, client: TestClient):
        response = client.post("/api/missions/unknown-mission/timeline/recompute")
        assert response.status_code == 404

    def test_recompute_generates_timeline_without_activation(
        self, client: TestClient, test_mission
    ):
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))
        recompute = client.post(
            f"/api/missions/{test_mission.id}/timeline/recompute"
        )
        assert recompute.status_code == 200
        data = recompute.json()
        assert data["mission_leg_id"] == test_mission.id
        assert len(data["segments"]) == 1

        # Should now be retrievable via standard timeline endpoint
        timeline = client.get(f"/api/missions/{test_mission.id}/timeline")
        assert timeline.status_code == 200


class TestMissionExportEndpoint:
    """Tests for mission timeline export endpoint."""

    def test_export_returns_404_when_timeline_missing(
        self, client: TestClient, test_mission
    ):
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))
        delete_mission_timeline(test_mission.id)
        response = client.post(f"/api/missions/{test_mission.id}/export")
        assert response.status_code == 404

    def test_export_supports_multiple_formats(
        self, client: TestClient, test_mission
    ):
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))
        activate = client.post(f"/api/missions/{test_mission.id}/activate")
        assert activate.status_code == 200

        for fmt, media in [
            ("csv", "text/csv"),
            (
                "xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            ("pdf", "application/pdf"),
        ]:
            response = client.post(
                f"/api/missions/{test_mission.id}/export",
                params={"format": fmt},
            )
            assert response.status_code == 200
            assert response.headers["content-type"].startswith(media)
            disposition = response.headers.get("content-disposition", "")
            assert disposition.endswith(f".{fmt}\"")
            assert len(response.content) > 0


class TestMissionDeactivateEndpoint:
    """Tests for POST /api/missions/active/deactivate endpoint."""

    def test_deactivate_active_mission_returns_200(
        self, client: TestClient, test_mission
    ):
        """Test deactivating an active mission returns 200."""
        # Create and activate mission
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))
        activate_response = client.post(
            f"/api/missions/{test_mission.id}/activate"
        )
        assert activate_response.status_code == 200

        # Deactivate mission
        response = client.post("/api/missions/active/deactivate")
        assert response.status_code == 200
        data = response.json()
        assert data["mission_id"] == test_mission.id
        assert data["is_active"] is False

    def test_deactivate_no_active_mission_returns_404(
        self, client: TestClient
    ):
        """Test deactivating when no mission is active returns 404."""
        response = client.post("/api/missions/active/deactivate")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_deactivate_sets_mission_inactive(
        self, client: TestClient, test_mission
    ):
        """Test that deactivation sets is_active to False."""
        # Create and activate mission
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))
        client.post(f"/api/missions/{test_mission.id}/activate")

        # Verify mission is active
        active_response = client.get("/api/missions/active")
        assert active_response.status_code == 200
        assert active_response.json()["is_active"] is True

        # Deactivate mission
        client.post("/api/missions/active/deactivate")

        # Verify mission is no longer active
        get_response = client.get(f"/api/missions/{test_mission.id}")
        assert get_response.status_code == 200
        assert get_response.json()["is_active"] is False

    def test_deactivate_clears_active_mission_status(
        self, client: TestClient, test_mission
    ):
        """Test that deactivation clears the active mission."""
        # Create and activate mission
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))
        client.post(f"/api/missions/{test_mission.id}/activate")

        # Verify active mission exists
        active_response = client.get("/api/missions/active")
        assert active_response.status_code == 200

        # Deactivate mission
        client.post("/api/missions/active/deactivate")

        # Verify no active mission exists
        active_response = client.get("/api/missions/active")
        assert active_response.status_code == 404

    def test_deactivate_clears_mission_metrics(
        self, client: TestClient, test_mission
    ):
        """Test that deactivation clears mission metrics."""
        # Create and activate mission
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))
        client.post(f"/api/missions/{test_mission.id}/activate")

        # Deactivate mission
        deactivate_response = client.post(
            "/api/missions/active/deactivate"
        )
        assert deactivate_response.status_code == 200
        data = deactivate_response.json()

        # Verify response contains deactivation info
        assert "mission_id" in data
        assert "is_active" in data
        assert "deactivated_at" in data
        assert data["is_active"] is False
        assert data["mission_id"] == test_mission.id

    def test_delete_active_mission_deactivates_route(
        self, client: TestClient, test_mission
    ):
        """Test that deleting active mission deactivates its route."""
        # Create and activate mission
        client.post("/api/missions", json=test_mission.model_dump(mode="json"))
        activate_response = client.post(
            f"/api/missions/{test_mission.id}/activate"
        )
        assert activate_response.status_code == 200

        # Delete the active mission
        delete_response = client.delete(
            f"/api/missions/{test_mission.id}"
        )
        assert delete_response.status_code == 204

        # Verify mission is gone
        get_response = client.get(f"/api/missions/{test_mission.id}")
        assert get_response.status_code == 404

        # Verify no active mission exists
        active_response = client.get("/api/missions/active")
        assert active_response.status_code == 404
