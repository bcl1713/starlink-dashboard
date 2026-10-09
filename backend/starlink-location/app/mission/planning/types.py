"""Leaf planning records shared with legacy mission models."""

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


def utc_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("A timezone-aware UTC timestamp is required")
    return value.astimezone(timezone.utc)


UTCTimestamp = Annotated[datetime, AfterValidator(utc_timestamp)]
ContentHash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
PlanningPolicy = Literal["prefer_starshield_v1"]


class PlanningRecord(BaseModel):
    """Strict schemas for new planning writes, including finite geometry."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class RouteAnchor(PlanningRecord):
    """One immutable route occurrence with explicit timing semantics."""

    route_id: str = Field(min_length=1)
    content_hash: ContentHash
    segment_index: int = Field(ge=0)
    fraction: float = Field(ge=0, le=1)
    occurrence_id: str = Field(min_length=1)
    source_time: UTCTimestamp
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timing_mode: Literal["route_bound", "fixed_utc", "elapsed"] = "route_bound"
    elapsed_seconds: float | None = None

    @model_validator(mode="after")
    def validate_timing(self):
        if (self.timing_mode == "elapsed") != (self.elapsed_seconds is not None):
            raise ValueError("Only elapsed timing requires an elapsed_seconds offset")
        return self


class HeightProfilePoint(PlanningRecord):
    timestamp: UTCTimestamp
    height_meters: float
    source: Literal["confirmed_ar", "route", "cruise_fallback"]
    assumption: str | None = None


class EvaluationContext(PlanningRecord):
    """Persisted seed grid; selected unlocked schedules do not define it."""

    version: Literal["planning_v1"] = "planning_v1"
    input_identity: ContentHash
    seed_times: list[UTCTimestamp] = Field(default_factory=list)
    candidate_times: list[UTCTimestamp] = Field(default_factory=list)
    boundaries: list[UTCTimestamp] = Field(default_factory=list)
    source_hashes: dict[str, ContentHash] = Field(default_factory=dict)
    height_profile: list[HeightProfilePoint] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    candidate_cadence_seconds: Literal[60] = 60
    interval_semantics: Literal["half_open"] = "half_open"

    @field_validator("version", mode="before")
    @classmethod
    def known_version(cls, value):
        if value != "planning_v1":
            raise ValueError("Unknown evaluation version; explicit migration required")
        return value

    @model_validator(mode="after")
    def ordered_grid(self):
        for values in (self.seed_times, self.candidate_times, self.boundaries):
            if values != sorted(set(values)):
                raise ValueError("Evaluation times must be unique and increasing")
        if not set(self.candidate_times).issubset(self.boundaries):
            raise ValueError("Every candidate must be an evaluation boundary")
        if not set(self.seed_times).issubset(self.candidate_times):
            raise ValueError("Every seed must be retained as a candidate")
        return self
