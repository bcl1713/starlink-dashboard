"""Timeline statistics and summary generation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from app.mission.models import (
    MissionLegTimeline,
    TimelineStatus,
    Transport,
    TransportState,
)
from app.satellites.rules import EventType, MissionEvent
from app.mission.timeline_builder.utils import ensure_datetime

logger = logging.getLogger(__name__)


@dataclass
class TimelineSummary:
    """Lightweight summary derived from the computed timeline."""

    mission_start: datetime
    mission_end: datetime
    degraded_seconds: float
    critical_seconds: float
    next_conflict_seconds: float
    transport_states: dict[Transport, TransportState]
    sample_count: int
    sample_interval_seconds: int
    generation_runtime_ms: float


def annotate_aar_markers(
    timeline: MissionLegTimeline,
    events: Sequence[MissionEvent],
) -> None:
    """Persist AAR window intervals for export consumers."""
    if not timeline.segments:
        return
    blocks: list[dict[str, str]] = []
    pending_start: datetime | None = None
    for event in events:
        if event.event_type != EventType.AAR_WINDOW:
            continue
        ts = ensure_datetime(event.timestamp)
        if event.severity in ("warning", "critical", "safety"):
            pending_start = ts
        elif pending_start:
            blocks.append(
                {
                    "start": pending_start.isoformat(),
                    "end": ts.isoformat(),
                }
            )
            pending_start = None
    if pending_start:
        blocks.append(
            {
                "start": pending_start.isoformat(),
                "end": ensure_datetime(
                    timeline.segments[-1].end_time or pending_start
                ).isoformat(),
            }
        )
    if blocks:
        stats = dict(timeline.statistics or {})
        stats["_aar_blocks"] = blocks
        timeline.statistics = stats


def attach_statistics(
    timeline: MissionLegTimeline, mission_start: datetime, mission_end: datetime
) -> None:
    """Compute and attach statistics to the timeline."""
    total_seconds = max((mission_end - mission_start).total_seconds(), 1.0)
    degraded_seconds = 0.0
    critical_seconds = 0.0
    for segment in timeline.segments:
        duration = (segment.end_time - segment.start_time).total_seconds()
        if duration <= 0:
            continue
        if segment.status == TimelineStatus.DEGRADED:
            degraded_seconds += duration
        elif segment.status == TimelineStatus.CRITICAL:
            critical_seconds += duration

    existing = timeline.statistics or {}
    preserved = {key: value for key, value in existing.items() if key.startswith("_")}
    timeline.statistics = {
        "total_duration_seconds": total_seconds,
        "degraded_seconds": degraded_seconds,
        "critical_seconds": critical_seconds,
        "nominal_seconds": total_seconds - degraded_seconds - critical_seconds,
    }
    timeline.statistics.update(preserved)


def summarize_timeline(
    timeline: MissionLegTimeline,
    mission_start: datetime,
    mission_end: datetime,
    sample_count: int,
    sample_interval_seconds: int,
    generation_runtime_ms: float,
) -> TimelineSummary:
    """Generate a lightweight summary from the timeline."""
    severity_order = {
        TransportState.AVAILABLE: 0,
        TransportState.DEGRADED: 1,
        TransportState.OFFLINE: 2,
    }
    transport_states: dict[Transport, TransportState] = {
        Transport.X: TransportState.AVAILABLE,
        Transport.KA: TransportState.AVAILABLE,
        Transport.KU: TransportState.AVAILABLE,
    }

    degraded_seconds = 0.0
    critical_seconds = 0.0
    conflict_start: datetime | None = None

    for segment in timeline.segments:
        duration = (segment.end_time - segment.start_time).total_seconds()
        if duration <= 0:
            continue

        if segment.status == TimelineStatus.DEGRADED:
            degraded_seconds += duration
        elif segment.status == TimelineStatus.CRITICAL:
            critical_seconds += duration

        if segment.status != TimelineStatus.NOMINAL and conflict_start is None:
            conflict_start = segment.start_time

        for transport, state in (
            (Transport.X, segment.x_state),
            (Transport.KA, segment.ka_state),
            (Transport.KU, segment.ku_state),
        ):
            if severity_order[state] > severity_order[transport_states[transport]]:
                transport_states[transport] = state

    next_conflict_seconds = (
        (conflict_start - mission_start).total_seconds() if conflict_start else -1.0
    )

    return TimelineSummary(
        mission_start=mission_start,
        mission_end=mission_end,
        degraded_seconds=degraded_seconds,
        critical_seconds=critical_seconds,
        next_conflict_seconds=next_conflict_seconds,
        transport_states=transport_states,
        sample_count=sample_count,
        sample_interval_seconds=sample_interval_seconds,
        generation_runtime_ms=generation_runtime_ms,
    )
