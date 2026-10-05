"""Shared incremental transport reducer for plans and replay frames."""

import copy
from dataclasses import dataclass, field

from app.mission.models import Transport, TransportState
from app.satellites.rules import EventType, MissionEvent


@dataclass(frozen=True)
class TransportReplayState:
    conditions: dict[Transport, dict[str, dict[str, str]]] = field(
        default_factory=lambda: {
            transport: {"degraded": {}, "offline": {}, "safety": {}}
            for transport in Transport
        }
    )

    def states(self) -> dict[Transport, TransportState]:
        return {
            transport: derive_state(conditions)[0]
            for transport, conditions in self.conditions.items()
        }


def apply_transport_event(
    state: TransportReplayState, event: MissionEvent
) -> TransportReplayState:
    conditions = copy.deepcopy(state.conditions)
    apply_event_conditions(conditions, event)
    return TransportReplayState(conditions)


def derive_state(
    condition_state: dict[str, dict[str, str]],
) -> tuple[TransportState, list[str]]:
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


def apply_event_conditions(
    active_conditions: dict[Transport, dict[str, dict[str, str]]],
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

    if event.event_type in (
        EventType.MANUAL_AAR_TRACK_START,
        EventType.MANUAL_AAR_TRACK_END,
    ):
        track_id = (
            event.metadata.get("track_id", "unknown") if event.metadata else "unknown"
        )
        key = f"manual_aar_track:{track_id}"
        if event.event_type == EventType.MANUAL_AAR_TRACK_START:
            return activate("degraded", key, reason or "Manual AR Track")
        return deactivate("degraded", key)

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
