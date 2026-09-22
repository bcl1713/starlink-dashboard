"""Integration tests for the Overview upcoming-POI API and ETA source."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.mission.dependencies import get_poi_manager, get_route_manager
from app.models.poi import POI
from app.models.route import (
    ParsedRoute,
    RouteMetadata,
    RoutePoint,
    RouteTimingProfile,
    RouteWaypoint,
)
from app.services.eta_calculator import ETACalculator
from app.services.overview_upcoming_pois import calculate_route_aware_eta_results


NOW = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)


def route(points: list[tuple[float, float]]) -> ParsedRoute:
    return ParsedRoute(
        metadata=RouteMetadata(
            name="Test route",
            file_path="routes/test-route.kml",
            point_count=len(points),
        ),
        points=[
            RoutePoint(
                latitude=latitude,
                longitude=longitude,
                sequence=index,
                expected_segment_speed_knots=300,
            )
            for index, (latitude, longitude) in enumerate(points)
        ],
        waypoints=[
            RouteWaypoint(
                name="X transition",
                latitude=points[-1][0],
                longitude=points[-1][1],
                order=1,
                expected_arrival_time=NOW + timedelta(minutes=5),
            )
        ],
        timing_profile=RouteTimingProfile(
            departure_time=NOW - timedelta(hours=1),
            arrival_time=NOW + timedelta(minutes=5),
            has_timing_data=True,
        ),
    )


def scheduled_poi() -> POI:
    return POI(
        id="x-transition",
        name="X transition",
        kind="x_band_transition",
        latitude=40.0,
        longitude=-71.0,
        projected_route_progress=100,
        expected_arrival_time=NOW - timedelta(minutes=30),
    )


def test_in_flight_eta_is_late_schedule_independent_and_uses_current_speed():
    active_route = route([(40.0, -73.0), (40.0, -72.0), (40.0, -71.0)])
    poi = scheduled_poi()
    calculator = ETACalculator()

    slow = calculate_route_aware_eta_results(
        pois=[poi],
        calculator=calculator,
        active_route=active_route,
        flight_phase="in_flight",
        latitude=40.0,
        longitude=-73.0,
        speed_knots=100,
    )
    late_schedule = poi.model_copy(
        update={"expected_arrival_time": NOW - timedelta(hours=4)}
    )
    slow_with_different_schedule = calculate_route_aware_eta_results(
        pois=[late_schedule],
        calculator=calculator,
        active_route=active_route,
        flight_phase="in_flight",
        latitude=40.0,
        longitude=-73.0,
        speed_knots=100,
    )
    fast = calculate_route_aware_eta_results(
        pois=[poi],
        calculator=calculator,
        active_route=active_route,
        flight_phase="in_flight",
        latitude=40.0,
        longitude=-73.0,
        speed_knots=500,
    )

    assert slow[poi.id] == slow_with_different_schedule[poi.id]
    assert slow[poi.id] != fast[poi.id]
    assert slow[poi.id] > 0


def test_in_flight_eta_changes_when_active_route_geometry_changes():
    poi = scheduled_poi()
    calculator = ETACalculator()
    short_route = route([(40.0, -73.0), (40.0, -71.0)])
    long_route = route([(40.0, -73.0), (40.0, -72.0), (40.0, -71.0)])

    short_eta = calculate_route_aware_eta_results(
        pois=[poi],
        calculator=calculator,
        active_route=short_route,
        flight_phase="in_flight",
        latitude=40.0,
        longitude=-73.0,
        speed_knots=300,
    )
    long_eta = calculate_route_aware_eta_results(
        pois=[poi],
        calculator=calculator,
        active_route=long_route,
        flight_phase="in_flight",
        latitude=40.0,
        longitude=-73.0,
        speed_knots=300,
    )

    assert short_eta[poi.id] != long_eta[poi.id]
    assert short_eta[poi.id] < long_eta[poi.id]


def test_api_returns_no_active_route_without_fabricating_records(client):
    response = client.get("/api/overview/upcoming-pois")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "no_active_route"
    assert payload["pois"] == []
    assert payload["calculated_at"].endswith("+00:00")


def test_api_uses_active_route_telemetry_without_endpoint_defaults(
    client, monkeypatch
):
    import app.api.overview_upcoming_pois as overview_api

    active_route = route([(40.0, -73.0), (40.0, -72.0), (40.0, -71.0)])
    generated_poi = scheduled_poi()
    coordinator = SimpleNamespace(
        get_current_telemetry=lambda: SimpleNamespace(
            position=SimpleNamespace(latitude=40.0, longitude=-73.0, speed=200)
        )
    )
    client.app.state.coordinator = coordinator
    client.app.dependency_overrides[get_route_manager] = lambda: SimpleNamespace(
        get_active_route=lambda: active_route
    )
    client.app.dependency_overrides[get_poi_manager] = lambda: SimpleNamespace(
        list_pois=lambda mission_id=None: [generated_poi]
    )
    monkeypatch.setattr(overview_api, "get_active_mission_id", lambda: "mission-1")
    monkeypatch.setattr(
        overview_api,
        "get_flight_state_manager",
        lambda: SimpleNamespace(get_status=lambda: SimpleNamespace(phase=SimpleNamespace(value="in_flight"))),
    )

    response = client.get("/api/overview/upcoming-pois")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["state"] == "available"
    assert payload["pois"][0]["eta_type"] == "estimated"
    assert payload["pois"][0]["eta_seconds"] > 0
    assert payload["pois"][0]["expected_arrival_time"] != payload["pois"][0]["estimated_arrival_time"]
    client.app.dependency_overrides.clear()
    del client.app.state.coordinator
