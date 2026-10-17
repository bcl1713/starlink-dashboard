"""UTC timestamps and actual/planned intervals, independent of acceptance time."""

import re
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from pydantic import BeforeValidator, PlainSerializer, model_validator

from .clock import Clock
from .common import StrictModel
from .errors import OperatorError


def utc_timestamp(value: object) -> datetime:
    if isinstance(value, str):
        if not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})",
            value,
        ):
            raise ValueError("Expected an aware RFC 3339 timestamp")
        value = datetime.fromisoformat(value.upper().replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("Expected an aware RFC 3339 timestamp")
    return value.astimezone(timezone.utc)


UtcTimestamp = Annotated[
    datetime,
    BeforeValidator(utc_timestamp),
    PlainSerializer(
        lambda value: value.isoformat(timespec="microseconds").replace("+00:00", "Z"),
        return_type=str,
        when_used="json",
    ),
]


class RecordTime(StrictModel):
    occurred_at: UtcTimestamp | None = None
    ended_at: UtcTimestamp | None = None
    precision: Literal["exact", "approximate", "unknown"] = "unknown"
    end_state: Literal["instant", "ongoing", "known", "unknown"] = "unknown"
    planned_start_at: UtcTimestamp | None = None
    planned_end_at: UtcTimestamp | None = None

    @model_validator(mode="after")
    def valid_intervals(self):
        if self.precision == "unknown" and (
            self.occurred_at is not None
            or self.ended_at is not None
            or self.end_state != "unknown"
        ):
            raise ValueError(
                "Unknown precision requires null actual times and unknown end"
            )
        if self.precision != "unknown" and self.occurred_at is None:
            raise ValueError("Known precision requires an actual start")
        if self.end_state == "known":
            if self.occurred_at is None or self.ended_at is None:
                raise ValueError("Known end requires actual start and end")
        elif self.end_state in ("instant", "ongoing"):
            if self.occurred_at is None or self.ended_at is not None:
                raise ValueError("Instant/ongoing requires actual start and null end")
        elif self.ended_at is not None:
            raise ValueError("Unknown end requires a null actual end")
        for start, end in (
            (self.occurred_at, self.ended_at),
            (self.planned_start_at, self.planned_end_at),
        ):
            if end is not None and (start is None or end < start):
                raise ValueError("End requires a start and cannot precede it")
        return self

    def validate_for_acceptance(self, clock: Clock) -> None:
        latest = utc_timestamp(clock.now()) + timedelta(seconds=60)
        fields = {
            f"time.{name}": "Actual time exceeds the acceptance clock tolerance"
            for name in ("occurred_at", "ended_at")
            if (value := getattr(self, name)) is not None and value > latest
        }
        if fields:
            raise OperatorError("validation_error", fields=fields)
