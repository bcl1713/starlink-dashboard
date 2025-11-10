"""Unit tests for mission data models."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.mission.models import (
    AARWindow,
    KaOutage,
    KuOutageOverride,
    Mission,
    MissionPhase,
    MissionTimeline,
    TimelineAdvisory,
    TimelineSegment,
    TimelineStatus,
    Transport,
    TransportConfig,
    TransportState,
    XTransition,
)


class TestXTransition:
    """Tests for XTransition model."""

    def test_create_valid_transition(self):
        """Test creating a valid X transition."""
        transition = XTransition(
            id="x-trans-1",
            latitude=35.5,
            longitude=-120.3,
            target_satellite_id="X-1",
        )
        assert transition.id == "x-trans-1"
        assert transition.latitude == 35.5
        assert transition.longitude == -120.3
        assert transition.target_satellite_id == "X-1"
        assert transition.is_same_satellite_transition is False

    def test_invalid_latitude(self):
        """Test that invalid latitude raises validation error."""
        with pytest.raises(ValueError, match="Latitude must be between -90 and 90"):
            XTransition(
                id="x-trans-1",
                latitude=91.0,
                longitude=-120.3,
                target_satellite_id="X-1",
            )

    def test_invalid_longitude(self):
        """Test that invalid longitude raises validation error."""
        with pytest.raises(ValueError, match="Longitude must be between -180 and 360"):
            XTransition(
                id="x-trans-1",
                latitude=35.5,
                longitude=370.0,
                target_satellite_id="X-1",
            )

    def test_longitude_normalization(self):
        """Test that longitude is normalized to -180 to 180 range."""
        transition = XTransition(
            id="x-trans-1",
            latitude=35.5,
            longitude=200.0,  # Normalize to -160.0
            target_satellite_id="X-1",
        )
        assert transition.longitude == -160.0

    def test_same_satellite_transition(self):
        """Test creating a same-satellite transition."""
        transition = XTransition(
            id="x-trans-1",
            latitude=35.5,
            longitude=-120.3,
            target_satellite_id="X-1",
            target_beam_id="beam-B",
            is_same_satellite_transition=True,
        )
        assert transition.is_same_satellite_transition is True
        assert transition.target_beam_id == "beam-B"


class TestKaOutage:
    """Tests for KaOutage model."""

    def test_create_valid_outage(self):
        """Test creating a valid Ka outage."""
        now = datetime.now(timezone.utc)
        outage = KaOutage(
            id="ka-outage-1",
            start_time=now,
            duration_seconds=600.0,
        )
        assert outage.id == "ka-outage-1"
        assert outage.start_time == now
        assert outage.duration_seconds == 600.0

    def test_invalid_duration(self):
        """Test that zero or negative duration raises validation error."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError):
            KaOutage(
                id="ka-outage-1",
                start_time=now,
                duration_seconds=0.0,
            )


class TestAARWindow:
    """Tests for AARWindow model."""

    def test_create_valid_aar_window(self):
        """Test creating a valid AAR window."""
        aar = AARWindow(
            id="aar-1",
            start_waypoint_name="AAR-Start",
            end_waypoint_name="AAR-End",
        )
        assert aar.id == "aar-1"
        assert aar.start_waypoint_name == "AAR-Start"
        assert aar.end_waypoint_name == "AAR-End"


class TestKuOutageOverride:
    """Tests for KuOutageOverride model."""

    def test_create_valid_override(self):
        """Test creating a valid Ku outage override."""
        now = datetime.now(timezone.utc)
        override = KuOutageOverride(
            id="ku-outage-1",
            start_time=now,
            duration_seconds=300.0,
            reason="Planned maintenance",
        )
        assert override.id == "ku-outage-1"
        assert override.start_time == now
        assert override.duration_seconds == 300.0
        assert override.reason == "Planned maintenance"


class TestTransportConfig:
    """Tests for TransportConfig model."""

    def test_create_valid_config(self):
        """Test creating a valid transport configuration."""
        config = TransportConfig(
            initial_x_satellite_id="X-1",
            initial_ka_satellite_ids=["T2-1", "T2-2", "T2-3"],
            x_transitions=[],
            ka_outages=[],
            aar_windows=[],
            ku_overrides=[],
        )
        assert config.initial_x_satellite_id == "X-1"
        assert len(config.initial_ka_satellite_ids) == 3
        assert config.initial_ka_satellite_ids == ["T2-1", "T2-2", "T2-3"]

    def test_default_ka_satellites(self):
        """Test that default Ka satellites are assigned."""
        config = TransportConfig(initial_x_satellite_id="X-1")
        assert config.initial_ka_satellite_ids == ["T2-1", "T2-2", "T2-3"]

    def test_with_transitions(self):
        """Test config with transitions."""
        transition = XTransition(
            id="x-trans-1",
            latitude=35.5,
            longitude=-120.3,
            target_satellite_id="X-2",
        )
        config = TransportConfig(
            initial_x_satellite_id="X-1",
            x_transitions=[transition],
        )
        assert len(config.x_transitions) == 1
        assert config.x_transitions[0].id == "x-trans-1"


class TestMission:
    """Tests for Mission model."""

    def test_create_valid_mission(self):
        """Test creating a valid mission."""
        mission = Mission(
            id="mission-001",
            name="Leg 6 Rev 6",
            route_id="leg-6-rev-6",
            transports=TransportConfig(initial_x_satellite_id="X-1"),
        )
        assert mission.id == "mission-001"
        assert mission.name == "Leg 6 Rev 6"
        assert mission.route_id == "leg-6-rev-6"
        assert mission.is_active is False
        assert mission.created_at is not None
        assert mission.updated_at is not None

    def test_mission_with_description_and_notes(self):
        """Test mission with optional fields."""
        mission = Mission(
            id="mission-002",
            name="Test Mission",
            description="A test mission for unit testing",
            route_id="test-route",
            transports=TransportConfig(initial_x_satellite_id="X-1"),
            notes="Ready for customer review",
        )
        assert mission.description == "A test mission for unit testing"
        assert mission.notes == "Ready for customer review"

    def test_mission_json_serialization(self):
        """Test that mission can be serialized to JSON."""
        mission = Mission(
            id="mission-003",
            name="Serialization Test",
            route_id="test-route",
            transports=TransportConfig(initial_x_satellite_id="X-1"),
        )
        json_str = mission.model_dump_json()
        assert json_str is not None

        # Verify it can be deserialized
        data = json.loads(json_str)
        assert data["id"] == "mission-003"
        assert data["name"] == "Serialization Test"

    def test_mission_deserialization(self):
        """Test that mission can be deserialized from JSON."""
        json_data = {
            "id": "mission-004",
            "name": "Deserialization Test",
            "route_id": "test-route",
            "transports": {
                "initial_x_satellite_id": "X-1",
                "initial_ka_satellite_ids": ["T2-1", "T2-2", "T2-3"],
            },
        }
        mission = Mission(**json_data)
        assert mission.id == "mission-004"
        assert mission.name == "Deserialization Test"


class TestTimelineSegment:
    """Tests for TimelineSegment model."""

    def test_create_nominal_segment(self):
        """Test creating a nominal timeline segment."""
        now = datetime.now(timezone.utc)
        segment = TimelineSegment(
            id="seg-001",
            start_time=now,
            end_time=now + timedelta(hours=1),
            status=TimelineStatus.NOMINAL,
        )
        assert segment.id == "seg-001"
        assert segment.status == TimelineStatus.NOMINAL
        assert segment.x_state == TransportState.AVAILABLE
        assert segment.ka_state == TransportState.AVAILABLE
        assert segment.ku_state == TransportState.AVAILABLE

    def test_create_degraded_segment(self):
        """Test creating a degraded timeline segment."""
        now = datetime.now(timezone.utc)
        segment = TimelineSegment(
            id="seg-002",
            start_time=now,
            end_time=now + timedelta(minutes=30),
            status=TimelineStatus.DEGRADED,
            x_state=TransportState.OFFLINE,
            reasons=["x_azimuth_conflict"],
            impacted_transports=[Transport.X],
        )
        assert segment.status == TimelineStatus.DEGRADED
        assert segment.x_state == TransportState.OFFLINE
        assert Transport.X in segment.impacted_transports
        assert "x_azimuth_conflict" in segment.reasons


class TestTimelineAdvisory:
    """Tests for TimelineAdvisory model."""

    def test_create_transition_advisory(self):
        """Test creating a transition advisory."""
        now = datetime.now(timezone.utc)
        advisory = TimelineAdvisory(
            id="adv-001",
            timestamp=now,
            event_type="transition",
            transport=Transport.X,
            severity="warning",
            message="Disable X from 18:25Z to 18:40Z due to transition to X-2",
            metadata={
                "satellite_from": "X-1",
                "satellite_to": "X-2",
                "buffer_minutes": 15,
            },
        )
        assert advisory.id == "adv-001"
        assert advisory.event_type == "transition"
        assert advisory.transport == Transport.X
        assert advisory.severity == "warning"
        assert "satellite_from" in advisory.metadata


class TestMissionTimeline:
    """Tests for MissionTimeline model."""

    def test_create_empty_timeline(self):
        """Test creating an empty timeline."""
        timeline = MissionTimeline(mission_id="mission-001")
        assert timeline.mission_id == "mission-001"
        assert len(timeline.segments) == 0
        assert len(timeline.advisories) == 0
        assert timeline.created_at is not None

    def test_timeline_with_segments(self):
        """Test timeline with segments."""
        now = datetime.now(timezone.utc)
        segment = TimelineSegment(
            id="seg-001",
            start_time=now,
            end_time=now + timedelta(hours=5),
            status=TimelineStatus.NOMINAL,
        )
        timeline = MissionTimeline(
            mission_id="mission-001",
            segments=[segment],
            statistics={
                "total_duration_seconds": 18000,
                "nominal_seconds": 18000,
                "degraded_seconds": 0,
                "critical_seconds": 0,
            },
        )
        assert len(timeline.segments) == 1
        assert timeline.statistics["nominal_seconds"] == 18000


class TestEnums:
    """Tests for enumeration types."""

    def test_transport_enum(self):
        """Test Transport enumeration."""
        assert Transport.X.value == "X"
        assert Transport.KA.value == "Ka"
        assert Transport.KU.value == "Ku"

    def test_transport_state_enum(self):
        """Test TransportState enumeration."""
        assert TransportState.AVAILABLE.value == "available"
        assert TransportState.DEGRADED.value == "degraded"
        assert TransportState.OFFLINE.value == "offline"

    def test_timeline_status_enum(self):
        """Test TimelineStatus enumeration."""
        assert TimelineStatus.NOMINAL.value == "nominal"
        assert TimelineStatus.DEGRADED.value == "degraded"
        assert TimelineStatus.CRITICAL.value == "critical"

    def test_mission_phase_enum(self):
        """Test MissionPhase enumeration."""
        assert MissionPhase.PRE_DEPARTURE.value == "pre_departure"
        assert MissionPhase.IN_FLIGHT.value == "in_flight"
        assert MissionPhase.POST_ARRIVAL.value == "post_arrival"
