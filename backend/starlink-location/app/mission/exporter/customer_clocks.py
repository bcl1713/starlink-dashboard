"""Compact display clocks; UTC geometry and canonical clocks stay exact."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .briefing_clocks import EASTERN, ensure_utc


@dataclass(frozen=True)
class CustomerRange:
    start: str
    end: str
    approximate: bool


def format_customer_range(
    start: datetime,
    end: datetime,
    departure: datetime,
    *,
    second_precision: bool = False
) -> CustomerRange:
    a, b, origin = map(ensure_utc, (start, end, departure))
    if b <= a:
        raise ValueError("Customer range end must follow start")
    seconds = second_precision or (b - a).total_seconds() < 60
    unit = 1 if seconds else 60

    def floor(value):
        return value.replace(microsecond=0) - timedelta(
            seconds=0 if seconds else value.second
        )

    low, high = floor(a), floor(b)
    if high != b:
        high += timedelta(seconds=unit)
    local_a, local_b = low.astimezone(EASTERN), high.astimezone(EASTERN)
    dates = (
        local_a.date() != local_b.date()
        or local_a.date() != origin.astimezone(EASTERN).date()
    )

    # Fold boundaries need explicit timezone identity on both ends.
    def ambiguous(value):
        return value.utcoffset() != value.replace(fold=1 - value.fold).utcoffset()

    offsets = local_a.utcoffset() != local_b.utcoffset() or any(
        ambiguous(value) for value in (local_a, local_b)
    )
    pattern = ("%d %b " if dates else "") + "%H:%M" + (":%S" if seconds else "")

    def label(value):
        suffix = value.tzname() if offsets else "ET"
        return value.strftime(pattern) + " " + suffix

    return CustomerRange(label(local_a), label(local_b), low != a or high != b)
