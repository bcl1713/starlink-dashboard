"""Immutable shared records for advisory PoP predictions and observations."""

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from app.services.ground_entry_point import GroundEntryPoint

Latitude = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("PoP timestamps must include a timezone")
    return value.astimezone(timezone.utc)


UtcTime = Annotated[datetime, AfterValidator(_utc)]


class ImmutableRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PopSite(ImmutableRecord):
    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    city: str
    country: str
    latitude: Latitude
    longitude: Longitude
    aliases: tuple[str, ...] = ()
    source: str
    coordinate_source: str

    @field_validator("city", "country", "source", "coordinate_source")
    @classmethod
    def nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Site identity and source fields must not be empty")
        return value

    @field_validator("aliases")
    @classmethod
    def nonempty_aliases(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("Aliases must not be empty")
        return tuple(sorted({value.strip() for value in values}))


class PopCatalog(ImmutableRecord):
    sites: tuple[PopSite, ...] = Field(min_length=1)
    fingerprint: str


class RouteVertex(ImmutableRecord):
    latitude: Latitude
    longitude: Longitude


class PopCrossing(ImmutableRecord):
    id: str
    from_pop_id: str
    to_pop_id: str
    from_city: str | None = None
    to_city: str | None = None
    segment_index: int = Field(ge=0)
    fraction: float = Field(ge=0, le=1, allow_inf_nan=False)
    latitude: Latitude
    longitude: Longitude
    distance_meters: float = Field(ge=0, allow_inf_nan=False)


class PopTransition(ImmutableRecord):
    crossing: PopCrossing
    crossing_utc: UtcTime
    window_start_utc: UtcTime
    window_end_utc: UtcTime


class PopForecast(ImmutableRecord):
    revision: str
    catalog_fingerprint: str
    status: Literal["ready", "disabled", "unavailable", "indeterminate"]
    reason: str | None = None
    transitions: tuple[PopTransition, ...] = ()


class PopObservation(ImmutableRecord):
    ip: str | None
    entry: GroundEntryPoint | None
    status: Literal["known", "unknown"]
    source: Literal["live", "simulation"]
    sampled_at: str | None = None
    lookup_at: str | None = None
    freshness: Literal["fresh", "stale", "unknown"] = "unknown"


class PopOccurrence(ImmutableRecord):
    transition_id: str
    disposition: Literal["pending", "observed", "superseded", "unconfirmed"]
    expected_utc: UtcTime
    window_start_utc: UtcTime
    window_end_utc: UtcTime
    from_city: str | None = None
    to_city: str | None = None
    observed_at: UtcTime | None = None
    timing_residual_seconds: float | None = None


class PopLiveState(ImmutableRecord):
    revision: str
    completed_ids: frozenset[str] = frozenset()
    overdue_ids: frozenset[str] = frozenset()
    tracked_transitions: tuple[PopTransition, ...] = ()
    superseded_ids: frozenset[str] = frozenset()
    unconfirmed_ids: frozenset[str] = frozenset()
    last_observed_pop_id: str | None = None
    occurrences: tuple[PopOccurrence, ...] = ()


class PopLiveAdvisory(ImmutableRecord):
    kind: Literal["window", "overdue", "mismatch", "observation_unknown"]
    transition_id: str | None = None
    observed_pop_id: str | None = None
