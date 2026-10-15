"""Complete typed flight/detection checkpoint for activation compensation."""

from dataclasses import dataclass
from datetime import datetime

from app.models.flight_status import FlightStatus


@dataclass(frozen=True)
class FlightStateCheckpoint:
    status: FlightStatus
    last_detection_observed_at: datetime | None
    speed_persistence_seconds: float
    last_speed_sample_time: datetime | None
    above_threshold_start_time: datetime | None
    arrival_start_time: datetime | None
    arrival_distance_at_start: float | None
