"""Mission planning data models for satellite communication coordination.

This module defines Pydantic models for mission data, including transport
configurations, satellite transitions, air-refueling windows, and timeline
advisories.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Transport(str, Enum):
    """Enumeration of available communication transports."""

    X = "X"  # Fixed geostationary satellite
    KA = "Ka"  # Three geostationary satellites
    KU = "Ku"  # Always-on LEO constellation


class TransportState(str, Enum):
    """State of a communication transport during mission."""

    AVAILABLE = "available"
    DEGRADED = "degraded"
    OFFLINE = "offline"


class MissionPhase(str, Enum):
    """Phases of a mission timeline."""

    PRE_DEPARTURE = "pre_departure"
    IN_FLIGHT = "in_flight"
    POST_ARRIVAL = "post_arrival"


class TimelineStatus(str, Enum):
    """Overall communication status during a timeline segment."""

    NOMINAL = "nominal"  # All transports available
    DEGRADED = "degraded"  # One transport unavailable
    CRITICAL = "critical"  # Two or more transports unavailable


class XTransition(BaseModel):
    """Configuration for a satellite transition on the X transport.

    Transitions can occur at off-route coordinates; they are projected to
    the route for timing but rendered at actual coordinates for visualization.
    """

    id: str = Field(..., description="Unique transition identifier")
    latitude: float = Field(
        ...,
        description="Transition latitude in decimal degrees (-90 to 90)",
    )
    longitude: float = Field(
        ...,
        description="Transition longitude in decimal degrees (-180 to 180)",
    )
    target_satellite_id: str = Field(
        ..., description="Target satellite ID (e.g., 'X-1', 'X-2')"
    )
    target_beam_id: Optional[str] = Field(
        default=None, description="Optional target beam ID for same-satellite transitions"
    )
    is_same_satellite_transition: bool = Field(
        default=False, description="True if transitioning to different beam on same satellite"
    )

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v):
        """Validate latitude is in valid range (-90 to 90)."""
        if not -90 <= v <= 90:
            raise ValueError("Latitude must be between -90 and 90 degrees")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v):
        """Validate and normalize longitude to the -180 to 180 degree range.

        Intentionally accepts both longitude formats:
        - Standard (-180 to 180): negative for west, positive for east
        - Alternative (0 to 360): used in some systems for western hemisphere

        Values are normalized to -180 to 180 range.
        """
        if not -180 <= v <= 360:
            raise ValueError("Longitude must be between -180 and 360 degrees")
        if v > 180:
            v -= 360
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "x-transition-1",
                "latitude": 35.5,
                "longitude": -120.3,
                "target_satellite_id": "X-1",
                "target_beam_id": None,
                "is_same_satellite_transition": False,
            }
        }
    }


class KaOutage(BaseModel):
    """Optional outage window for Ka transport.

    Ka transitions are auto-calculated from coverage, but planners can
    schedule manual outage windows (e.g., maintenance, testing).
    """

    id: str = Field(..., description="Unique outage identifier")
    start_time: datetime = Field(
        ...,
        description="Start time of outage window (UTC, ISO-8601)",
    )
    duration_seconds: float = Field(
        ..., description="Duration of outage in seconds", gt=0
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "ka-outage-1",
                "start_time": "2025-10-27T18:30:00Z",
                "duration_seconds": 600.0,
            }
        }
    }


class AARWindow(BaseModel):
    """Air-Refueling (AAR) window defining a segment of the route.

    AAR windows are defined by start/end waypoint names from the active
    route's KML. During AAR, the X transport azimuth exclusion zone
    inverts to 315°–45°.
    """

    id: str = Field(..., description="Unique AAR window identifier")
    start_waypoint_name: str = Field(
        ...,
        description="Name of the starting waypoint (from KML) for AAR segment",
    )
    end_waypoint_name: str = Field(
        ...,
        description="Name of the ending waypoint (from KML) for AAR segment",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "aar-1",
                "start_waypoint_name": "AAR-Start",
                "end_waypoint_name": "AAR-End",
            }
        }
    }


class KuOutageOverride(BaseModel):
    """Manual override for Ku transport outage (LEO link failure).

    Ku is normally always-on; this allows planners to flag expected or
    actual downtime windows.
    """

    id: str = Field(..., description="Unique Ku outage identifier")
    start_time: datetime = Field(
        ...,
        description="Start time of outage window (UTC, ISO-8601)",
    )
    duration_seconds: float = Field(
        ..., description="Duration of outage in seconds", gt=0
    )
    reason: Optional[str] = Field(
        default=None, description="Reason for Ku outage override"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "ku-outage-1",
                "start_time": "2025-10-27T20:15:00Z",
                "duration_seconds": 300.0,
                "reason": "Planned maintenance window",
            }
        }
    }


class TransportConfig(BaseModel):
    """Configuration for all three transports in the mission."""

    initial_x_satellite_id: str = Field(
        ...,
        description="Initial X satellite ID at mission start (e.g., 'X-1')",
    )
    initial_ka_satellite_ids: list[str] = Field(
        default_factory=lambda: ["AOR", "POR", "IOR"],
        description="Initial Ka satellite IDs (default: AOR, POR, IOR)",
    )
    x_transitions: list[XTransition] = Field(
        default_factory=list,
        description="List of X transport satellite transitions",
    )
    ka_outages: list[KaOutage] = Field(
        default_factory=list,
        description="Optional Ka outage windows (auto-calculated transitions supplement these)",
    )
    aar_windows: list[AARWindow] = Field(
        default_factory=list,
        description="Air-refueling segments",
    )
    ku_overrides: list[KuOutageOverride] = Field(
        default_factory=list,
        description="Manual Ku outage overrides",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "initial_x_satellite_id": "X-1",
                "initial_ka_satellite_ids": ["AOR", "POR", "IOR"],
                "x_transitions": [],
                "ka_outages": [],
                "aar_windows": [],
                "ku_overrides": [],
            }
        }
    }


class TimelineAdvisory(BaseModel):
    """Operator advisory for a specific time window.

    Advisories guide operators on manual actions (e.g., "Disable X from
    01:25Z to 02:10Z due to transition") and highlight risk windows.
    """

    id: str = Field(..., description="Unique advisory identifier")
    timestamp: datetime = Field(
        ...,
        description="Time when advisory applies (UTC, ISO-8601)",
    )
    event_type: str = Field(
        ...,
        description="Type of event (e.g., 'transition', 'azimuth_conflict', 'buffer', 'aar_window')",
    )
    transport: Transport = Field(
        ...,
        description="Affected transport (X, Ka, Ku)",
    )
    severity: str = Field(
        default="info",
        description="Severity level (info, warning, critical)",
    )
    message: str = Field(
        ...,
        description="Human-readable advisory message",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Additional context (e.g., satellite ID, reason codes)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "advisory-001",
                "timestamp": "2025-10-27T18:25:00Z",
                "event_type": "transition",
                "transport": "X",
                "severity": "warning",
                "message": "Disable X from 18:25Z to 18:40Z due to transition to X-2",
                "metadata": {
                    "reason": "transition",
                    "satellite_from": "X-1",
                    "satellite_to": "X-2",
                    "buffer_minutes": 15,
                },
            }
        }
    }


class MissionLeg(BaseModel):
    """Complete mission leg configuration for communication planning.

    A mission leg ties together a timed flight route with transport assignments,
    satellite transitions, operational constraints (AAR, buffers), and
    produces a communication timeline for planning and customer delivery.
    """

    id: str = Field(
        ...,
        description="Unique mission identifier (UUID or slug)",
    )
    name: str = Field(
        ...,
        description="Human-readable mission name",
        min_length=1,
    )
    description: Optional[str] = Field(
        default=None,
        description="Detailed mission description",
    )
    route_id: str = Field(
        ...,
        description="Associated flight route ID (from route system)",
    )
    transports: TransportConfig = Field(
        ...,
        description="Transport and satellite configuration",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When mission was created (UTC, ISO-8601)",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When mission was last updated (UTC, ISO-8601)",
    )
    is_active: bool = Field(
        default=False,
        description="Whether this mission is currently active",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Planner notes or remarks",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "mission-001",
                "name": "Leg 6 Rev 6 - KSA to Europe",
                "description": "Cross-continental flight with two X transitions and one AAR",
                "route_id": "leg-6-rev-6",
                "transports": {
                    "initial_x_satellite_id": "X-1",
                    "initial_ka_satellite_ids": ["AOR", "POR", "IOR"],
                    "x_transitions": [],
                    "ka_outages": [],
                    "aar_windows": [],
                    "ku_overrides": [],
                },
                "created_at": "2025-10-20T10:30:00Z",
                "updated_at": "2025-10-20T10:30:00Z",
                "is_active": False,
                "notes": "Customer ready for briefing after timeline validation",
            }
        }
    }


class TimelineSegment(BaseModel):
    """A contiguous time segment in the mission with uniform communication state."""

    id: str = Field(..., description="Unique segment identifier")
    start_time: datetime = Field(
        ...,
        description="Segment start time (UTC, ISO-8601)",
    )
    end_time: datetime = Field(
        ...,
        description="Segment end time (UTC, ISO-8601)",
    )
    status: TimelineStatus = Field(
        ...,
        description="Communication status during segment (nominal, degraded, critical)",
    )
    x_state: TransportState = Field(
        default=TransportState.AVAILABLE,
        description="X transport state during segment",
    )
    ka_state: TransportState = Field(
        default=TransportState.AVAILABLE,
        description="Ka transport state during segment",
    )
    ku_state: TransportState = Field(
        default=TransportState.AVAILABLE,
        description="Ku transport state during segment",
    )
    reasons: list[str] = Field(
        default_factory=list,
        description="Reason codes explaining segment status (e.g., 'x_azimuth_conflict', 'ka_coverage_gap')",
    )
    impacted_transports: list[Transport] = Field(
        default_factory=list,
        description="Transports that are degraded or offline",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Additional context (e.g., satellite IDs, event triggers)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "segment-001",
                "start_time": "2025-10-27T16:45:00Z",
                "end_time": "2025-10-27T18:25:00Z",
                "status": "nominal",
                "x_state": "available",
                "ka_state": "available",
                "ku_state": "available",
                "reasons": [],
                "impacted_transports": [],
                "metadata": {"satellites": {"X": "X-1", "Ka": ["AOR", "POR", "IOR"]}},
            }
        }
    }


class MissionTimeline(BaseModel):
    """Complete timeline for a mission showing communication state evolution."""

    mission_id: str = Field(..., description="Associated mission ID")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When timeline was computed (UTC, ISO-8601)",
    )
    segments: list[TimelineSegment] = Field(
        default_factory=list,
        description="Ordered list of timeline segments",
    )
    advisories: list[TimelineAdvisory] = Field(
        default_factory=list,
        description="Operator advisories for the mission",
    )
    statistics: dict = Field(
        default_factory=dict,
        description="Summary statistics (e.g., degraded_seconds, critical_seconds)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "mission_id": "mission-001",
                "created_at": "2025-10-27T10:00:00Z",
                "segments": [],
                "advisories": [],
                "statistics": {
                    "total_duration_seconds": 19800,
                    "nominal_seconds": 18000,
                    "degraded_seconds": 1200,
                    "critical_seconds": 600,
                },
            }
        }
    }
