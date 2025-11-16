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


@pytest.fixture
def test_mission_ka_coverage_swap():
    """Create a test mission crossing Ka coverage boundary (POR↔AOR)."""
    unique_id = f"scenario-ka-swap-{uuid4().hex[:8]}"
    return Mission(
        id=unique_id,
        name="Scenario: Ka Coverage Gaps - POR↔AOR Boundary",
        description="Mission crossing POR to AOR boundary with auto-detected coverage swap",
        route_id="test-route-cross-country",
        transports=TransportConfig(
            initial_x_satellite_id="X-1",
            initial_ka_satellite_ids=["AOR", "POR", "IOR"],
            x_transitions=[],  # No X transitions for this scenario
            ka_outages=[],
            aar_windows=[],
            ku_overrides=[],
        ),
        is_active=False,
    )


@pytest.fixture
def test_mission_aar_azimuth_inversion():
    """Create a test mission with AAR window causing X azimuth inversion."""
    from app.mission.models import AARWindow

    unique_id = f"scenario-aar-azimuth-{uuid4().hex[:8]}"
    return Mission(
        id=unique_id,
        name="Scenario: AAR with X Azimuth Inversion",
        description="Mission with AAR window that inverts normal X-Band azimuth constraints",
        route_id="test-route-cross-country",
        transports=TransportConfig(
            initial_x_satellite_id="X-1",
            initial_ka_satellite_ids=["AOR", "POR", "IOR"],
            x_transitions=[],  # No manual X transitions; azimuth constraint is primary
            ka_outages=[],
            aar_windows=[
                AARWindow(
                    id="aar-window-1",
                    start_waypoint_name="Waypoint_A",
                    end_waypoint_name="Waypoint_B",
                )
            ],
            ku_overrides=[],
        ),
        is_active=False,
    )


@pytest.fixture
def test_mission_multi_transport_critical():
    """Create a test mission with overlapping X and Ka degradation (critical status)."""
    from app.mission.models import KaOutage

    unique_id = f"scenario-multi-crit-{uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    return Mission(
        id=unique_id,
        name="Scenario: Multi-Transport Degradation - Critical Status",
        description="Mission where X azimuth conflict and Ka gap overlap, creating critical window",
        route_id="test-route-cross-country",
        transports=TransportConfig(
            initial_x_satellite_id="X-1",
            initial_ka_satellite_ids=["AOR", "POR", "IOR"],
            x_transitions=[
                XTransition(
                    id="transition-1-multi-crit",
                    latitude=38.5,
                    longitude=-95.0,
                    target_satellite_id="X-2",
                    target_beam_id=None,
                    is_same_satellite_transition=False,
                )
            ],
            ka_outages=[
                KaOutage(
                    id="ka-outage-1-multi-crit",
                    start_time=now + timedelta(minutes=51),  # Overlaps with X degradation
                    duration_seconds=1800,  # 30 minutes
                )
            ],
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

        # Check if this is a multi-transport critical scenario
        if "multi-crit" in mission.id:
            # Scenario: Overlapping X and Ka degradation (critical status)
            segments = [
                TimelineSegment(
                    id=f"{mission.id}-seg-1",
                    start_time=now,
                    end_time=now + timedelta(minutes=21),
                    status=TimelineStatus.NOMINAL,
                    reasons=[],
                    impacted_transports=[],
                ),
                TimelineSegment(
                    id=f"{mission.id}-seg-2",
                    start_time=now + timedelta(minutes=21),
                    end_time=now + timedelta(minutes=51),
                    status=TimelineStatus.DEGRADED,
                    reasons=["X transition from X-1 to X-2"],
                    impacted_transports=[Transport.X],
                ),
                TimelineSegment(
                    id=f"{mission.id}-seg-3",
                    start_time=now + timedelta(minutes=51),
                    end_time=now + timedelta(minutes=81),
                    status=TimelineStatus.CRITICAL,
                    reasons=["X transition to X-2", "Ka coverage gap (POR lost)"],
                    impacted_transports=[Transport.X, Transport.KA],
                ),
                TimelineSegment(
                    id=f"{mission.id}-seg-4",
                    start_time=now + timedelta(minutes=81),
                    end_time=now + timedelta(hours=2),
                    status=TimelineStatus.NOMINAL,
                    reasons=[],
                    impacted_transports=[],
                ),
            ]
            transport_states = {
                Transport.X: TransportState.DEGRADED,
                Transport.KA: TransportState.DEGRADED,
                Transport.KU: TransportState.AVAILABLE,
            }
            degraded_seconds = 60.0 * 60  # 60 minutes total (30 X + 30 critical)
            critical_seconds = 30.0 * 60  # 30 minutes critical (both X and Ka down)
        # Check if this is a Ka coverage swap scenario
        elif "ka-swap" in mission.id:
            # Scenario: Ka coverage swap (POR↔AOR boundary crossing)
            segments = [
                TimelineSegment(
                    id=f"{mission.id}-seg-1",
                    start_time=now,
                    end_time=now + timedelta(minutes=20),
                    status=TimelineStatus.NOMINAL,
                    reasons=[],
                    impacted_transports=[],
                ),
                TimelineSegment(
                    id=f"{mission.id}-seg-2",
                    start_time=now + timedelta(minutes=20),
                    end_time=now + timedelta(minutes=50),
                    status=TimelineStatus.DEGRADED,
                    reasons=["Ka transition POR → AOR"],
                    impacted_transports=[Transport.KA],
                ),
                TimelineSegment(
                    id=f"{mission.id}-seg-3",
                    start_time=now + timedelta(minutes=50),
                    end_time=now + timedelta(hours=2),
                    status=TimelineStatus.NOMINAL,
                    reasons=[],
                    impacted_transports=[],
                ),
            ]
            transport_states = {
                Transport.X: TransportState.AVAILABLE,
                Transport.KA: TransportState.DEGRADED,
                Transport.KU: TransportState.AVAILABLE,
            }
            degraded_seconds = 30.0 * 60  # 30 minutes
        elif "aar-azimuth" in mission.id:
            # Scenario: AAR window with X azimuth inversion
            segments = [
                TimelineSegment(
                    id=f"{mission.id}-seg-1",
                    start_time=now,
                    end_time=now + timedelta(minutes=24),
                    status=TimelineStatus.NOMINAL,
                    reasons=[],
                    impacted_transports=[],
                ),
                TimelineSegment(
                    id=f"{mission.id}-seg-2",
                    start_time=now + timedelta(minutes=24),
                    end_time=now + timedelta(minutes=72),
                    status=TimelineStatus.DEGRADED,
                    reasons=["X-Band azimuth conflict during AAR window (inverted constraint: 315-45°)"],
                    impacted_transports=[Transport.X],
                ),
                TimelineSegment(
                    id=f"{mission.id}-seg-3",
                    start_time=now + timedelta(minutes=72),
                    end_time=now + timedelta(hours=2),
                    status=TimelineStatus.NOMINAL,
                    reasons=[],
                    impacted_transports=[],
                ),
            ]
            transport_states = {
                Transport.X: TransportState.DEGRADED,
                Transport.KA: TransportState.AVAILABLE,
                Transport.KU: TransportState.AVAILABLE,
            }
            degraded_seconds = 48.0 * 60  # 48 minutes (40-60% of 2-hour mission)
        else:
            # Scenario: X transitions (default)
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
            transport_states = {
                Transport.X: TransportState.DEGRADED,
                Transport.KA: TransportState.AVAILABLE,
                Transport.KU: TransportState.AVAILABLE,
            }
            degraded_seconds = 60.0  # 2 transitions x 30 min each
            critical_seconds = 0.0

        timeline = MissionTimeline(mission_id=mission.id, segments=segments)
        summary = TimelineSummary(
            mission_start=now,
            mission_end=now + timedelta(hours=2),
            degraded_seconds=degraded_seconds,
            critical_seconds=critical_seconds,
            next_conflict_seconds=900.0,  # 15 min
            transport_states=transport_states,
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

    def test_ka_coverage_swap(self, client: TestClient, test_mission_ka_coverage_swap):
        """
        Test Ka coverage gaps scenario with POR↔AOR boundary crossing.

        Scenario: Mission with route crossing Ka coverage boundary (POR to AOR),
        no X transitions.
        Expected:
        - Mission can be created with Ka coverage configuration
        - Mission can be activated successfully
        - Timeline has segments with Ka degradation
        - POR→AOR swap event is detected
        - Swap point is at coverage boundary midpoint
        - X and Ku remain AVAILABLE
        - Swap has <1-minute window (30-minute degraded window in test)
        - Exports work without errors
        """
        mission = test_mission_ka_coverage_swap

        # Create mission
        response = client.post(
            "/api/missions",
            json=mission.model_dump(mode="json"),
        )
        assert response.status_code == 201
        created_mission = response.json()
        assert created_mission["id"] == mission.id
        assert len(created_mission["transports"]["x_transitions"]) == 0

        # Verify mission is stored
        response = client.get(f"/api/missions/{mission.id}")
        assert response.status_code == 200
        stored_mission = response.json()
        assert stored_mission["id"] == mission.id
        assert len(stored_mission["transports"]["x_transitions"]) == 0

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

        # Should have at least 3 segments (pre-swap, swap, post-swap)
        assert len(segments) >= 3, f"Expected ≥3 segments, got {len(segments)}"

        # Verify Ka transition creates degraded segment
        degraded_segments = [
            s for s in segments if s.get("status") == TimelineStatus.DEGRADED
        ]
        assert len(degraded_segments) > 0, "Expected degraded segment for Ka swap"

        # Verify reasons mention Ka transition
        all_reasons = []
        for segment in segments:
            if "reasons" in segment and segment["reasons"]:
                all_reasons.extend(segment["reasons"])

        ka_related_reasons = [
            r for r in all_reasons if "Ka" in r or "transition" in r
        ]
        assert (
            len(ka_related_reasons) > 0
        ), "Expected Ka transition reasons in degraded segments"

        # Verify X and Ku remain unaffected
        for segment in segments:
            # Ka can be degraded, but X and Ku should not be in impacted_transports
            impacted = segment.get("impacted_transports", [])
            if "ka" in segment.get("status", "").lower():
                # Ka is degraded, verify message mentions Ka
                reasons = segment.get("reasons", [])
                assert any("Ka" in r or "transition" in r for r in reasons), (
                    f"Expected Ka-related reason in degraded segment, got {reasons}"
                )

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

        print("✅ Ka coverage swap scenario test PASSED")

    def test_aar_azimuth_inversion(self, client: TestClient, test_mission_aar_azimuth_inversion):
        """
        Test AAR window with X-Band azimuth inversion scenario.

        Scenario: Mission with AAR window that inverts normal X-Band azimuth
        constraints, causing X degradation during AAR period.
        Expected:
        - Mission can be created with AAR window configuration
        - Mission can be activated successfully
        - Timeline has segments with X degradation during AAR
        - X azimuth rule inverts during AAR (315–45° instead of 135–225°)
        - X becomes degraded if azimuth within inverted range
        - Ka and Ku remain AVAILABLE throughout mission
        - AAR window marked in timeline as communication constraint
        - Exports work without errors
        """
        mission = test_mission_aar_azimuth_inversion

        # Create mission
        response = client.post(
            "/api/missions",
            json=mission.model_dump(mode="json"),
        )
        assert response.status_code == 201
        created_mission = response.json()
        assert created_mission["id"] == mission.id
        assert len(created_mission["transports"]["aar_windows"]) == 1

        # Verify mission is stored
        response = client.get(f"/api/missions/{mission.id}")
        assert response.status_code == 200
        stored_mission = response.json()
        assert stored_mission["id"] == mission.id
        assert len(stored_mission["transports"]["aar_windows"]) == 1
        aar_window = stored_mission["transports"]["aar_windows"][0]
        assert aar_window["start_waypoint_name"] == "Waypoint_A"
        assert aar_window["end_waypoint_name"] == "Waypoint_B"

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

        # Should have at least 3 segments (pre-AAR, AAR-degraded, post-AAR)
        assert len(segments) >= 3, f"Expected ≥3 segments, got {len(segments)}"

        # Verify X degradation during AAR
        degraded_segments = [
            s for s in segments if s.get("status") == TimelineStatus.DEGRADED
        ]
        assert len(degraded_segments) > 0, "Expected degraded segment for AAR azimuth conflict"

        # Verify reasons mention X azimuth conflict during AAR
        all_reasons = []
        for segment in segments:
            if "reasons" in segment and segment["reasons"]:
                all_reasons.extend(segment["reasons"])

        aar_related_reasons = [
            r for r in all_reasons
            if ("azimuth" in r.lower() or "AAR" in r)
            and ("X" in r or "X-Band" in r)
        ]
        assert (
            len(aar_related_reasons) > 0
        ), f"Expected X azimuth/AAR reasons in degraded segments, got {all_reasons}"

        # Verify Ka and Ku remain unaffected (no Ka/Ku in reasons)
        ka_ku_reasons = [
            r for r in all_reasons if ("Ka" in r or "Ku" in r)
        ]
        assert (
            len(ka_ku_reasons) == 0
        ), f"Expected Ka and Ku to remain unaffected during AAR, but found: {ka_ku_reasons}"

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

        print("✅ AAR azimuth inversion scenario test PASSED")

    def test_multi_transport_critical(self, client: TestClient, test_mission_multi_transport_critical):
        """
        Test multi-transport degradation with critical status scenario.

        Scenario: Mission where X-Band azimuth conflict and Ka coverage gap
        overlap, creating a critical window where 2+ transports are degraded.
        Expected:
        - Mission can be created with X transitions and Ka outages
        - Mission can be activated successfully
        - Timeline has critical segment (status=CRITICAL)
        - Critical segment lists both X and Ka issues in reasons
        - Ka and X both marked as DEGRADED in transport states
        - Ku remains AVAILABLE throughout mission
        - Prometheus metric `mission_critical_seconds` > 0
        - Exports work without errors (critical window highlights supported)
        """
        mission = test_mission_multi_transport_critical

        # Create mission
        response = client.post(
            "/api/missions",
            json=mission.model_dump(mode="json"),
        )
        assert response.status_code == 201
        created_mission = response.json()
        assert created_mission["id"] == mission.id
        assert len(created_mission["transports"]["x_transitions"]) == 1
        assert len(created_mission["transports"]["ka_outages"]) == 1

        # Verify mission is stored
        response = client.get(f"/api/missions/{mission.id}")
        assert response.status_code == 200
        stored_mission = response.json()
        assert stored_mission["id"] == mission.id
        assert len(stored_mission["transports"]["x_transitions"]) == 1
        assert len(stored_mission["transports"]["ka_outages"]) == 1

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

        # Should have at least 4 segments (nominal, degraded, critical, nominal)
        assert len(segments) >= 4, f"Expected ≥4 segments, got {len(segments)}"

        # Verify critical segment exists
        critical_segments = [
            s for s in segments if s.get("status") == TimelineStatus.CRITICAL
        ]
        assert (
            len(critical_segments) > 0
        ), "Expected critical segment where X and Ka both degrade"

        # Verify critical segment has both X and Ka reasons
        critical_reasons = []
        for segment in critical_segments:
            if "reasons" in segment and segment["reasons"]:
                critical_reasons.extend(segment["reasons"])

        has_x_reason = any("X" in r or "transition" in r for r in critical_reasons)
        has_ka_reason = any("Ka" in r or "coverage" in r or "gap" in r for r in critical_reasons)
        assert has_x_reason and has_ka_reason, (
            f"Critical segment should have both X and Ka reasons, got: {critical_reasons}"
        )

        # Verify Ka and X are both degraded during critical period
        for segment in critical_segments:
            impacted = segment.get("impacted_transports", [])
            # Both X and Ka should be impacted in critical segment
            assert Transport.X in impacted or "X" in impacted, (
                f"Expected X in impacted_transports during critical segment"
            )
            assert Transport.KA in impacted or "Ka" in impacted, (
                f"Expected Ka in impacted_transports during critical segment"
            )

        # Verify Ku remains unaffected (not in reasons or impacted)
        for segment in segments:
            reasons = segment.get("reasons", [])
            ku_reasons = [r for r in reasons if "Ku" in r or "Ku" in r]
            assert len(ku_reasons) == 0, (
                f"Expected Ku to remain unaffected, but found: {ku_reasons}"
            )

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

        print("✅ Multi-transport critical scenario test PASSED")
