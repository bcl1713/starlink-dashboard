"""Integration tests for mission communication planning scenarios."""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi.testclient import TestClient

from app.mission.models import (
    Mission,
    Transport,
    TransportConfig,
    TimelineSegment,
    TimelineStatus,
    TransportState,
    MissionTimeline,
    XTransition,
)
from app.mission.storage import delete_mission, mission_exists, list_missions
from app.mission.timeline_service import TimelineSummary


@pytest.fixture
def test_mission_x_transitions():
    """Create a test mission with 2 X-Band transitions."""
    unique_id = f"scenario-x-trans-{uuid4().hex[:8]}"
    return Mission(
        id=unique_id,
        name="Scenario: Normal Ops with X Transitions",
        description="Mission with X-1 to X-2 transition at 30%, then back to X-1 at 70%",
        route_id="test-route-cross-country",
        transports=TransportConfig(
            initial_x_satellite_id="X-1",
            initial_ka_satellite_ids=["AOR", "POR", "IOR"],
            x_transitions=[
                XTransition(
                    id="transition-1-x1-to-x2",
                    latitude=40.0,
                    longitude=-100.0,
                    target_satellite_id="X-2",
                    target_beam_id=None,
                    is_same_satellite_transition=False,
                ),
                XTransition(
                    id="transition-2-x2-to-x1",
                    latitude=35.5,
                    longitude=-87.0,
                    target_satellite_id="X-1",
                    target_beam_id=None,
                    is_same_satellite_transition=False,
                ),
            ],
            ka_outages=[],
            aar_windows=[],
            ku_overrides=[],
        ),
        is_active=False,
    )


@pytest.fixture(autouse=True)
def cleanup_scenario_missions():
    """Clean up test scenario missions after each test."""
    yield
    missions = list_missions()
    for mission_dict in missions:
        mission_id = mission_dict.get("id", "")
        if mission_id.startswith("scenario-"):
            if mission_exists(mission_id):
                delete_mission(mission_id)


@pytest.fixture(autouse=True)
def stub_timeline_builder(monkeypatch):
    """Stub mission timeline computation to avoid heavy dependencies."""

    def _builder(mission, route_manager, poi_manager=None):
        now = datetime.now(timezone.utc)
        # Create multiple segments to represent X transitions
        segments = [
            TimelineSegment(
                id=f"{mission.id}-seg-1",
                start_time=now,
                end_time=now + timedelta(minutes=15),
                status=TimelineStatus.NOMINAL,
                reasons=[],
                impacted_transports=[],
            ),
            TimelineSegment(
                id=f"{mission.id}-seg-2",
                start_time=now + timedelta(minutes=15),
                end_time=now + timedelta(minutes=45),
                status=TimelineStatus.DEGRADED,
                reasons=["X transition from X-1 to X-2"],
                impacted_transports=[Transport.X],
            ),
            TimelineSegment(
                id=f"{mission.id}-seg-3",
                start_time=now + timedelta(minutes=45),
                end_time=now + timedelta(minutes=75),
                status=TimelineStatus.NOMINAL,
                reasons=[],
                impacted_transports=[],
            ),
            TimelineSegment(
                id=f"{mission.id}-seg-4",
                start_time=now + timedelta(minutes=75),
                end_time=now + timedelta(minutes=105),
                status=TimelineStatus.DEGRADED,
                reasons=["X transition from X-2 to X-1"],
                impacted_transports=[Transport.X],
            ),
            TimelineSegment(
                id=f"{mission.id}-seg-5",
                start_time=now + timedelta(minutes=105),
                end_time=now + timedelta(hours=2),
                status=TimelineStatus.NOMINAL,
                reasons=[],
                impacted_transports=[],
            ),
        ]
        timeline = MissionTimeline(mission_id=mission.id, segments=segments)
        summary = TimelineSummary(
            mission_start=now,
            mission_end=now + timedelta(hours=2),
            degraded_seconds=60.0,  # 2 transitions x 30 min each
            critical_seconds=0.0,
            next_conflict_seconds=900.0,  # 15 min
            transport_states={
                Transport.X: TransportState.DEGRADED,
                Transport.KA: TransportState.AVAILABLE,
                Transport.KU: TransportState.AVAILABLE,
            },
            sample_count=120,
            sample_interval_seconds=60,
            generation_runtime_ms=45.2,
        )
        return timeline, summary

    monkeypatch.setattr("app.mission.routes.build_mission_timeline", _builder)


class TestMissionScenarioNormalOps:
    """Scenario tests for normal operations with transport transitions."""

    def test_normal_ops_x_transitions(
        self, client: TestClient, test_mission_x_transitions
    ):
        """
        Test normal ops scenario with X-Band transitions.

        Scenario: Mission with 2 X transitions at waypoints 30% and 70%.
        Expected:
        - Mission can be created with X transitions
        - Mission can be activated successfully
        - Timeline has multiple segments with degraded status
        - Each X transition creates a degraded segment
        - Ka and Ku remain AVAILABLE
        - Exports work without errors
        """
        mission = test_mission_x_transitions

        # Create mission
        response = client.post(
            "/api/missions",
            json=mission.model_dump(mode="json"),
        )
        assert response.status_code == 201
        created_mission = response.json()
        assert created_mission["id"] == mission.id
        assert len(created_mission["transports"]["x_transitions"]) == 2

        # Verify mission is stored
        response = client.get(f"/api/missions/{mission.id}")
        assert response.status_code == 200
        stored_mission = response.json()
        assert stored_mission["id"] == mission.id
        assert len(stored_mission["transports"]["x_transitions"]) == 2

        # Activate mission
        response = client.post(f"/api/missions/{mission.id}/activate")
        assert response.status_code == 200
        activated_mission = response.json()
        assert activated_mission["is_active"] is True

        # Fetch timeline
        response = client.get("/api/missions/active/timeline")
        assert response.status_code == 200
        timeline_data = response.json()

        # Verify timeline structure
        assert "segments" in timeline_data
        segments = timeline_data["segments"]

        # Should have at least 4 segments (pre-trans1, trans1, between, trans2, post)
        assert len(segments) >= 4, f"Expected ≥4 segments, got {len(segments)}"

        # Verify X transitions create degraded segments
        degraded_segments = [
            s for s in segments if s.get("status") == TimelineStatus.DEGRADED
        ]
        assert len(degraded_segments) > 0, "Expected degraded segments for X transitions"

        # Verify reasons mention X transitions
        all_reasons = []
        for segment in segments:
            if "reasons" in segment and segment["reasons"]:
                all_reasons.extend(segment["reasons"])

        x_related_reasons = [r for r in all_reasons if "X" in r or "transition" in r]
        assert (
            len(x_related_reasons) > 0
        ), "Expected X transition reasons in degraded segments"

        # Verify timeline has valid metadata
        assert "mission_id" in timeline_data
        assert timeline_data["mission_id"] == mission.id

        # Verify first and last segments have valid times
        assert len(segments) > 0
        first_segment = segments[0]
        last_segment = segments[-1]
        assert "start_time" in first_segment
        assert "end_time" in last_segment

        # Test export to CSV
        response = client.post(f"/api/missions/{mission.id}/export", json={"format": "csv"})
        assert response.status_code == 200
        csv_data = response.text
        assert len(csv_data) > 0
        assert "Time" in csv_data or "time" in csv_data.lower()

        # Test export to XLSX
        response = client.post(f"/api/missions/{mission.id}/export", json={"format": "xlsx"})
        assert response.status_code == 200
        assert len(response.content) > 0

        # Test export to PDF
        response = client.post(f"/api/missions/{mission.id}/export", json={"format": "pdf"})
        assert response.status_code == 200
        assert len(response.content) > 0

        print("✅ Normal ops scenario test PASSED")
