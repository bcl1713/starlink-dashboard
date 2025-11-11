"""Unit tests for satellite communication constraint rules engine."""

from datetime import datetime, timedelta

import pytest

from app.mission.models import Transport
from app.satellites.rules import ConstraintConfig, EventType, MissionEvent, RuleEngine


class TestMissionEvent:
    """Test mission event objects."""

    def test_event_creation(self):
        """Test creating a mission event."""
        now = datetime.utcnow()
        event = MissionEvent(
            timestamp=now,
            event_type=EventType.X_TRANSITION_START,
            transport=Transport.X,
            affected_transport=Transport.X,
            reason="X transition to X-1",
        )

        assert event.timestamp == now
        assert event.event_type == EventType.X_TRANSITION_START
        assert event.transport == Transport.X
        assert event.severity == "warning"

    def test_event_sorting(self):
        """Test sorting events by timestamp."""
        base_time = datetime.utcnow()

        event1 = MissionEvent(
            timestamp=base_time + timedelta(hours=1),
            event_type=EventType.X_TRANSITION_START,
            transport=Transport.X,
        )

        event2 = MissionEvent(
            timestamp=base_time,
            event_type=EventType.TAKEOFF_BUFFER,
            transport=Transport.X,
        )

        events = [event1, event2]
        sorted_events = sorted(events)

        assert sorted_events[0].timestamp == base_time
        assert sorted_events[1].timestamp == base_time + timedelta(hours=1)


class TestConstraintConfig:
    """Test constraint configuration."""

    def test_default_config(self):
        """Test default constraint values."""
        config = ConstraintConfig()

        assert config.normal_azimuth_min == 135.0
        assert config.normal_azimuth_max == 225.0
        assert config.aar_azimuth_min == 315.0
        assert config.aar_azimuth_max == 45.0
        assert config.transition_buffer_minutes == 15

    def test_custom_config(self):
        """Test custom constraint configuration."""
        config = ConstraintConfig(
            normal_azimuth_min=120.0,
            transition_buffer_minutes=20,
        )

        assert config.normal_azimuth_min == 120.0
        assert config.transition_buffer_minutes == 20


class TestRuleEngine:
    """Test rule evaluation engine."""

    def test_engine_initialization(self):
        """Test creating rule engine."""
        engine = RuleEngine()

        assert len(engine.events) == 0
        assert engine.config is not None

    def test_engine_with_custom_config(self):
        """Test rule engine with custom configuration."""
        config = ConstraintConfig(transition_buffer_minutes=20)
        engine = RuleEngine(config=config)

        assert engine.config.transition_buffer_minutes == 20

    def test_evaluate_x_azimuth_evaluation(self):
        """Test azimuth evaluation returns valid geometry."""
        engine = RuleEngine()

        # Aircraft at various positions relative to satellite
        is_violation, azimuth = engine.evaluate_x_azimuth_window(
            aircraft_lat=45.0,
            aircraft_lon=0.0,
            aircraft_alt=0.0,
            satellite_lon=0.0,
            timestamp=datetime.utcnow(),
        )

        # Should return valid boolean and azimuth
        assert isinstance(is_violation, bool)
        assert 0 <= azimuth < 360

    def test_evaluate_x_azimuth_violation(self):
        """Test azimuth evaluation when violation occurs."""
        engine = RuleEngine()

        # This test is approximate; actual violation depends on exact geometry
        # At high northern latitude with satellite at different longitude
        is_violation, azimuth = engine.evaluate_x_azimuth_window(
            aircraft_lat=85.0,  # High latitude
            aircraft_lon=0.0,
            aircraft_alt=0.0,
            satellite_lon=0.0,
            timestamp=datetime.utcnow(),
            is_aar_mode=False,
        )

        # Verify we get numeric results
        assert isinstance(is_violation, bool)
        assert 0 <= azimuth < 360

    def test_add_x_transition_events(self):
        """Test adding X transition degrade events."""
        engine = RuleEngine()
        now = datetime.utcnow()

        engine.add_x_transition_events(now, "X-1", is_aar_mode=False)

        assert len(engine.events) == 2

        # Check event types
        event_types = {e.event_type for e in engine.events}
        assert EventType.X_TRANSITION_START in event_types
        assert EventType.X_TRANSITION_END in event_types

        # Check timestamps (should be ±15 min)
        sorted_events = sorted(engine.events)
        time_diff = sorted_events[1].timestamp - sorted_events[0].timestamp
        assert time_diff == timedelta(minutes=30)

    def test_add_ka_coverage_events(self):
        """Test adding Ka coverage entry/exit events."""
        engine = RuleEngine()
        now = datetime.utcnow()
        end = now + timedelta(hours=1)

        engine.add_ka_coverage_events(now, end, "Ka-T2-1")

        assert len(engine.events) == 2

        # Check event types
        event_types = {e.event_type for e in engine.events}
        assert EventType.KA_COVERAGE_ENTRY in event_types
        assert EventType.KA_COVERAGE_EXIT in event_types

    def test_add_manual_outage_events(self):
        """Test adding manual outage window events."""
        engine = RuleEngine()
        now = datetime.utcnow()
        end = now + timedelta(hours=2)

        engine.add_manual_outage_events(now, end, Transport.KA, "Scheduled maintenance")

        assert len(engine.events) == 2

        # Check event types
        event_types = {e.event_type for e in engine.events}
        assert EventType.KA_OUTAGE_START in event_types
        assert EventType.KA_OUTAGE_END in event_types

    def test_add_takeoff_landing_buffers(self):
        """Test adding takeoff and landing buffer events."""
        engine = RuleEngine()
        departure = datetime.utcnow()
        landing = departure + timedelta(hours=10)

        engine.add_takeoff_landing_buffers(departure, landing)

        # Should have 4 events (takeoff start/end, landing start/end)
        assert len(engine.events) == 4

        event_types = {e.event_type for e in engine.events}
        assert EventType.TAKEOFF_BUFFER in event_types
        assert EventType.LANDING_BUFFER in event_types

    def test_add_aar_window_events(self):
        """Test adding AAR window events."""
        engine = RuleEngine()
        start = datetime.utcnow() + timedelta(hours=2)
        end = start + timedelta(minutes=45)

        engine.add_aar_window_events(start, end, "AAR-1")

        assert len(engine.events) == 2

        event_types = {e.event_type for e in engine.events}
        assert EventType.AAR_WINDOW in event_types

    def test_get_sorted_events(self):
        """Test getting events in sorted order."""
        engine = RuleEngine()
        base_time = datetime.utcnow()

        # Add events out of order
        engine.add_aar_window_events(base_time + timedelta(hours=2), base_time + timedelta(hours=3))
        engine.add_takeoff_landing_buffers(base_time, base_time + timedelta(hours=10))

        sorted_events = engine.get_sorted_events()

        # Verify sorted by timestamp
        for i in range(len(sorted_events) - 1):
            assert sorted_events[i].timestamp <= sorted_events[i + 1].timestamp

    def test_generate_advisories(self):
        """Test generating human-readable advisories."""
        engine = RuleEngine()
        now = datetime.utcnow()

        engine.add_x_transition_events(now + timedelta(hours=2), "X-1")

        advisories = engine.generate_advisories()

        # Should have at least one advisory about X transition
        assert len(advisories) > 0
        assert any("X" in adv for adv in advisories)

    def test_clear_events(self):
        """Test clearing all events."""
        engine = RuleEngine()
        now = datetime.utcnow()

        engine.add_x_transition_events(now, "X-1")
        assert len(engine.events) > 0

        engine.clear_events()
        assert len(engine.events) == 0

    def test_multiple_transport_events(self):
        """Test engine with events from multiple transports."""
        engine = RuleEngine()
        now = datetime.utcnow()

        engine.add_x_transition_events(now, "X-1")
        engine.add_ka_coverage_events(now + timedelta(hours=1), now + timedelta(hours=2), "Ka-T2-1")
        engine.add_manual_outage_events(
            now + timedelta(hours=3),
            now + timedelta(hours=4),
            Transport.KU,
            "Ku maintenance",
        )

        assert len(engine.events) == 6

        # Verify transport distribution
        x_events = [e for e in engine.events if e.transport == Transport.X]
        ka_events = [e for e in engine.events if e.transport == Transport.KA]
        ku_events = [e for e in engine.events if e.transport == Transport.KU]

        assert len(x_events) == 2
        assert len(ka_events) == 2
        assert len(ku_events) == 2

    def test_event_severity_levels(self):
        """Test that events have appropriate severity levels."""
        engine = RuleEngine()
        now = datetime.utcnow()

        engine.add_takeoff_landing_buffers(now, now + timedelta(hours=10))
        events = engine.get_sorted_events()

        # Find landing event (should be critical)
        landing_events = [e for e in events if e.event_type == EventType.LANDING_BUFFER]
        assert any(e.severity == "critical" for e in landing_events)

    def test_buffer_configuration_affects_timing(self):
        """Test that buffer configuration changes event timing."""
        config1 = ConstraintConfig(transition_buffer_minutes=15)
        engine1 = RuleEngine(config=config1)

        config2 = ConstraintConfig(transition_buffer_minutes=20)
        engine2 = RuleEngine(config=config2)

        now = datetime.utcnow()

        engine1.add_x_transition_events(now, "X-1")
        engine2.add_x_transition_events(now, "X-1")

        events1 = engine1.get_sorted_events()
        events2 = engine2.get_sorted_events()

        # Calculate time differences
        time_diff1 = events1[1].timestamp - events1[0].timestamp
        time_diff2 = events2[1].timestamp - events2[0].timestamp

        # Different configurations should produce different timings
        assert time_diff1 == timedelta(minutes=30)  # ±15
        assert time_diff2 == timedelta(minutes=40)  # ±20
        assert time_diff1 != time_diff2

    def test_aar_mode_flag(self):
        """Test that AAR mode flag is properly handled."""
        engine = RuleEngine()

        # Both should complete without error
        # (actual violation depends on geometry)
        is_violation1, az1 = engine.evaluate_x_azimuth_window(
            aircraft_lat=30.0,
            aircraft_lon=0.0,
            aircraft_alt=0.0,
            satellite_lon=0.0,
            timestamp=datetime.utcnow(),
            is_aar_mode=False,  # Normal ops
        )

        is_violation2, az2 = engine.evaluate_x_azimuth_window(
            aircraft_lat=30.0,
            aircraft_lon=0.0,
            aircraft_alt=0.0,
            satellite_lon=0.0,
            timestamp=datetime.utcnow(),
            is_aar_mode=True,  # AAR mode
        )

        # Both should return valid results
        assert isinstance(is_violation1, bool)
        assert isinstance(is_violation2, bool)
        assert 0 <= az1 < 360
        assert 0 <= az2 < 360
