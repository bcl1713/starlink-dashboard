"""Strict timing-only evidence; internal point arrays never cross the wire."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from app.models.aviation_weather import Contract, Hash, Time

Status = Literal["overlap", "no-overlap", "unknown"]
Reason = Literal[
    "missing-timing", "invalid-timing", "ambiguous-association", "unavailable-plan"
]


class EncounterPlanSummary(Contract):
    revision: Hash
    method: Literal["segment-linear-utc-v1"] = "segment-linear-utc-v1"
    source: Literal["ordinary", "simulation"]
    source_revision: Annotated[str, Field(max_length=256)] | None
    precision: Literal["minute", "second", "unknown"] = "unknown"


class EncounterPlan(EncounterPlanSummary):
    context_key: Hash
    times_ms: tuple[Time | None, ...] = Field(max_length=20000)
    reasons: tuple[Reason | None, ...] = Field(max_length=20000)

    @model_validator(mode="after")
    def aligned(self) -> Self:
        if len(self.times_ms) != len(self.reasons) or any(
            (time is None) != (reason is not None)
            for time, reason in zip(self.times_ms, self.reasons)
        ):
            raise ValueError("Invalid plan evidence alignment")
        return self


class PassageEvidence(Contract):
    entry_ms: Time | None
    exit_ms: Time | None
    status: Status
    reason: Reason | None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.status == "unknown":
            if (
                self.entry_ms is not None
                or self.exit_ms is not None
                or self.reason is None
            ):
                raise ValueError("Unknown passage requires a reason and no times")
        elif (
            self.entry_ms is None
            or self.exit_ms is None
            or self.entry_ms > self.exit_ms
            or self.reason is not None
        ):
            raise ValueError("Known passage requires ordered times and no reason")
        return self


class EncounterEvidence(Contract):
    spans: list[PassageEvidence] = Field(min_length=1, max_length=100000)
    status: Status
    unknown_count: Time
    reason: Reason | None

    @model_validator(mode="after")
    def aggregate(self) -> Self:
        unknown = sum(s.status == "unknown" for s in self.spans)
        status = (
            "overlap"
            if any(s.status == "overlap" for s in self.spans)
            else "unknown" if unknown else "no-overlap"
        )
        reason = (
            next((s.reason for s in self.spans if s.reason), None)
            if status == "unknown"
            else None
        )
        if (
            self.status != status
            or self.unknown_count != unknown
            or self.reason != reason
        ):
            raise ValueError("Inconsistent passage aggregate")
        return self
