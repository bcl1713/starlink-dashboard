"""Validate the provenance of the exact position used for route estimates."""

from datetime import datetime, timezone
from math import isfinite

from app.models.telemetry import PositionState


def valid_coordinate(value: object, limit: float) -> bool:
    """Accept finite numeric coordinates, including genuine zero."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
        and -limit <= value <= limit
    )


def position_observation(
    latitude: object, longitude: object, observed_at: object, now: datetime
) -> tuple[datetime | None, PositionState]:
    """Classify same-sample collection age; unknown provenance fails closed."""
    if not valid_coordinate(latitude, 90) or not valid_coordinate(longitude, 180):
        return None, "unavailable"
    return observation_time(observed_at, now)


def observation_time(
    observed_at: object, now: datetime
) -> tuple[datetime | None, PositionState]:
    """Classify a verified observation timestamp without renewing its age."""
    if not isinstance(observed_at, datetime) or observed_at.utcoffset() is None:
        return None, "unavailable"
    observed_at = observed_at.astimezone(timezone.utc)
    age = (now - observed_at).total_seconds()
    if age < -5:
        return None, "unavailable"
    return observed_at, "stale" if age >= 10 else "fresh"


def speed_is_fresh(speed: object, observed_at: object, now: datetime) -> bool:
    """Require a verified speed observation, allowing measured stationary zero."""
    return (
        isinstance(speed, (int, float))
        and not isinstance(speed, bool)
        and isfinite(speed)
        and speed >= 0
        and observation_time(observed_at, now)[1] == "fresh"
    )
