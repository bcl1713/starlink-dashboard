"""Transport state display and serialization utilities.

Pure functions for handling transport display names, state visualization,
and conflict detection without manager dependencies.
"""

from __future__ import annotations

from typing import Iterable

from app.mission.models import (
    TimelineSegment,
    Transport,
    TransportState,
)

# Display names for transport bands
TRANSPORT_DISPLAY = {
    Transport.X: "X-Band",
    Transport.KA: "CommKa",
    Transport.KU: "StarShield",
}

# List of transport column names in standard order
STATE_COLUMNS = [
    TRANSPORT_DISPLAY[Transport.X],
    TRANSPORT_DISPLAY[Transport.KA],
    TRANSPORT_DISPLAY[Transport.KU],
]

# Status colors for route visualization and legends
# Using standard traffic light colors for clear status indication
STATUS_COLORS = {
    "nominal": "#2ecc71",  # Green
    "degraded": "#f1c40f",  # Yellow/Orange
    "critical": "#e74c3c",  # Red
    "unknown": "#95a5a6",  # Gray (fallback)
}


def serialize_transport_list(transports: Iterable[Transport]) -> str:
    """Convert a list of transports to a comma-separated display string.

    Args:
        transports: Iterable of Transport enum values

    Returns:
        Comma-separated transport display names
    """
    labels: list[str] = []
    for transport in transports:
        if isinstance(transport, Transport):
            labels.append(TRANSPORT_DISPLAY.get(transport, transport.value))
        else:
            labels.append(str(transport))
    return ", ".join(labels)


def is_x_ku_conflict_reason(reason: str | None) -> bool:
    """Check if a reason string indicates an X-Ku band conflict.

    Args:
        reason: The reason string to check

    Returns:
        True if the reason indicates an X-Ku conflict
    """
    if not reason:
        return False
    return reason.startswith("X-Ku Conflict")


def segment_is_x_ku_warning(segment: TimelineSegment) -> bool:
    """Determine if a segment represents an X-Ku conflict warning.

    An X-Ku warning is when:
    - X-Band is degraded
    - Only X-Band is impacted
    - All reasons are X-Ku conflicts

    Args:
        segment: The timeline segment to check

    Returns:
        True if the segment is an X-Ku conflict warning
    """
    if segment.x_state != TransportState.DEGRADED:
        return False
    if any(transport != Transport.X for transport in segment.impacted_transports):
        return False
    if not segment.reasons:
        return False
    return all(is_x_ku_conflict_reason(reason) for reason in segment.reasons)


def display_transport_state(
    state: TransportState,
    *,
    warning_override: bool = False,
) -> str:
    """Convert a transport state to display text.

    If warning_override is True and state is DEGRADED, returns "WARNING".
    Otherwise returns the state value in uppercase.

    Args:
        state: The transport state to display
        warning_override: Whether to override DEGRADED with "WARNING"

    Returns:
        Display text for the transport state
    """
    if warning_override and state == TransportState.DEGRADED:
        return "WARNING"
    return state.value.upper()
