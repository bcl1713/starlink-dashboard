"""Tests for mission transport availability state machine."""

from datetime import datetime, timedelta, timezone

from app.mission.models import Transport, TransportState
from app.mission.state import generate_transport_intervals
from app.satellites.rules import EventType, MissionEvent

BASE_TIME = datetime(2025, 10, 27, 12, 0, tzinfo=timezone.utc)


def _make_event(**kwargs):
    defaults = {
        "timestamp": BASE_TIME + timedelta(minutes=10),
        "event_type": EventType.X_TRANSITION_START,
        "transport": Transport.X,
        "affected_transport": Transport.X,
        "reason": "default",
    }
    defaults.update(kwargs)
    return MissionEvent(**defaults)


def test_generate_intervals_no_events():
    """All transports remain available when no events are provided."""
    end_time = BASE_TIME + timedelta(hours=2)
    intervals = generate_transport_intervals([], BASE_TIME, end_time)

    for transport in [Transport.X, Transport.KA, Transport.KU]:
        assert len(intervals[transport]) == 1
        interval = intervals[transport][0]
        assert interval.state == TransportState.AVAILABLE
        assert interval.start == BASE_TIME
        assert interval.end == end_time


def test_x_transition_creates_degraded_interval():
    """X transition events should downgrade the X transport."""
    start = BASE_TIME
    end = start + timedelta(hours=2)
    events = [
        _make_event(
            timestamp=start + timedelta(minutes=30),
            event_type=EventType.X_TRANSITION_START,
            satellite_id="X-2",
            reason="Transition to X-2",
        ),
        _make_event(
            timestamp=start + timedelta(minutes=60),
            event_type=EventType.X_TRANSITION_END,
            satellite_id="X-2",
        ),
    ]

    intervals = generate_transport_intervals(events, start, end)
    x_states = [interval.state for interval in intervals[Transport.X]]

    assert x_states == [
        TransportState.AVAILABLE,
        TransportState.DEGRADED,
        TransportState.AVAILABLE,
    ]

    degraded_interval = intervals[Transport.X][1]
    assert "Transition to X-2" in degraded_interval.reasons[0]


def test_landing_buffer_pushes_x_offline():
    """Landing buffer should eventually transition X to offline."""
    start = BASE_TIME
    end = start + timedelta(hours=3)
    events = [
        _make_event(
            timestamp=start + timedelta(hours=1),
            event_type=EventType.LANDING_BUFFER,
            severity="warning",
            reason="Landing prep",
        ),
        _make_event(
            timestamp=start + timedelta(hours=1, minutes=15),
            event_type=EventType.LANDING_BUFFER,
            severity="critical",
            reason="Landing complete - X disabled",
        ),
    ]

    intervals = generate_transport_intervals(events, start, end)
    x_states = [interval.state for interval in intervals[Transport.X]]

    assert x_states == [
        TransportState.AVAILABLE,
        TransportState.DEGRADED,
        TransportState.OFFLINE,
    ]
    assert intervals[Transport.X][-1].reasons[0].startswith("Landing complete")


def test_ka_coverage_and_outage_precedence():
    """Ka coverage gaps degrade, outages force offline state."""
    start = BASE_TIME
    end = start + timedelta(hours=2)

    events = [
        _make_event(
            transport=Transport.KA,
            affected_transport=Transport.KA,
            timestamp=start + timedelta(minutes=10),
            event_type=EventType.KA_COVERAGE_EXIT,
            satellite_id="POR",
            reason="Coverage exit",
        ),
        _make_event(
            transport=Transport.KA,
            affected_transport=Transport.KA,
            timestamp=start + timedelta(minutes=30),
            event_type=EventType.KA_OUTAGE_START,
            reason="Maintenance",
        ),
        _make_event(
            transport=Transport.KA,
            affected_transport=Transport.KA,
            timestamp=start + timedelta(minutes=50),
            event_type=EventType.KA_OUTAGE_END,
            reason="Maintenance complete",
        ),
        _make_event(
            transport=Transport.KA,
            affected_transport=Transport.KA,
            timestamp=start + timedelta(minutes=70),
            event_type=EventType.KA_COVERAGE_ENTRY,
            satellite_id="POR",
            reason="Coverage restored",
        ),
    ]

    intervals = generate_transport_intervals(events, start, end)
    ka_states = [interval.state for interval in intervals[Transport.KA]]

    assert ka_states == [
        TransportState.AVAILABLE,
        TransportState.DEGRADED,
        TransportState.OFFLINE,
        TransportState.DEGRADED,
        TransportState.AVAILABLE,
    ]

    offline_interval = intervals[Transport.KA][2]
    assert "Maintenance" in offline_interval.reasons[0]


def test_events_before_mission_start_apply_at_start():
    """Events occurring before mission start should affect initial interval."""
    start = BASE_TIME
    end = start + timedelta(hours=1)
    events = [
        _make_event(
            timestamp=start - timedelta(minutes=5),
            event_type=EventType.X_TRANSITION_START,
            satellite_id="X-3",
            reason="Pre-departure transition",
        ),
    ]

    intervals = generate_transport_intervals(events, start, end)
    x_states = [interval.state for interval in intervals[Transport.X]]

    # Only a degraded interval should remain because no end event was provided.
    assert x_states == [TransportState.DEGRADED]
    assert intervals[Transport.X][0].start == start
    assert intervals[Transport.X][0].end == end


def test_aar_window_does_not_degrade_transport():
    """AAR window markers should not degrade X-Band on their own."""
    start = BASE_TIME
    end = start + timedelta(hours=2)
    events = [
        _make_event(
            timestamp=start + timedelta(minutes=20),
            event_type=EventType.AAR_WINDOW,
            severity="warning",
            reason="AAR Start",
        ),
        _make_event(
            timestamp=start + timedelta(minutes=60),
            event_type=EventType.AAR_WINDOW,
            severity="info",
            reason="AAR End",
        ),
    ]

    intervals = generate_transport_intervals(events, start, end)
    x_states = [interval.state for interval in intervals[Transport.X]]

    assert x_states == [TransportState.AVAILABLE]
