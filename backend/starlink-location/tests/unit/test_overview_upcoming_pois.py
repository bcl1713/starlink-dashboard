"""Unit tests for truthful Overview upcoming-POI projection."""

from datetime import datetime, timedelta, timezone
from typing import get_args

from app.models.overview_upcoming_pois import OverviewUpcomingPoisState
from app.models.poi import POI
from app.services.overview_upcoming_pois import project_overview_upcoming_pois

NOW = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)


def test_overview_response_exposes_only_the_v2_context_states():
    assert set(get_args(OverviewUpcomingPoisState)) == {
        "available",
        "no_active_mission",
        "route_unavailable",
        "inconsistent_active_mission",
        "no_generated_pois",
        "no_upcoming_pois",
        "unavailable",
    }


def poi(
    name: str,
    kind: str,
    progress: float,
    *,
    expected_arrival_time: datetime | None = None,
) -> POI:
    return POI(
        id=name.lower().replace(" ", "-"),
        name=name,
        kind=kind,
        latitude=40.0,
        longitude=-73.0,
        projected_route_progress=progress,
        expected_arrival_time=expected_arrival_time,
    )


def test_in_flight_projection_keeps_departure_and_arrival_on_map_but_not_table():
    response = project_overview_upcoming_pois(
        pois=[
            poi("Departure", "departure", 0),
            poi("X transition", "x_band_transition", 20),
            poi("Ka exit", "ka_coverage_exit", 30),
            poi("Arrival", "arrival", 100),
        ],
        eta_results={
            "departure": -60,
            "x-transition": -20 * 60,
            "ka-exit": -61 * 60,
            "arrival": 30 * 60,
        },
        flight_phase="in_flight",
        current_progress=50,
        calculated_at=NOW,
    )

    assert [poi.kind for poi in response.pois if poi.upcoming] == ["arrival"]
    assert {poi.kind for poi in response.pois if poi.map_retained} == {
        "departure",
        "x_band_transition",
        "arrival",
    }


def test_upcoming_order_places_untimed_route_order_after_timed_entries():
    response = project_overview_upcoming_pois(
        pois=[
            poi("A", "x_band_transition", 20),
            poi("B", "ka_coverage_exit", 30),
            poi("C", "ka_coverage_entry", 40),
        ],
        eta_results={"a": 60, "b": None, "c": 30},
        flight_phase="in_flight",
        current_progress=0,
        calculated_at=NOW,
    )

    assert [poi.name for poi in response.top_five] == ["C", "A", "B"]


def test_projection_orders_dynamic_estimates_before_untimed_route_order():
    response = project_overview_upcoming_pois(
        pois=[
            poi("Untimed first", "x_band_transition", 70),
            poi("Two hours", "ka_coverage_exit", 60),
            poi("Thirty five", "ka_coverage_entry", 50),
            poi("Ten", "aar_start", 40),
            poi("Forty five", "ka_transition", 30),
            poi("Untimed second", "arrival", 80),
            poi("Twenty", "x_band_transition", 20),
        ],
        eta_results={
            "untimed-first": None,
            "two-hours": 120 * 60,
            "thirty-five": 35 * 60,
            "ten": 10 * 60,
            "forty-five": 45 * 60,
            "untimed-second": None,
            "twenty": 20 * 60,
        },
        flight_phase="in_flight",
        current_progress=0,
        calculated_at=NOW,
    )

    assert [poi.name for poi in response.pois if poi.upcoming] == [
        "Ten",
        "Twenty",
        "Thirty five",
        "Forty five",
        "Two hours",
        "Untimed first",
        "Untimed second",
    ]


def test_in_flight_projection_uses_live_eta_not_scheduled_arrival():
    response = project_overview_upcoming_pois(
        pois=[
            poi(
                "X transition",
                "x_band_transition",
                30,
                expected_arrival_time=NOW + timedelta(minutes=5),
            )
        ],
        eta_results={"x-transition": 90 * 60},
        flight_phase="in_flight",
        current_progress=0,
        calculated_at=NOW,
    )

    projected = response.pois[0]
    assert projected.expected_arrival_time == NOW + timedelta(minutes=5)
    assert projected.eta_seconds == 90 * 60
    assert projected.estimated_arrival_time == NOW + timedelta(minutes=90)
    assert projected.eta_type == "estimated"
    assert projected.upcoming is True


def test_in_flight_retention_uses_dynamic_eta_not_scheduled_arrival():
    response = project_overview_upcoming_pois(
        pois=[
            poi(
                "X transition",
                "x_band_transition",
                20,
                expected_arrival_time=NOW - timedelta(hours=3),
            )
        ],
        eta_results={"x-transition": -30 * 60},
        flight_phase="in_flight",
        current_progress=50,
        calculated_at=NOW,
    )

    assert response.pois[0].map_retained is True


def test_in_flight_ahead_poi_is_upcoming_even_when_estimated_eta_is_negative():
    response = project_overview_upcoming_pois(
        pois=[poi("Ahead", "x_band_transition", 70)],
        eta_results={"ahead": -1.0},
        flight_phase="in_flight",
        current_progress=50,
        calculated_at=NOW,
    )

    assert response.state == "available"
    assert response.pois[0].upcoming is True


def test_in_flight_behind_poi_is_not_upcoming_even_with_positive_eta():
    response = project_overview_upcoming_pois(
        pois=[poi("Behind", "x_band_transition", 20)],
        eta_results={"behind": 60.0},
        flight_phase="in_flight",
        current_progress=50,
        calculated_at=NOW,
    )

    assert response.state == "no_upcoming_pois"
    assert response.pois[0].upcoming is False


def test_in_flight_poi_at_current_route_position_is_not_upcoming():
    response = project_overview_upcoming_pois(
        pois=[poi("Current", "x_band_transition", 50)],
        eta_results={"current": 60.0},
        flight_phase="in_flight",
        current_progress=50,
        calculated_at=NOW,
    )

    assert response.state == "no_upcoming_pois"
    assert response.pois[0].upcoming is False


def test_anticipated_historical_pois_are_available_in_route_order():
    response = project_overview_upcoming_pois(
        pois=[
            poi("Later on route", "x_band_transition", 70),
            poi("Earlier on route", "ka_coverage_exit", 30),
        ],
        eta_results={"later-on-route": -60.0, "earlier-on-route": -3600.0},
        flight_phase="pre_departure",
        current_progress=0,
        calculated_at=NOW,
    )

    assert response.state == "available"
    assert [projected.name for projected in response.pois if projected.upcoming] == [
        "Earlier on route",
        "Later on route",
    ]


def test_post_arrival_pois_are_not_upcoming():
    response = project_overview_upcoming_pois(
        pois=[poi("Destination", "arrival", 100)],
        eta_results={"destination": 60.0},
        flight_phase="post_arrival",
        current_progress=100,
        calculated_at=NOW,
    )

    assert response.state == "no_upcoming_pois"
    assert response.pois[0].upcoming is False
