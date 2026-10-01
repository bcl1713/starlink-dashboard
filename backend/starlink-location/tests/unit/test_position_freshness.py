"""Position age is independent of request and network collection time."""

from datetime import datetime, timedelta, timezone

import pytest

from app.services.position_freshness import position_observation

NOW = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (0, "fresh"),
        (-9.999, "fresh"),
        (-10, "stale"),
        (5, "fresh"),
        (5.001, "unavailable"),
    ],
)
def test_position_age_boundaries(offset, expected):
    observed = NOW + timedelta(seconds=offset)
    timestamp, state = position_observation(0.0, 0.0, observed, NOW)
    assert state == expected
    assert timestamp == (None if expected == "unavailable" else observed)


@pytest.mark.parametrize(
    ("latitude", "longitude", "observed"),
    [
        (None, 0, NOW),
        (True, 0, NOW),
        (float("nan"), 0, NOW),
        (91, 0, NOW),
        (0, 181, NOW),
        (0, 0, None),
        (0, 0, NOW.replace(tzinfo=None)),
    ],
)
def test_unverified_position_fails_closed(latitude, longitude, observed):
    assert position_observation(latitude, longitude, observed, NOW) == (
        None,
        "unavailable",
    )
