"""Read-only full mission chronology, independent of notification snapshots."""

from typing import Literal

from pydantic import Field

from .common import Identifier, SchemaVersion, StrictModel
from .event_models import OperationalEvent, SourceCapture
from .time_models import UtcTimestamp


class TimelineLeg(StrictModel):
    leg_id: str
    name: str
    coverage: Literal["available", "partial", "last_known", "unavailable"]
    reason: str | None = None
    scheduled_departure_at: UtcTimestamp | None = None
    scheduled_arrival_at: UtcTimestamp | None = None


class MissionTimelineSnapshot(StrictModel):
    schema_version: SchemaVersion = 1
    mission_id: Identifier
    store_id: str
    api_epoch: str
    source_mode: Literal["live", "simulation"]
    simulation_run_id: str | None = None
    as_of: UtcTimestamp
    generation: str
    H: int
    legs: list[TimelineLeg] = Field(default_factory=list)
    sources: list[SourceCapture] = Field(default_factory=list)
    events: list[OperationalEvent] = Field(default_factory=list)
