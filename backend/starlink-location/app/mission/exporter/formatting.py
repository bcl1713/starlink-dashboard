"""Timeline export formatting utilities.

Pure functions for formatting timestamps, time intervals, and metric names
without dependencies on managers or visualization components.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.mission.models import MissionLegTimeline

EASTERN_TZ = ZoneInfo("America/New_York")


def ensure_timezone(value: datetime) -> datetime:
    """Return a timezone-aware UTC datetime.

    Args:
        value: A datetime object (with or without timezone info)

    Returns:
        A timezone-aware UTC datetime
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def mission_start_timestamp(timeline: MissionLegTimeline) -> datetime:
    """Infer the mission's zero point for T+ offsets.

    Uses the earliest segment start time, or the timeline creation time if
    no segments exist.

    Args:
        timeline: The mission leg timeline

    Returns:
        The mission start timestamp in UTC
    """
    if timeline.segments:
        earliest = min(ensure_timezone(seg.start_time) for seg in timeline.segments)
        return earliest
    return ensure_timezone(timeline.created_at)


def format_utc(dt: datetime) -> str:
    """Return UTC string without seconds (timezone suffix indicates Z).

    Example: "2025-12-03 14:30Z"

    Args:
        dt: A datetime object

    Returns:
        UTC-formatted string
    """
    return ensure_timezone(dt).strftime("%Y-%m-%d %H:%MZ")


def format_eastern(dt: datetime) -> str:
    """Return Eastern time with timezone abbreviation (DST-aware).

    Example: "2025-12-03 09:30EST" or "2025-12-03 09:30EDT"

    Args:
        dt: A datetime object

    Returns:
        Eastern-formatted string with DST abbreviation
    """
    eastern = ensure_timezone(dt).astimezone(EASTERN_TZ)
    return eastern.strftime("%Y-%m-%d %H:%M%Z")


def format_offset(delta: timedelta) -> str:
    """Format timedelta as T+/-HH:MM.

    Example: "T+02:30" or "T-00:15"

    Args:
        delta: A timedelta object

    Returns:
        Formatted offset string relative to mission start
    """
    total_minutes = int(delta.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    hours, minutes = divmod(total_minutes, 60)
    return f"T{sign}{hours:02d}:{minutes:02d}"


def format_seconds_hms(value: float | int) -> str:
    """Format seconds as human-readable HH:MM:SS, handling negative values.

    Args:
        value: Number of seconds (can be negative)

    Returns:
        Formatted duration string (e.g., "02:30:45" or "-01:15:30")
    """
    total_seconds = int(round(value))
    sign = "-" if total_seconds < 0 else ""
    total_seconds = abs(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}"


def compose_time_block(
    moment: datetime,
    mission_start: datetime,
) -> str:
    """Compose a three-line time representation (UTC / Eastern / T+offset).

    Args:
        moment: The timestamp to format
        mission_start: The mission start time for T+ calculation

    Returns:
        Three-line time block as formatted string
    """
    utc_str = format_utc(moment)
    eastern_str = format_eastern(moment)
    offset = moment - mission_start
    offset_str = format_offset(offset)
    return f"{utc_str}\n{eastern_str}\n{offset_str}"


def humanize_metric_name(key: str) -> str:
    """Convert snake_case metric name to readable Title Case.

    Handles special case for "seconds" suffix to avoid redundancy.
    Example: "latency_ms" -> "Latency Ms", "tcp_duration_seconds" -> "Tcp Duration"

    Args:
        key: Snake_case metric name

    Returns:
        Title-cased metric name
    """
    label = key.replace("_", " ").strip()
    if key.endswith("seconds"):
        label = label[: -len("seconds")].strip()
        if not label.lower().endswith("duration"):
            label = f"{label} duration"
    label = label.title()
    return label or key
