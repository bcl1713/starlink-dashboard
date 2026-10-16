"""Typed, serializable evidence and movement contracts."""

from math import isfinite
from typing import Literal
from uuid import uuid4

from pydantic import AwareDatetime, BaseModel, Field

from app.services.position_freshness import (
    observation_time,
    position_observation,
    speed_is_fresh,
)

EventKind = Literal[
    "off_blocks", "takeoff", "landed", "on_blocks", "correction", "stop_classified"
]
MovementState = Literal[
    "unknown",
    "parked",
    "taxi_out",
    "airborne",
    "probable_landed_rollout",
    "taxi_in",
    "parked_at_stop",
]


class DetectionPolicy(BaseModel):
    """Engineering defaults, not calibrated aircraft operating limits."""

    movement_knots: float = Field(default=3, gt=0)
    movement_dwell: float = Field(default=15, gt=0)
    airborne_knots: float = Field(default=80, gt=0)
    airborne_dwell: float = Field(default=20, gt=0)
    altitude_change_feet: float = Field(default=200, gt=0)
    landing_knots: float = Field(default=35, gt=0)
    landing_dwell: float = Field(default=20, gt=0)
    landing_stable_feet: float = Field(default=75, gt=0)
    parking_knots: float = Field(default=1, ge=0)
    parking_dwell: float = Field(default=300, gt=0)
    parking_radius_m: float = Field(default=50, gt=0)
    destination_radius_m: float = Field(default=10000, gt=100)


class FlightObservation(BaseModel):
    observed_at: AwareDatetime
    received_at: AwareDatetime | None = None
    position_observed_at: AwareDatetime | None = None
    speed_observed_at: AwareDatetime | None = None
    altitude_observed_at: AwareDatetime | None = None
    altitude_validity_source: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    speed_knots: float | None = None
    altitude_feet: float | None = None
    altitude_usable: bool = False
    source_mode: Literal["live", "simulation"]
    mission_id: str
    leg_id: str
    route_id: str
    destination_distance_m: float | None = None

    @property
    def usable_motion(self) -> bool:
        return position_observation(
            self.latitude,
            self.longitude,
            self.position_observed_at,
            self.received_at or self.observed_at,
        )[1] == "fresh" and speed_is_fresh(
            self.speed_knots,
            self.speed_observed_at,
            self.received_at or self.observed_at,
        )

    @property
    def usable_altitude(self) -> bool:
        return bool(
            self.altitude_usable
            and self.altitude_validity_source
            and self.altitude_feet is not None
            and isfinite(self.altitude_feet)
            and observation_time(
                self.altitude_observed_at, self.received_at or self.observed_at
            )[1]
            == "fresh"
        )


class FlightEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    mission_id: str
    leg_id: str
    kind: EventKind
    occurred_at: AwareDatetime
    detected_at: AwareDatetime
    source: Literal["inferred", "manual"]
    confidence: Literal["inferred", "operator_confirmed"] = "inferred"
    evidence: dict = Field(default_factory=dict)
    revision: int = 1


class Candidate(BaseModel):
    kind: str
    since: AwareDatetime
    latitude: float | None = None
    longitude: float | None = None
    altitude_feet: float | None = None


class DetectionState(BaseModel):
    movement: MovementState = "unknown"
    uncertain: bool = True
    last_observed_at: AwareDatetime | None = None
    candidate: Candidate | None = None
    parked_altitude: float | None = None
    max_airborne_altitude: float | None = None
    landed_altitude: float | None = None
    destination_complete: bool = False


class DetectionResult(BaseModel):
    state: DetectionState
    emitted_events: list[FlightEvent] = Field(default_factory=list)
    candidate_changes: list[dict] = Field(default_factory=list)
    leg_completion: bool = False
