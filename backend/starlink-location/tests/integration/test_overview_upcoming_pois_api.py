"""Integration tests for the Overview upcoming-POI API and ETA source."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from app.mission.dependencies import get_poi_manager, get_route_manager
from app.mission.timeline_builder.pois import MISSION_EVENT_CATEGORY
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


@pytest.fixture(autouse=True)
def reset_overview_api_overrides(client):
    """Prevent endpoint dependency overrides from leaking into later API tests."""
    yield
    client.app.dependency_overrides.clear()
    if hasattr(client.app.state, "coordinator"):
        del client.app.state.coordinator


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
        category=MISSION_EVENT_CATEGORY,
        generated_source="mission-timeline",
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


def test_api_uses_active_route_telemetry_without_endpoint_defaults(client, monkeypatch):
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
        lambda: SimpleNamespace(
            get_status=lambda: SimpleNamespace(phase=SimpleNamespace(value="in_flight"))
        ),
    )

    response = client.get("/api/overview/upcoming-pois")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["state"] == "available"
    assert payload["pois"][0]["eta_type"] == "estimated"
    assert payload["pois"][0]["eta_seconds"] > 0
    assert (
        payload["pois"][0]["expected_arrival_time"]
        != payload["pois"][0]["estimated_arrival_time"]
    )
    client.app.dependency_overrides.clear()
    del client.app.state.coordinator


def test_api_excludes_public_spoofed_mission_event_poi_and_keeps_timeline_generated_poi(
    client, monkeypatch
):
    import app.api.overview_upcoming_pois as overview_api

    active_route = route([(40.0, -73.0), (40.0, -71.0)])
    poi_manager = client.app.state.poi_manager
    generated_poi = scheduled_poi().model_copy(
        update={"mission_id": "mission-1", "generated_source": "mission-timeline"}
    )
    poi_manager._pois[generated_poi.id] = generated_poi
    client.app.dependency_overrides[get_route_manager] = lambda: SimpleNamespace(
        get_active_route=lambda: active_route
    )
    client.app.dependency_overrides[get_poi_manager] = lambda: poi_manager
    monkeypatch.setattr(overview_api, "get_active_mission_id", lambda: "mission-1")
    monkeypatch.setattr(
        overview_api,
        "get_flight_state_manager",
        lambda: SimpleNamespace(
            get_status=lambda: SimpleNamespace(
                phase=SimpleNamespace(value="pre_departure")
            )
        ),
    )

    spoof_response = client.post(
        "/api/pois/",
        json={
            "name": "Spoofed mission event",
            "latitude": 40.0,
            "longitude": -71.0,
            "mission_id": "mission-1",
            "category": MISSION_EVENT_CATEGORY,
            "kind": "x_band_transition",
            "expected_arrival_time": (NOW + timedelta(minutes=10)).isoformat(),
        },
    )
    response = client.get("/api/overview/upcoming-pois")

    assert spoof_response.status_code == 201, spoof_response.text
    assert response.status_code == 200, response.text
    assert [poi["poi_id"] for poi in response.json()["pois"]] == [generated_poi.id]


def test_api_returns_no_generated_pois_for_active_route_with_only_manual_typed_pois(
    client, monkeypatch
):
    import app.api.overview_upcoming_pois as overview_api

    active_route = route([(40.0, -73.0), (40.0, -71.0)])
    manual_poi = scheduled_poi().model_copy(
        update={"category": "landmark", "generated_source": None}
    )
    client.app.dependency_overrides[get_route_manager] = lambda: SimpleNamespace(
        get_active_route=lambda: active_route
    )
    client.app.dependency_overrides[get_poi_manager] = lambda: SimpleNamespace(
        list_pois=lambda mission_id=None: [manual_poi]
    )
    monkeypatch.setattr(overview_api, "get_active_mission_id", lambda: "mission-1")

    response = client.get("/api/overview/upcoming-pois")

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "no_generated_pois"
    assert response.json()["pois"] == []


def test_api_returns_unavailable_without_in_flight_telemetry(client, monkeypatch):
    import app.api.overview_upcoming_pois as overview_api

    active_route = route([(40.0, -73.0), (40.0, -71.0)])
    client.app.dependency_overrides[get_route_manager] = lambda: SimpleNamespace(
        get_active_route=lambda: active_route
    )
    client.app.dependency_overrides[get_poi_manager] = lambda: SimpleNamespace(
        list_pois=lambda mission_id=None: [scheduled_poi()]
    )
    monkeypatch.setattr(overview_api, "get_active_mission_id", lambda: "mission-1")
    monkeypatch.setattr(
        overview_api,
        "get_flight_state_manager",
        lambda: SimpleNamespace(
            get_status=lambda: SimpleNamespace(phase=SimpleNamespace(value="in_flight"))
        ),
    )
    monkeypatch.delattr(client.app.state, "coordinator", raising=False)

    response = client.get("/api/overview/upcoming-pois")

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "unavailable"
    assert response.json()["pois"] == []


def test_api_in_flight_eta_uses_fixed_telemetry_not_schedule_and_changes_for_detour_route(
    client, monkeypatch
):
    import app.api.overview_upcoming_pois as overview_api

    direct_route = route([(40.0, -73.0), (40.0, -71.0)])
    detour_route = route([(40.0, -73.0), (45.0, -80.0), (40.0, -71.0)])
    active_route = {"value": direct_route}
    poi = scheduled_poi()
    coordinator = SimpleNamespace(
        get_current_telemetry=lambda: SimpleNamespace(
            position=SimpleNamespace(latitude=40.0, longitude=-73.0, speed=200)
        )
    )
    client.app.state.coordinator = coordinator
    client.app.dependency_overrides[get_route_manager] = lambda: SimpleNamespace(
        get_active_route=lambda: active_route["value"]
    )
    client.app.dependency_overrides[get_poi_manager] = lambda: SimpleNamespace(
        list_pois=lambda mission_id=None: [poi]
    )
    monkeypatch.setattr(overview_api, "get_active_mission_id", lambda: "mission-1")
    monkeypatch.setattr(overview_api, "get_eta_calculator", ETACalculator)
    monkeypatch.setattr(
        overview_api,
        "get_flight_state_manager",
        lambda: SimpleNamespace(
            get_status=lambda: SimpleNamespace(phase=SimpleNamespace(value="in_flight"))
        ),
    )

    direct_response = client.get("/api/overview/upcoming-pois")
    direct_eta = direct_response.json()["pois"][0]["eta_seconds"]
    poi = poi.model_copy(update={"expected_arrival_time": NOW + timedelta(days=1)})
    scheduled_response = client.get("/api/overview/upcoming-pois")
    scheduled_eta = scheduled_response.json()["pois"][0]["eta_seconds"]
    active_route["value"] = detour_route
    detour_response = client.get("/api/overview/upcoming-pois")
    detour_eta = detour_response.json()["pois"][0]["eta_seconds"]

    assert direct_response.status_code == 200, direct_response.text
    assert direct_eta == pytest.approx(1324.5896)
    assert scheduled_eta == pytest.approx(direct_eta)
    assert detour_eta == pytest.approx(12188.2341)
    assert detour_eta > direct_eta + 10_000
