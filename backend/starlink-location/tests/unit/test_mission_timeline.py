"""Tests for mission timeline segment assembly."""

from datetime import datetime, timedelta, timezone

from app.mission.models import (
    MissionLegTimeline,
    TimelineSegment,
    TimelineStatus,
    Transport,
    TransportState,
)
from app.mission.state import TransportInterval
from app.mission.timeline import build_timeline_segments
from app.mission.timeline_service import _annotate_aar_markers
from app.satellites.rules import EventType, MissionEvent


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


def test_annotate_aar_markers_appends_reasons():
    """AAR start/end markers should show up in timeline segment reasons."""
    segments = [
        TimelineSegment(
            id="seg-1",
            start_time=BASE,
            end_time=BASE + timedelta(minutes=30),
            status=TimelineStatus.NOMINAL,
            x_state=TransportState.AVAILABLE,
            ka_state=TransportState.AVAILABLE,
            ku_state=TransportState.AVAILABLE,
            reasons=[],
            impacted_transports=[],
            metadata={},
        ),
        TimelineSegment(
            id="seg-2",
            start_time=BASE + timedelta(minutes=30),
            end_time=BASE + timedelta(minutes=60),
            status=TimelineStatus.NOMINAL,
            x_state=TransportState.AVAILABLE,
            ka_state=TransportState.AVAILABLE,
            ku_state=TransportState.AVAILABLE,
            reasons=[],
            impacted_transports=[],
            metadata={},
        ),
    ]
    timeline = MissionTimeline(
        mission_id="mission-1",
        segments=segments,
        advisories=[],
        statistics={},
    )
    events = [
        MissionEvent(
            timestamp=BASE + timedelta(minutes=10),
            event_type=EventType.AAR_WINDOW,
            transport=Transport.X,
            affected_transport=Transport.X,
            severity="warning",
            reason="AAR Start",
        ),
        MissionEvent(
            timestamp=BASE + timedelta(minutes=45),
            event_type=EventType.AAR_WINDOW,
            transport=Transport.X,
            affected_transport=Transport.X,
            severity="info",
            reason="AAR End",
        ),
    ]

    _annotate_aar_markers(timeline, events)

    blocks = timeline.statistics.get("_aar_blocks")
    assert blocks is not None
    assert len(blocks) == 1
    block = blocks[0]
    expected_start = (BASE + timedelta(minutes=10)).isoformat()
    expected_end = (BASE + timedelta(minutes=45)).isoformat()
    assert block["start"] == expected_start
    assert block["end"] == expected_end
