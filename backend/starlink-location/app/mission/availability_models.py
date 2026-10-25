"""Persisted planned eligibility and append-only operational change records."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class Transport(str, Enum):
    """Canonical RF transport keys; Ku is displayed as Starshield."""

    X = "X"
    KA = "Ka"
    KU = "Ku"


def aware_utc(value: datetime) -> datetime:
    """Reject ambiguous mission-clock instants and normalize offsets to UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Availability timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


class AvailabilityChange(BaseModel):
    """One immutable failure/restoration command at an authoritative clock instant.

    Restoration is another record, never an edit to the original failure.
    A null simulation_run_id identifies live mission operations.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    transport: Transport
    unavailable: StrictBool
    effective_at: datetime
    reason: str | None = None
    simulation_run_id: str | None = Field(default=None, min_length=1)

    @field_validator("effective_at")
    @classmethod
    def validate_time(cls, value: datetime) -> datetime:
        return aware_utc(value)


class MissionAvailability(BaseModel):
    """Mission defaults and immutable operational history.

    Missing default keys mean eligible, except for the legacy per-leg
    starshield_enabled fallback. Saving an explicit Ku default supersedes it.
    Writers replace this model under the repository's revision guard.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    revision: int = Field(default=0, ge=0)
    defaults: dict[Transport, StrictBool] = Field(default_factory=dict)
    history: tuple[AvailabilityChange, ...] = ()
    simulation_run_id: str | None = Field(default=None, min_length=1)

    @field_validator("history")
    @classmethod
    def validate_history(cls, value: tuple[AvailabilityChange, ...]):
        ids: set[str] = set()
        previous: dict[str | None, datetime] = {}
        for record in value:
            if record.id in ids:
                raise ValueError("Availability change IDs must be unique")
            ids.add(record.id)
            prior = previous.get(record.simulation_run_id)
            if prior is not None and record.effective_at < prior:
                raise ValueError(
                    "Availability history must be chronological within each run"
                )
            previous[record.simulation_run_id] = record.effective_at
        return value


class FailureWindow(BaseModel):
    """Derived half-open failure window; an absent end persists indefinitely."""

    model_config = ConfigDict(frozen=True)

    transport: Transport
    start: datetime
    end: datetime | None = None


class LegAvailability(BaseModel):
    """Immutable resolved planning input detached from mutable mission models."""

    model_config = ConfigDict(frozen=True)

    mission_id: str
    leg_id: str
    revision: int
    simulation_run_id: str | None = None
    planned: tuple[tuple[Transport, bool], ...]
    failures: tuple[FailureWindow, ...] = ()

    def resolve(self, at: datetime) -> dict[Transport, bool]:
        at = aware_utc(at)
        result = dict(self.planned)
        for window in self.failures:
            if window.start <= at and (window.end is None or at < window.end):
                result[window.transport] = False
        return result

    def boundaries(self, start: datetime, end: datetime) -> tuple[datetime, ...]:
        """Internal change instants only; callers already own interval endpoints."""
        start, end = aware_utc(start), aware_utc(end)
        if end < start:
            raise ValueError("Availability interval end precedes start")
        return tuple(
            sorted(
                {
                    instant
                    for window in self.failures
                    for instant in (window.start, window.end)
                    if instant is not None and start < instant < end
                }
            )
        )
