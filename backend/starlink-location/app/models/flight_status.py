"""Flight status and ETA mode data models for the Starlink location service."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FlightPhase(str, Enum):
    """Enumeration of flight phases for state transitions."""

    PRE_DEPARTURE = "pre_departure"
    IN_FLIGHT = "in_flight"
    POST_ARRIVAL = "post_arrival"


class ETAMode(str, Enum):
    """Enumeration of ETA calculation modes."""

    ANTICIPATED = "anticipated"  # Pre-departure: based on flight plan
    ESTIMATED = "estimated"  # Post-departure: based on real-time telemetry


class FlightStatus(BaseModel):
    """Current flight status and phase information."""

    phase: FlightPhase = Field(
        default=FlightPhase.PRE_DEPARTURE,
        description="Current flight phase (pre_departure, in_flight, post_arrival)",
    )
    eta_mode: ETAMode = Field(
        default=ETAMode.ANTICIPATED,
        description="Current ETA calculation mode (anticipated or estimated)",
    )
    active_route_id: Optional[str] = Field(
        default=None,
        description="Identifier of the active route associated with this flight, if any",
    )
    active_route_name: Optional[str] = Field(
        default=None,
        description="Human-readable name of the active route associated with this flight",
    )
    has_timing_data: bool = Field(
        default=False,
        description="Whether the active route provides timing metadata for anticipated ETAs",
    )
    scheduled_departure_time: Optional[datetime] = Field(
        default=None,
        description="Scheduled departure time (UTC, ISO-8601) from the active route timing profile",
    )
    scheduled_arrival_time: Optional[datetime] = Field(
        default=None,
        description="Scheduled arrival time (UTC, ISO-8601) from the active route timing profile",
    )
    departure_time: Optional[datetime] = Field(
        default=None,
        description="Actual departure time (UTC, ISO-8601) when detected/manual",
    )
    arrival_time: Optional[datetime] = Field(
        default=None,
        description="Actual arrival time (UTC, ISO-8601) when detected/manual",
    )
    speed_persistence_seconds: float = Field(
        default=0.0,
        description="Seconds aircraft has maintained speed above departure threshold",
    )
    last_departure_check_time: Optional[datetime] = Field(
        default=None,
        description="Last time departure was checked (for speed persistence tracking)",
    )
    last_arrival_check_time: Optional[datetime] = Field(
        default=None,
        description="Last time arrival was checked (for dwell time tracking)",
    )
    time_until_departure_seconds: Optional[float] = Field(
        default=None,
        description="Seconds until departure (positive pre-departure, 0 once departed, negative if delayed)",
    )
    time_since_departure_seconds: Optional[float] = Field(
        default=None,
        description="Seconds since departure (only populated after departure is detected)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "phase": "in_flight",
                "eta_mode": "estimated",
                "active_route_id": "leg-1-rev-6",
                "active_route_name": "Leg 1 Rev 6",
                "has_timing_data": True,
                "scheduled_departure_time": "2025-10-27T16:45:00Z",
                "scheduled_arrival_time": "2025-10-27T22:05:00Z",
                "departure_time": "2025-10-27T16:57:55Z",
                "arrival_time": None,
                "speed_persistence_seconds": 15.0,
                "last_departure_check_time": "2025-10-27T16:57:55Z",
                "last_arrival_check_time": None,
                "time_until_departure_seconds": 0.0,
                "time_since_departure_seconds": 720.0,
            }
        }
    }


class FlightStatusResponse(BaseModel):
    """Response model for flight status API endpoint."""

    phase: FlightPhase = Field(..., description="Current flight phase")
    eta_mode: ETAMode = Field(..., description="Current ETA calculation mode")
    active_route_id: Optional[str] = Field(
        default=None,
        description="Identifier of the active route associated with this flight, if any",
    )
    active_route_name: Optional[str] = Field(
        default=None,
        description="Human-readable name of the active route associated with this flight",
    )
    has_timing_data: bool = Field(
        default=False,
        description="Whether the active route provides timing metadata",
    )
    scheduled_departure_time: Optional[datetime] = Field(
        default=None,
        description="Scheduled departure time (UTC, ISO-8601) from the active route timing profile",
    )
    scheduled_arrival_time: Optional[datetime] = Field(
        default=None,
        description="Scheduled arrival time (UTC, ISO-8601) from the active route timing profile",
    )
    departure_time: Optional[datetime] = Field(
        default=None, description="Actual departure time when detected"
    )
    arrival_time: Optional[datetime] = Field(
        default=None, description="Actual arrival time when detected"
    )
    time_until_departure_seconds: Optional[float] = Field(
        default=None,
        description="Seconds until departure (positive pre-departure, 0 once departed, negative if delayed)",
    )
    time_since_departure_seconds: Optional[float] = Field(
        default=None,
        description="Seconds since departure (only populated after departure)",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of this status",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "phase": "in_flight",
                "eta_mode": "estimated",
                "active_route_id": "leg-1-rev-6",
                "active_route_name": "Leg 1 Rev 6",
                "has_timing_data": True,
                "scheduled_departure_time": "2025-10-27T16:45:00Z",
                "scheduled_arrival_time": "2025-10-27T22:05:00Z",
                "departure_time": "2025-10-27T16:57:55Z",
                "arrival_time": None,
                "time_until_departure_seconds": 0.0,
                "time_since_departure_seconds": 720.0,
                "timestamp": "2025-10-27T16:58:00Z",
            }
        }
    }


class ManualFlightPhaseTransition(BaseModel):
    """Request model for manual flight phase transitions."""

    phase: FlightPhase = Field(
        ...,
        description="Target flight phase (pre_departure, in_flight, post_arrival)",
    )
    reason: Optional[str] = Field(
        default=None, description="Reason for manual transition (for logging)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "phase": "in_flight",
                "reason": "Manual correction: aircraft took off earlier than expected",
            }
        }
    }


class DepartureUpdateRequest(BaseModel):
    """Manual override request for setting departure time and transitioning to in-flight."""

    timestamp: Optional[datetime] = Field(
        default=None,
        description="Explicit departure timestamp (UTC, ISO-8601). Defaults to now if omitted.",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Optional reason for the manual departure trigger (for audit logging).",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "timestamp": "2025-10-27T16:46:30Z",
                "reason": "Manual departure trigger during simulation reset",
            }
        }
    }


class ArrivalUpdateRequest(BaseModel):
    """Manual override request for setting arrival time and transitioning to post-arrival."""

    timestamp: Optional[datetime] = Field(
        default=None,
        description="Explicit arrival timestamp (UTC, ISO-8601). Defaults to now if omitted.",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Optional reason for the manual arrival trigger (for audit logging).",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "timestamp": "2025-10-27T22:03:10Z",
                "reason": "Manual arrival trigger following ATC confirmation",
            }
        }
    }
