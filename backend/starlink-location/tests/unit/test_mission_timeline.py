"""Tests for mission timeline segment assembly."""

from datetime import datetime, timedelta, timezone

from app.mission.models import TimelineStatus, Transport, TransportState
from app.mission.state import TransportInterval
from app.mission.timeline import build_timeline_segments


BASE = datetime(2025, 10, 27, 12, 0, tzinfo=timezone.utc)


def _interval(transport, start_offset, end_offset, state, reasons=None):
    start = BASE + timedelta(minutes=start_offset)
    end = BASE + timedelta(minutes=end_offset) if end_offset is not None else None
    return TransportInterval(
        transport=transport,
        state=state,
        start=start,
        end=end,
        reasons=reasons or [],
    )


def test_nominal_segment_generation():
    """Single nominal interval should produce one nominal segment."""
    intervals = {
        Transport.X: [_interval(Transport.X, 0, 60, TransportState.AVAILABLE)],
        Transport.KA: [_interval(Transport.KA, 0, 60, TransportState.AVAILABLE)],
        Transport.KU: [_interval(Transport.KU, 0, 60, TransportState.AVAILABLE)],
    }

    segments = build_timeline_segments(
        mission_id="mission-1",
        mission_start=BASE,
        mission_end=BASE + timedelta(minutes=60),
        intervals=intervals,
    )

    assert len(segments) == 1
    assert segments[0].status == TimelineStatus.NOMINAL
    assert segments[0].reasons == []
    assert segments[0].impacted_transports == []


def test_degraded_and_critical_segments():
    """Mixed transport states should create degraded and critical segments."""
    intervals = {
        Transport.X: [
            _interval(Transport.X, 0, 20, TransportState.AVAILABLE),
            _interval(
                Transport.X,
                20,
                40,
                TransportState.DEGRADED,
                reasons=["X transition"],
            ),
            _interval(Transport.X, 40, 60, TransportState.AVAILABLE),
        ],
        Transport.KA: [
            _interval(Transport.KA, 0, 30, TransportState.AVAILABLE),
            _interval(
                Transport.KA,
                30,
                60,
                TransportState.OFFLINE,
                reasons=["Ka outage"],
            ),
        ],
        Transport.KU: [
            _interval(Transport.KU, 0, 60, TransportState.AVAILABLE),
        ],
    }

    segments = build_timeline_segments(
        mission_id="mission-1",
        mission_start=BASE,
        mission_end=BASE + timedelta(minutes=60),
        intervals=intervals,
    )

    statuses = [segment.status for segment in segments]
    assert statuses == [
        TimelineStatus.NOMINAL,
        TimelineStatus.DEGRADED,
        TimelineStatus.CRITICAL,
        TimelineStatus.DEGRADED,
    ]

    degraded_segment = segments[1]
    assert Transport.X in degraded_segment.impacted_transports
    assert degraded_segment.reasons == ["X transition"]

    critical_segment = segments[2]
    assert set(critical_segment.impacted_transports) == {Transport.X, Transport.KA}
    assert "Ka outage" in critical_segment.reasons


def test_segment_boundaries_clamped():
    """Segment boundaries should honor mission start/end range."""
    intervals = {
        Transport.X: [
            _interval(
                Transport.X,
                -10,
                10,
                TransportState.DEGRADED,
                reasons=["Pre-start transition"],
            ),
            _interval(Transport.X, 10, 70, TransportState.AVAILABLE),
        ],
    }

    mission_start = BASE
    mission_end = BASE + timedelta(minutes=60)
    segments = build_timeline_segments(
        mission_id="mission-1",
        mission_start=mission_start,
        mission_end=mission_end,
        intervals=intervals,
    )

    assert segments[0].start_time == mission_start
    assert segments[-1].end_time == mission_end
    assert segments[0].status == TimelineStatus.DEGRADED
