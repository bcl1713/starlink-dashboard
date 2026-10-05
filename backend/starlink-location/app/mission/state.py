"""Transport availability state machine for mission planning.

Transforms `MissionEvent` sequences emitted by the rule engine into contiguous
transport availability intervals (available, degraded, offline). These
intervals feed the timeline engine to build customer-facing segments.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from app.mission.models import Transport, TransportState
from app.mission.replay_state import (
    apply_event_conditions as _apply_event,
)
from app.mission.replay_state import (
    derive_state as _derive_state,
)
from app.satellites.rules import MissionEvent


@dataclass
class TransportInterval:
    """Represents a contiguous availability span for a single transport."""

    transport: Transport
    state: TransportState
    start: datetime
    end: datetime | None = None
    reasons: list[str] = field(default_factory=list)


def generate_transport_intervals(
    events: Sequence[MissionEvent],
    mission_start: datetime,
    mission_end: datetime,
    transports: Sequence[Transport] | None = None,
) -> dict[Transport, list[TransportInterval]]:
    """Generate contiguous availability intervals for each transport.

    Args:
        events: Sequence of `MissionEvent` objects (sorted or unsorted).
        mission_start: Start timestamp for the mission timeline.
        mission_end: End timestamp for the mission timeline.
        transports: Optional explicit list of transports to evaluate.

    Returns:
        Dict mapping Transport -> list of `TransportInterval` objects spanning
        the entire mission timeline.

    Raises:
        ValueError: If mission_end is not after mission_start.
    """

    if mission_end <= mission_start:
        raise ValueError("mission_end must be after mission_start")

    transports = list(transports or [Transport.X, Transport.KA, Transport.KU])

    active_conditions: dict[Transport, dict[str, dict[str, str]]] = {
        transport: {"degraded": {}, "offline": {}, "safety": {}}
        for transport in transports
    }

    intervals: dict[Transport, list[TransportInterval]] = {}
    current_state: dict[Transport, TransportState] = {}
    current_reasons: dict[Transport, list[str]] = {}

    for transport in transports:
        intervals[transport] = [
            TransportInterval(
                transport=transport,
                state=TransportState.AVAILABLE,
                start=mission_start,
                reasons=[],
            )
        ]
        current_state[transport] = TransportState.AVAILABLE
        current_reasons[transport] = []

    sorted_events = sorted(events)

    for event in sorted_events:
        transport = event.affected_transport or event.transport
        if transport not in active_conditions:
            continue

        effective_time = _clamp_timestamp(event.timestamp, mission_start, mission_end)
        if effective_time >= mission_end:
            break

        changed = _apply_event(active_conditions, event)
        if not changed:
            continue

        new_state, reasons = _derive_state(active_conditions[transport])
        if (
            new_state == current_state[transport]
            and reasons == current_reasons[transport]
        ):
            # State and rationale unchanged even though event fired.
            continue

        _close_interval(intervals[transport], effective_time)
        intervals[transport].append(
            TransportInterval(
                transport=transport,
                state=new_state,
                start=effective_time,
                reasons=reasons,
            )
        )

        current_state[transport] = new_state
        current_reasons[transport] = reasons

    for transport in transports:
        if intervals[transport]:
            intervals[transport][-1].end = mission_end

    return intervals


def _clamp_timestamp(ts: datetime, start: datetime, end: datetime) -> datetime:
    if ts <= start:
        return start
    if ts >= end:
        return end
    return ts


def _close_interval(
    intervals: list[TransportInterval], transition_time: datetime
) -> None:
    """Close the current interval at the provided timestamp."""
    if not intervals:
        return
    current = intervals[-1]
    if current.start == transition_time:
        # Replace zero-length interval entirely.
        intervals.pop()
    else:
        current.end = transition_time
