"""Rule evaluation engine for communication constraints and mission advisories.

Combines azimuth checks, coverage events, takeoff/landing buffers, and AAR
windows to produce operator advisories and mission event lists.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from app.mission.models import MissionPhase, TimelineStatus, Transport, TransportState
from app.satellites.geometry import is_in_azimuth_range, look_angles

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of mission events affecting transport availability."""

    X_AZIMUTH_VIOLATION = "x_azimuth_violation"
    X_TRANSITION_START = "x_transition_start"
    X_TRANSITION_END = "x_transition_end"
    KA_COVERAGE_ENTRY = "ka_coverage_entry"
    KA_COVERAGE_EXIT = "ka_coverage_exit"
    KA_TRANSITION = "ka_transition"
    KA_OUTAGE_START = "ka_outage_start"
    KA_OUTAGE_END = "ka_outage_end"
    KU_OUTAGE_START = "ku_outage_start"
    KU_OUTAGE_END = "ku_outage_end"
    TAKEOFF_BUFFER = "takeoff_buffer"
    LANDING_BUFFER = "landing_buffer"
    AAR_WINDOW = "aar_window"


@dataclass
class MissionEvent:
    """Represents an event affecting transport availability during mission."""

    timestamp: datetime
    event_type: EventType
    transport: Transport
    affected_transport: Optional[Transport] = None  # What transport is affected
    severity: str = "warning"  # "info", "warning", "critical"
    reason: str = ""
    satellite_id: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def __lt__(self, other: "MissionEvent") -> bool:
        """Allow sorting by timestamp."""
        return self.timestamp < other.timestamp


@dataclass
class ConstraintConfig:
    """Configuration for X transport azimuth constraints and buffers."""

    normal_azimuth_min: float = 135.0  # Normal ops: 135° to 225° forbidden
    normal_azimuth_max: float = 225.0
    aar_azimuth_min: float = 315.0  # AAR: 315° to 45° forbidden (wraps)
    aar_azimuth_max: float = 45.0

    transition_buffer_minutes: int = 15  # ±15 min degrade around transitions
    takeoff_buffer_minutes: int = 15  # Pre-departure blackout
    landing_buffer_minutes: int = 15  # Post-arrival blackout

    elevation_min_degrees: float = 0.0  # Minimum elevation for visibility


class RuleEngine:
    """Evaluates communication constraints and generates mission events."""

    def __init__(self, config: Optional[ConstraintConfig] = None):
        """Initialize rule engine with optional custom config.

        Args:
            config: ConstraintConfig for azimuth/buffer settings
        """
        self.config = config or ConstraintConfig()
        self.events: List[MissionEvent] = []

    def evaluate_x_azimuth_window(
        self,
        aircraft_lat: float,
        aircraft_lon: float,
        aircraft_alt: float,
        satellite_lon: float,
        timestamp: datetime,  # noqa: ARG002 (timestamp reserved for future logging)
        is_aar_mode: bool = False,
        heading_deg: float | None = None,
    ) -> Tuple[bool, float, Dict[str, float | bool]]:
        """Evaluate if aircraft-to-satellite azimuth violates constraints.

        Args:
            aircraft_lat: Aircraft latitude
            aircraft_lon: Aircraft longitude
            aircraft_alt: Aircraft altitude in meters
            satellite_lon: Satellite longitude (assumes equator at geostationary altitude)
            is_aar_mode: True if in AAR phase (different azimuth constraints)
            heading_deg: Optional aircraft heading for relative azimuth calculation

        Returns:
            Tuple of (is_violation, relative_azimuth_degrees, debug_metadata)
        """
        azimuth, elevation = look_angles(
            aircraft_lat, aircraft_lon, aircraft_alt, satellite_lon
        )
        relative_azimuth = _relative_to_heading(azimuth, heading_deg)
        debug_metadata: Dict[str, float | bool] = {
            "absolute_azimuth_degrees": azimuth,
            "relative_azimuth_degrees": relative_azimuth,
            "elevation_degrees": elevation,
            "min_elevation_degrees": self.config.elevation_min_degrees,
        }

        # Check elevation minimum
        elevation_violation = elevation < self.config.elevation_min_degrees
        debug_metadata["elevation_below_min"] = elevation_violation
        if elevation_violation:
            debug_metadata["violation_reason"] = "elevation"
            return True, relative_azimuth, debug_metadata

        # Check azimuth constraint
        if is_aar_mode:
            min_az = self.config.aar_azimuth_min
            max_az = self.config.aar_azimuth_max
        else:
            min_az = self.config.normal_azimuth_min
            max_az = self.config.normal_azimuth_max

        is_in_forbidden = is_in_azimuth_range(relative_azimuth, min_az, max_az)
        if is_in_forbidden:
            debug_metadata["violation_reason"] = "azimuth"
        return is_in_forbidden, relative_azimuth, debug_metadata

    def add_x_transition_events(
        self,
        transition_time: datetime,
        satellite_id: str,
        is_aar_mode: bool = False,
    ) -> None:
        """Add degradation events around X satellite transition.

        Injects ±15-minute degrade windows.

        Args:
            transition_time: Planned transition timestamp
            satellite_id: Target satellite ID (e.g., 'X-1')
            is_aar_mode: True if during AAR phase
        """
        buffer = timedelta(minutes=self.config.transition_buffer_minutes)

        # Event at transition start (degrade begins)
        self.events.append(
            MissionEvent(
                timestamp=transition_time - buffer,
                event_type=EventType.X_TRANSITION_START,
                transport=Transport.X,
                affected_transport=Transport.X,
                severity="warning",
                reason=f"X Transition to {satellite_id}",
                satellite_id=satellite_id,
            )
        )

        # Event at transition end (degrade ends)
        self.events.append(
            MissionEvent(
                timestamp=transition_time + buffer,
                event_type=EventType.X_TRANSITION_END,
                transport=Transport.X,
                affected_transport=Transport.X,
                severity="info",
                reason=f"X Transition to {satellite_id}",
                satellite_id=satellite_id,
            )
        )

    def add_ka_coverage_events(
        self, entry_time: datetime, exit_time: datetime, satellite_id: str
    ) -> None:
        """Add Ka coverage entry/exit events.

        Args:
            entry_time: Time entering coverage
            exit_time: Time exiting coverage
            satellite_id: Satellite ID (e.g., 'AOR')
        """
        self.events.append(
            MissionEvent(
                timestamp=entry_time,
                event_type=EventType.KA_COVERAGE_ENTRY,
                transport=Transport.KA,
                affected_transport=Transport.KA,
                severity="info",
                reason=f"Ka coverage {satellite_id} available",
                satellite_id=satellite_id,
            )
        )

        self.events.append(
            MissionEvent(
                timestamp=exit_time,
                event_type=EventType.KA_COVERAGE_EXIT,
                transport=Transport.KA,
                affected_transport=Transport.KA,
                severity="warning",
                reason=f"Ka coverage {satellite_id} lost",
                satellite_id=satellite_id,
            )
        )

    def add_manual_outage_events(
        self,
        start_time: datetime,
        end_time: datetime,
        transport: Transport,
        reason: str = "",
    ) -> None:
        """Add manual outage window events (Ka/Ku).

        Args:
            start_time: Outage start
            end_time: Outage end
            transport: Affected transport (Ka or Ku)
            reason: Reason for outage
        """
        outage_type = f"{transport.value.lower()}_outage".replace("-", "_")

        self.events.append(
            MissionEvent(
                timestamp=start_time,
                event_type=EventType(f"{outage_type}_start"),
                transport=transport,
                affected_transport=transport,
                severity="warning",
                reason=reason or f"{transport} outage",
            )
        )

        self.events.append(
            MissionEvent(
                timestamp=end_time,
                event_type=EventType(f"{outage_type}_end"),
                transport=transport,
                affected_transport=transport,
                severity="info",
                reason=f"{transport} outage ended",
            )
        )

    def add_takeoff_landing_buffers(
        self, departure_time: datetime, landing_time: datetime
    ) -> None:
        """Add takeoff/landing blackout windows.

        Args:
            departure_time: Planned takeoff
            landing_time: Planned arrival
        """
        takeoff_buffer = timedelta(minutes=self.config.takeoff_buffer_minutes)
        landing_buffer = timedelta(minutes=self.config.landing_buffer_minutes)

        self._emit_comm_safety_window(
            timestamp=departure_time,
            event_type=EventType.TAKEOFF_BUFFER,
            severity="safety",
            reason="Safety-of-Flight (takeoff)",
        )
        self._emit_comm_safety_window(
            timestamp=departure_time + takeoff_buffer,
            event_type=EventType.TAKEOFF_BUFFER,
            severity="info",
            reason="Takeoff window complete",
        )

        self._emit_comm_safety_window(
            timestamp=landing_time - landing_buffer,
            event_type=EventType.LANDING_BUFFER,
            severity="safety",
            reason="Safety-of-Flight (landing)",
        )
        self._emit_comm_safety_window(
            timestamp=landing_time,
            event_type=EventType.LANDING_BUFFER,
            severity="info",
            reason="Landing window complete",
        )

    def add_aar_window_events(
        self, start_time: datetime, end_time: datetime, window_name: str = ""
    ) -> None:
        """Add AAR (air-refueling) window events.

        Args:
            start_time: AAR start
            end_time: AAR end
            window_name: Optional window identifier
        """
        start_label = "AAR Start"
        end_label = "AAR End"
        self.events.append(
            MissionEvent(
                timestamp=start_time,
                event_type=EventType.AAR_WINDOW,
                transport=Transport.X,
                affected_transport=Transport.X,
                severity="safety",
                reason=start_label,
            )
        )

        self.events.append(
            MissionEvent(
                timestamp=end_time,
                event_type=EventType.AAR_WINDOW,
                transport=Transport.X,
                affected_transport=Transport.X,
                severity="info",
                reason=end_label,
            )
        )

    def get_sorted_events(self) -> List[MissionEvent]:
        """Get all events sorted by timestamp.

        Returns:
            Sorted list of MissionEvent objects
        """
        return sorted(self.events)

    def generate_advisories(self) -> List[str]:
        """Generate human-readable mission advisories from events.

        Returns:
            List of advisory strings (e.g., "Disable X from 01:25Z to 02:10Z")
        """
        advisories = []
        events = self.get_sorted_events()

        # Group related events
        i = 0
        while i < len(events):
            event = events[i]

            if event.event_type == EventType.X_TRANSITION_START:
                # Find corresponding end event
                end_idx = None
                for j in range(i + 1, len(events)):
                    if (
                        events[j].event_type == EventType.X_TRANSITION_END
                        and events[j].satellite_id == event.satellite_id
                    ):
                        end_idx = j
                        break

                if end_idx:
                    end_time = events[end_idx].timestamp
                    advisory = (
                        f"Disable X from {event.timestamp.strftime('%H:%MZ')} to "
                        f"{end_time.strftime('%H:%MZ')} during transition to {event.satellite_id}"
                    )
                    advisories.append(advisory)
                    i = end_idx + 1
                else:
                    i += 1
            else:
                i += 1

        return advisories

    def clear_events(self) -> None:
        """Clear all accumulated events."""
        self.events = []


    def _emit_comm_safety_window(
        self,
        timestamp: datetime,
        event_type: EventType,
        severity: str,
        reason: str,
    ) -> None:
        """Emit takeoff/landing safety window events for all transports."""
        for transport in (Transport.X, Transport.KA, Transport.KU):
            self.events.append(
                MissionEvent(
                    timestamp=timestamp,
                    event_type=event_type,
                    transport=transport,
                    affected_transport=transport,
                    severity=severity,
                    reason=reason,
                )
            )


def _relative_to_heading(azimuth: float, heading_deg: float | None) -> float:
    """Convert absolute azimuth to heading-relative azimuth (nose = 0°)."""
    azimuth = azimuth % 360.0
    if heading_deg is None:
        return azimuth
    return (azimuth - heading_deg) % 360.0
