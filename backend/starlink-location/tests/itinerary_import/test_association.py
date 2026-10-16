"""Route association must tolerate source precision without guessing occurrences."""

from datetime import datetime, timedelta, timezone

import pytest

from app.mission.planning.models import ExpectedLeg
from app.models.route import (
    ParsedRoute,
    RouteMetadata,
    RouteTimingProfile,
    RouteWaypoint,
)

START = datetime(2035, 1, 1, 10, tzinfo=timezone.utc)


def leg(id="one", start=START, duration=120, departure="AAAA", arrival="BBBB"):
    return ExpectedLeg(
        id=id,
        ordinal=1,
        departure_airport=departure,
        arrival_airport=arrival,
        departure_time=start,
        arrival_time=start + timedelta(minutes=duration),
    )


def route(start=START, duration=120, departure="AAAA", arrival="BBBB"):
    return ParsedRoute(
        metadata=RouteMetadata(
            name="Invented", file_path="invented.kml", point_count=0
        ),
        points=[],
        waypoints=[
            RouteWaypoint(name=n, latitude=0, longitude=i, order=i, role=role)
            for i, (n, role) in enumerate(
                [(departure, "departure"), (arrival, "arrival")]
            )
        ],
        timing_profile=RouteTimingProfile(
            departure_time=start,
            arrival_time=start + timedelta(minutes=duration),
            has_timing_data=True,
        ),
    )


def associate(legs, routes):
    from app.mission.itinerary_import.association import associate_routes

    return associate_routes(legs, routes)


@pytest.mark.parametrize("seconds", [0, 42, -60, 60, 119])
def test_second_precision_is_not_a_discrepancy(seconds):
    r = route(START + timedelta(seconds=seconds))
    result = associate([leg()], {"kml": r})
    assert result.assignments == {"one": "kml"}
    assert result.issues == []
    assert r.timing_profile.departure_time == START + timedelta(seconds=seconds)


def test_larger_shift_with_unique_endpoints_and_changed_duration():
    result = associate(
        [leg()], {"kml": route(START + timedelta(hours=3), duration=135)}
    )
    assert result.assignments == {"one": "kml"}
    assert result.evidence["one"]["departure_offset_seconds"] == 10800


def test_midnight_dates_and_shuffled_files():
    late = START.replace(hour=23)
    legs = [leg("a", late), leg("b", late + timedelta(days=1))]
    routes = {
        "next": route(late + timedelta(days=1, seconds=31)),
        "first": route(late + timedelta(seconds=42)),
    }
    assert associate(legs, routes).assignments == {"a": "first", "b": "next"}
    assert associate(legs, dict(reversed(list(routes.items())))).assignments == {
        "a": "first",
        "b": "next",
    }


def test_repeated_routes_do_not_choose_by_order_or_nearest_shift():
    legs = [leg("a"), leg("b", START + timedelta(hours=4))]
    routes = {
        "x": route(START + timedelta(hours=2)),
        "y": route(START + timedelta(hours=3)),
    }
    for choices in (routes, dict(reversed(list(routes.items())))):
        result = associate(legs, choices)
        assert result.assignments == {}
        assert {issue.leg_id for issue in result.issues} == {"a", "b"}


@pytest.mark.parametrize("change", ["date", "endpoints", "missing"])
def test_contradictory_or_missing_evidence_is_unresolved(change):
    r = route(START + timedelta(days=5) if change == "date" else START)
    if change == "endpoints":
        r.waypoints[-1].name = "CCCC"
    if change == "missing":
        r.timing_profile = None
    result = associate([leg()], {"kml": r})
    assert result.assignments == {}
    assert result.issues


def test_unassigned_extra_file_is_reported():
    result = associate([leg()], {"one": route(), "extra": route(departure="CCCC")})
    assert result.assignments == {"one": "one"}
    assert any(issue.code == "unassigned_route" for issue in result.issues)


def test_unique_route_shift_across_midnight_uses_endpoint_evidence():
    source = leg(start=START.replace(hour=23, minute=58))
    r = route(source.departure_time + timedelta(minutes=5))
    result = associate([source], {"route": r})
    assert result.assignments == {source.id: "route"}
    assert result.issues == []
