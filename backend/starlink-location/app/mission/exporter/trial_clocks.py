"""Exact customer clocks, with elapsed arithmetic on UTC instants."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class ClockLabels:
    et: str
    zulu: str
    relative: str


def ensure_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("Trial clocks require a timezone-aware timestamp")
    return timestamp.astimezone(timezone.utc)


def _seconds(seconds: int, microseconds: int) -> str:
    if microseconds:
        return f":{seconds:02d}.{microseconds:06d}".rstrip("0")
    return f":{seconds:02d}" if seconds else ""


def _absolute(timestamp: datetime) -> str:
    return timestamp.strftime("%Y-%m-%d %H:%M") + _seconds(
        timestamp.second, timestamp.microsecond
    )


def format_clocks(timestamp: datetime, takeoff: datetime) -> ClockLabels:
    """Always include dates and EST/EDT; retain seconds only when needed."""
    instant, origin = ensure_utc(timestamp), ensure_utc(takeoff)
    elapsed = instant - origin
    sign = "+" if elapsed >= timedelta(0) else "-"
    elapsed = abs(elapsed)
    hours, remainder = divmod(elapsed.days * 86400 + elapsed.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    relative = f"T{sign}{hours:02d}:{minutes:02d}" + _seconds(
        seconds, elapsed.microseconds
    )
    local = instant.astimezone(EASTERN)
    return ClockLabels(
        et=f"{_absolute(local)} {local.tzname()}",
        zulu=f"{_absolute(instant)}Z",
        relative=relative,
    )
