"""Unit tests for truthful Overview upcoming-POI projection."""

from datetime import datetime, timedelta, timezone

from app.models.poi import POI
from app.services.overview_upcoming_pois import project_overview_upcoming_pois


NOW = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)


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
    assert [poi.kind for poi in response.pois if poi.map_retained] == [
        "departure",
        "x_band_transition",
        "arrival",
    ]


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
