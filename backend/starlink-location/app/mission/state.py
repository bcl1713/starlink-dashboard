"""Transport availability state machine for mission planning.

Transforms `MissionEvent` sequences emitted by the rule engine into contiguous
transport availability intervals (available, degraded, offline). These
intervals feed the timeline engine to build customer-facing segments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Sequence

from app.mission.models import Transport, TransportState
from app.satellites.rules import EventType, MissionEvent


@dataclass
class TransportInterval:
    """Represents a contiguous availability span for a single transport."""

    transport: Transport
    state: TransportState
    start: datetime
    end: Optional[datetime] = None
    reasons: List[str] = field(default_factory=list)


def generate_transport_intervals(
    events: Sequence[MissionEvent],
    mission_start: datetime,
    mission_end: datetime,
    transports: Optional[Sequence[Transport]] = None,
) -> Dict[Transport, List[TransportInterval]]:
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

    active_conditions: Dict[Transport, Dict[str, Dict[str, str]]] = {
        transport: {"degraded": {}, "offline": {}, "safety": {}}
        for transport in transports
    }

    intervals: Dict[Transport, List[TransportInterval]] = {}
    current_state: Dict[Transport, TransportState] = {}
    current_reasons: Dict[Transport, List[str]] = {}

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
    intervals: List[TransportInterval], transition_time: datetime
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


def _derive_state(
    condition_state: Dict[str, Dict[str, str]]
) -> tuple[TransportState, List[str]]:
    """Return (state, reasons) based on active degraded/offline conditions."""
    offline_reasons = [
        condition_state["offline"][key]
        for key in sorted(condition_state["offline"].keys())
    ]
    degraded_reasons = [
        condition_state["degraded"][key]
        for key in sorted(condition_state["degraded"].keys())
    ]
    safety_reasons = [
        condition_state["safety"][key]
        for key in sorted(condition_state["safety"].keys())
    ]

    if offline_reasons:
        return (
            TransportState.OFFLINE,
            offline_reasons + degraded_reasons + safety_reasons,
        )
    if degraded_reasons:
        return TransportState.DEGRADED, degraded_reasons + safety_reasons
    return TransportState.AVAILABLE, safety_reasons


def _apply_event(
    active_conditions: Dict[Transport, Dict[str, Dict[str, str]]],
    event: MissionEvent,
) -> bool:
    """Apply a MissionEvent to the active condition set."""
    transport = event.affected_transport or event.transport
    if transport not in active_conditions:
        return False

    def activate(bucket: str, key: str, reason: str) -> bool:
        existing = active_conditions[transport][bucket].get(key)
        if existing == reason:
            return False
        active_conditions[transport][bucket][key] = reason
        return True

    def deactivate(bucket: str, key: str) -> bool:
        return active_conditions[transport][bucket].pop(key, None) is not None

    reason = event.reason or ""
    sat_suffix = event.satellite_id or ""

    if event.event_type == EventType.X_TRANSITION_START:
        key = f"x_transition:{sat_suffix or 'unknown'}"
        return activate("degraded", key, reason or f"X transition {sat_suffix}".strip())

    if event.event_type == EventType.X_TRANSITION_END:
        key = f"x_transition:{sat_suffix or 'unknown'}"
        return deactivate("degraded", key)

    if event.event_type == EventType.TAKEOFF_BUFFER:
        key = "takeoff_buffer"
        if event.severity == "safety":
            return activate("safety", key, reason or "Takeoff buffer")
        if event.severity in ("warning", "critical"):
            return activate("degraded", key, reason or "Takeoff buffer")
        d1 = deactivate("degraded", key)
        d2 = deactivate("safety", key)
        return d1 or d2

    if event.event_type == EventType.LANDING_BUFFER:
        prep_key = "landing_buffer"
        if event.severity == "safety":
            return activate("safety", prep_key, reason or "Landing buffer")
        if event.severity == "warning":
            return activate("degraded", prep_key, reason or "Landing buffer")

        d1 = deactivate("degraded", prep_key)
        d2 = deactivate("safety", prep_key)
        changed = d1 or d2

        offline_key = "landing_complete"
        offline_reason = reason or "Landing complete - X offline"
        return activate("offline", offline_key, offline_reason) or changed

    if event.event_type == EventType.AAR_WINDOW:
        return False

    if event.event_type == EventType.X_AZIMUTH_VIOLATION:
        key = "x_azimuth"
        if event.severity in ("warning", "critical"):
            return activate("degraded", key, reason or "X azimuth conflict")
        return deactivate("degraded", key)

    if event.event_type == EventType.KA_COVERAGE_EXIT:
        key = "ka_no_coverage"
        return activate("degraded", key, reason or "Ka coverage gap")

    if event.event_type == EventType.KA_COVERAGE_ENTRY:
        key = "ka_no_coverage"
        return deactivate("degraded", key)

    if event.event_type == EventType.KA_TRANSITION:
        transition_id = event.metadata.get("transition_id") if event.metadata else None
        key = f"ka_transition:{transition_id or event.satellite_id or 'swap'}"
        if event.severity in ("warning", "critical"):
            return activate("degraded", key, reason or "Ka transition")
        return deactivate("degraded", key)

    if event.event_type == EventType.KA_OUTAGE_START:
        key = f"ka_outage:{event.metadata.get('id', 'default')}"
        outage_reason = reason or "Ka outage"
        return activate("offline", key, outage_reason)

    if event.event_type == EventType.KA_OUTAGE_END:
        key = f"ka_outage:{event.metadata.get('id', 'default')}"
        return deactivate("offline", key)

    if event.event_type == EventType.KU_OUTAGE_START:
        key = f"ku_outage:{event.metadata.get('id', 'default')}"
        outage_reason = reason or "Ku outage"
        return activate("offline", key, outage_reason)

    if event.event_type == EventType.KU_OUTAGE_END:
        key = f"ku_outage:{event.metadata.get('id', 'default')}"
        return deactivate("offline", key)

    return False
