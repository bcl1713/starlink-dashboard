"""Immutable UTC evidence and classifications for secure-call continuity."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.services.pop.models import ImmutableRecord, UtcTime

Capability = Literal["available", "unavailable", "unknown"]
Classification = Literal[
    "ordinary", "advisory", "x_fallback", "planned_outage", "existing_outage", "unknown"
]
Seconds = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class CapabilitySpan(ImmutableRecord):
    start_utc: UtcTime
    end_utc: UtcTime
    ka: Capability
    x: Capability
    starshield: Capability
    x_concurrency_only: bool = False
    existing_call_outage: bool = False
    source_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def valid_interval(self):
        if self.end_utc <= self.start_utc:
            raise ValueError("Capability bounds require start before end")
        if self.x_concurrency_only and self.x != "unavailable":
            raise ValueError("Concurrency fallback requires unavailable operating X")
        return self


class CallContinuityInterval(ImmutableRecord):
    start_utc: UtcTime
    end_utc: UtcTime
    classification: Classification
    transition_ids: tuple[str, ...] = ()
    usable_alternatives: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def valid_interval(self):
        if self.end_utc <= self.start_utc:
            raise ValueError("Continuity bounds require start before end")
        return self


class CallContinuityProjection(ImmutableRecord):
    revision: str = Field(min_length=1)
    intervals: tuple[CallContinuityInterval, ...]
    planned_communications_outage_seconds: Seconds
    pop_call_outage_seconds: Seconds
    longest_call_outage_seconds: Seconds
