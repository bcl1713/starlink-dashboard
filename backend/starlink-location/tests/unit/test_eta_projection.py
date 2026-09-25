"""Unit tests for anticipated route-aware ETA projection."""

from datetime import datetime, timezone

import pytest

from app.models.poi import POI
from app.models.route import (
    ParsedRoute,
    RouteMetadata,
    RoutePoint,
    RouteTimingProfile,
    RouteWaypoint,
)
from app.services.eta.calculator import ETACalculator
from app.services.eta.projection import ETAProjection
import app.services.eta.projection as projection_module


class frozen_datetime(datetime):
    """Datetime replacement with a fixed UTC clock for projection tests."""

    frozen_time: datetime

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls.frozen_time.replace(tzinfo=None)
        return cls.frozen_time.astimezone(tz)


def freeze_datetime(value: str) -> type[frozen_datetime]:
    """Return a datetime replacement frozen at the supplied ISO-8601 UTC time."""
    frozen = datetime.fromisoformat(value.replace("Z", "+00:00"))

    class FrozenDateTime(frozen_datetime):
        frozen_time = frozen

    return FrozenDateTime


@pytest.fixture
def calculator():
    """Create the projection under test with its base ETA calculator."""
    return ETAProjection(ETACalculator())


@pytest.fixture
def route_with_timing():
    """Create a route departing at noon with a timed waypoint at 12:30 UTC."""
    departure_time = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)
    return ParsedRoute(
        metadata=RouteMetadata(
            name="Timed route",
            description="",
            file_path="routes/timed-route.kml",
            imported_at=departure_time,
            point_count=1,
        ),
        points=[RoutePoint(latitude=40.0, longitude=-73.0, sequence=0)],
        waypoints=[
            RouteWaypoint(
                name="Timed POI",
                latitude=40.0,
                longitude=-73.0,
                order=0,
                expected_arrival_time=datetime(2026, 9, 25, 12, 30, tzinfo=timezone.utc),
            )
        ],
        timing_profile=RouteTimingProfile(
            departure_time=departure_time,
            has_timing_data=True,
        ),
    )


@pytest.fixture
def timed_poi():
    """Create a POI that matches the timed route waypoint by name."""
    return POI(id="timed-poi", name="Timed POI", latitude=40.0, longitude=-73.0)


def test_anticipated_eta_before_expected_departure_uses_calendar_delta(
    monkeypatch, calculator, route_with_timing, timed_poi
):
    monkeypatch.setattr(
        projection_module, "datetime", freeze_datetime("2026-09-25T11:45:00Z")
    )

    assert calculator._calculate_route_aware_eta_anticipated(
        40.0, -73.0, timed_poi, route_with_timing
    ) == 45 * 60


def test_anticipated_eta_after_missed_departure_reanchors_planned_duration_at_now(
    monkeypatch, calculator, route_with_timing, timed_poi
):
    monkeypatch.setattr(
        projection_module, "datetime", freeze_datetime("2026-09-25T13:00:00Z")
    )

    assert calculator._calculate_route_aware_eta_anticipated(
        40.0, -73.0, timed_poi, route_with_timing
    ) == 30 * 60


def test_anticipated_eta_after_missed_departure_reanchors_projected_waypoint(
    monkeypatch, calculator, route_with_timing
):
    monkeypatch.setattr(
        projection_module, "datetime", freeze_datetime("2026-09-25T13:00:00Z")
    )
    projected_poi = POI(
        id="projected-poi",
        name="Projected POI",
        latitude=40.0,
        longitude=-73.0,
        projected_waypoint_index=0,
    )

    assert calculator._calculate_route_aware_eta_anticipated(
        40.0, -73.0, projected_poi, route_with_timing
    ) == 30 * 60


def test_anticipated_eta_returns_none_for_matched_waypoint_without_timing(
    calculator, route_with_timing, timed_poi
):
    route_with_timing.waypoints[0].expected_arrival_time = None

    assert (
        calculator._calculate_route_aware_eta_anticipated(
            40.0, -73.0, timed_poi, route_with_timing
        )
        is None
    )
