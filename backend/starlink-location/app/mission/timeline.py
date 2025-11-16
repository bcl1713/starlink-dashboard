"""Mission timeline generation utilities.

Converts per-transport availability intervals into mission timeline segments
that summarize nominal/degraded/critical states with reasons for dashboards
and exports.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Sequence

from app.mission.models import MissionTimeline, TimelineSegment, TimelineStatus, Transport, TransportState
from app.mission.state import TransportInterval


def build_timeline_segments(
    mission_id: str,
    mission_start: datetime,
    mission_end: datetime,
    intervals: Dict[Transport, Sequence[TransportInterval]],
) -> List[TimelineSegment]:
    """Merge per-transport intervals into mission timeline segments.

    Args:
        mission_id: Mission identifier for segment IDs.
        mission_start: Start timestamp for mission timeline.
        mission_end: End timestamp for mission timeline.
        intervals: Mapping of transport -> sequence of TransportInterval objects.

    Returns:
        Ordered list of TimelineSegment objects covering [mission_start, mission_end].

    Raises:
        ValueError: If boundaries or intervals are invalid.
    """

    if mission_end <= mission_start:
        raise ValueError("mission_end must be after mission_start")

    boundaries = _collect_boundaries(
        mission_start,
        mission_end,
        intervals,
    )
    segments: List[TimelineSegment] = []

    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = boundaries[i + 1]
        if start >= end:
            continue

        x_interval = _interval_at(Transport.X, intervals, start)
        ka_interval = _interval_at(Transport.KA, intervals, start)
        ku_interval = _interval_at(Transport.KU, intervals, start)

        x_state = x_interval.state if x_interval else TransportState.AVAILABLE
        ka_state = ka_interval.state if ka_interval else TransportState.AVAILABLE
        ku_state = ku_interval.state if ku_interval else TransportState.AVAILABLE

        impacted = [
            transport
            for transport, state in (
                (Transport.X, x_state),
                (Transport.KA, ka_state),
                (Transport.KU, ku_state),
            )
            if state != TransportState.AVAILABLE
        ]

        status = _derive_status(x_state, ka_state, ku_state)

        reasons = _collect_reasons([x_interval, ka_interval, ku_interval])

        metadata = {
            "segment_index": len(segments),
            "impacted_count": len(impacted),
        }

        segment = TimelineSegment(
            id=f"{mission_id}-segment-{len(segments) + 1:03d}",
            start_time=start,
            end_time=end,
            status=status,
            x_state=x_state,
            ka_state=ka_state,
            ku_state=ku_state,
            reasons=reasons,
            impacted_transports=impacted,
            metadata=metadata,
        )
        segments.append(segment)

    return segments


def assemble_mission_timeline(
    mission_id: str,
    mission_start: datetime,
    mission_end: datetime,
    intervals: Dict[Transport, Sequence[TransportInterval]],
) -> MissionTimeline:
    """Create MissionTimeline model from interval data."""
    segments = build_timeline_segments(
        mission_id=mission_id,
        mission_start=mission_start,
        mission_end=mission_end,
        intervals=intervals,
    )

    return MissionTimeline(
        mission_id=mission_id,
        segments=segments,
        advisories=[],
    )


def _collect_boundaries(
    mission_start: datetime,
    mission_end: datetime,
    intervals: Dict[Transport, Sequence[TransportInterval]],
) -> List[datetime]:
    boundaries = {mission_start, mission_end}

    for transport_intervals in intervals.values():
        for interval in transport_intervals:
            boundaries.add(interval.start)
            if interval.end:
                boundaries.add(interval.end)

    ordered = sorted(boundaries)
    return [ts for ts in ordered if mission_start <= ts <= mission_end]


def _interval_at(
    transport: Transport,
    intervals: Dict[Transport, Sequence[TransportInterval]],
    timestamp: datetime,
) -> TransportInterval | None:
    transport_intervals = intervals.get(transport) or []
    for interval in transport_intervals:
        interval_end = interval.end
        if interval_end is None:
            interval_end = datetime.max

        if interval.start <= timestamp < interval_end:
            return interval

    return transport_intervals[-1] if transport_intervals else None


def _derive_status(
    x_state: TransportState,
    ka_state: TransportState,
    ku_state: TransportState,
) -> TimelineStatus:
    impacted = sum(
        1 for state in (x_state, ka_state, ku_state) if state != TransportState.AVAILABLE
    )
    if impacted == 0:
        return TimelineStatus.NOMINAL
    if impacted == 1:
        return TimelineStatus.DEGRADED
    return TimelineStatus.CRITICAL


def _collect_reasons(intervals: Sequence[TransportInterval | None]) -> List[str]:
    reasons: List[str] = []
    seen = set()
    for interval in intervals:
        if not interval:
            continue
        for reason in interval.reasons:
            if reason and reason not in seen:
                seen.add(reason)
                reasons.append(reason)
    return reasons
