"""Mission validation utilities."""

from datetime import datetime, timezone

# Warning threshold in minutes (±8 hours)
LARGE_OFFSET_THRESHOLD_MINUTES = 480


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


def validate_adjusted_departure_time(
    adjusted: datetime, original: datetime
) -> list[str]:
    """Validate adjusted departure time and return any warnings.

    Calculates the offset between adjusted and original departure times and
    returns a warning if the offset exceeds ±8 hours. This function does NOT
    raise exceptions - warnings are informational only.

    Args:
        adjusted: The requested adjusted departure time
        original: The original departure time from the KML route

    Returns:
        List of warning messages (empty if no warnings)
    """
    warnings = []

    # Ensure both datetimes are timezone-aware for proper comparison
    adjusted = ensure_timezone(adjusted)
    original = ensure_timezone(original)

    offset_seconds = (adjusted - original).total_seconds()
    offset_minutes = offset_seconds / 60.0
    offset_hours = offset_minutes / 60.0

    # Check if offset exceeds threshold
    if abs(offset_minutes) > LARGE_OFFSET_THRESHOLD_MINUTES:
        direction = "earlier" if offset_minutes < 0 else "later"
        hours_abs = abs(offset_hours)
        warnings.append(
            f"Large time shift detected: {hours_abs:.1f} hours {direction}. "
            "Consider requesting new route from flight planners."
        )

    return warnings
