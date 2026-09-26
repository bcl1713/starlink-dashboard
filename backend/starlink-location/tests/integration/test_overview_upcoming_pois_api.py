"""Integration tests for the Overview upcoming-POI API and ETA source."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.mission.dependencies import get_poi_manager
from app.mission.models import Mission, MissionLeg, TransportConfig
from app.mission.storage import save_mission_v2
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


def arrange_active_v2_context(
    client,
    *,
    mission_id: str = "mission-1",
    leg_id: str = "leg-1",
    route_id: str = "test-route",
    active_route: ParsedRoute | None = None,
) -> ParsedRoute:
    """Persist one active v2 leg and make its route the active route."""
    active_route = active_route or route([(40.0, -73.0), (40.0, -71.0)])
    mission = Mission(
        id=mission_id,
        name=mission_id,
        legs=[
            MissionLeg(
                id=leg_id,
                name=leg_id,
                route_id=route_id,
                is_active=True,
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            )
        ],
    )
    save_mission_v2(mission)
    route_manager = client.app.state.route_manager
    route_manager.add_route(route_id, active_route)
    assert route_manager.activate_route(route_id) is True
    return active_route


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


def test_api_returns_no_active_mission_without_fabricating_records(client):
    response = client.get("/api/overview/upcoming-pois")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "no_active_mission"
    assert payload["pois"] == []
    assert payload["calculated_at"].endswith("+00:00")


@pytest.mark.parametrize(
    ("setup", "expected_state"),
    [
        ("route_only_active", "no_active_mission"),
        ("missing_leg_route", "route_unavailable"),
        ("mismatched_active_route", "route_unavailable"),
        ("two_persisted_active_legs", "inconsistent_active_mission"),
    ],
)
def test_overview_context_failures_return_no_pois(client, setup, expected_state):
    route_manager = client.app.state.route_manager
    if setup == "route_only_active":
        route_manager.add_route("route-a", route([(40.0, -73.0), (40.0, -71.0)]))
        assert route_manager.activate_route("route-a") is True
    elif setup == "missing_leg_route":
        save_mission_v2(
            Mission(
                id="mission-a",
                name="mission-a",
                legs=[
                    MissionLeg(
                        id="leg-a",
                        name="leg-a",
                        route_id="missing-route",
                        is_active=True,
                        transports=TransportConfig(initial_x_satellite_id="X-1"),
                    )
                ],
            )
        )
    elif setup == "mismatched_active_route":
        arrange_active_v2_context(client, route_id="route-a")
        route_manager.add_route("route-b", route([(40.0, -73.0), (40.0, -70.0)]))
        route_manager._active_route_id = "route-b"
    else:
        arrange_active_v2_context(client, mission_id="mission-a", route_id="route-a")
        save_mission_v2(
            Mission(
                id="mission-b",
                name="mission-b",
                legs=[
                    MissionLeg(
                        id="leg-b",
                        name="leg-b",
                        route_id="route-a",
                        is_active=True,
                        transports=TransportConfig(initial_x_satellite_id="X-1"),
                    )
                ],
            )
        )

    response = client.get("/api/overview/upcoming-pois")

    assert response.status_code == 200
    assert response.json()["state"] == expected_state
    assert response.json()["pois"] == []


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
    arrange_active_v2_context(client, active_route=active_route)
    client.app.dependency_overrides[get_poi_manager] = lambda: SimpleNamespace(
        list_pois=lambda mission_id=None: [generated_poi]
    )
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
    arrange_active_v2_context(client, active_route=active_route)
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

    active_route = route([(40.0, -73.0), (40.0, -71.0)])
    manual_poi = scheduled_poi().model_copy(
        update={"category": "landmark", "generated_source": None}
    )
    arrange_active_v2_context(client, active_route=active_route)
    client.app.dependency_overrides[get_poi_manager] = lambda: SimpleNamespace(
        list_pois=lambda mission_id=None: [manual_poi]
    )

    response = client.get("/api/overview/upcoming-pois")

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "no_generated_pois"
    assert response.json()["pois"] == []


def test_api_excludes_generated_pois_from_an_inactive_leg_of_the_same_parent(
    client, monkeypatch
):
    """Overview may project only the active leg's generated timeline POIs."""
    import app.api.overview_upcoming_pois as overview_api

    active_route = route([(40.0, -73.0), (40.0, -71.0)])
    inactive_route = route([(41.0, -74.0), (41.0, -72.0)])
    save_mission_v2(
        Mission(
            id="mission-1",
            name="mission-1",
            legs=[
                MissionLeg(
                    id="leg-active",
                    name="leg-active",
                    route_id="route-active",
                    is_active=True,
                    transports=TransportConfig(initial_x_satellite_id="X-1"),
                ),
                MissionLeg(
                    id="leg-inactive",
                    name="leg-inactive",
                    route_id="route-inactive",
                    is_active=False,
                    transports=TransportConfig(initial_x_satellite_id="X-1"),
                ),
            ],
        )
    )
    route_manager = client.app.state.route_manager
    route_manager.add_route("route-active", active_route)
    route_manager.add_route("route-inactive", inactive_route)
    assert route_manager.activate_route("route-active") is True
    client.app.dependency_overrides[get_poi_manager] = lambda: SimpleNamespace(
        list_pois=lambda mission_id=None: [
            scheduled_poi().model_copy(
                update={
                    "id": "active-leg-poi",
                    "mission_id": "mission-1",
                    "route_id": "route-active",
                }
            ),
            scheduled_poi().model_copy(
                update={
                    "id": "inactive-leg-poi",
                    "mission_id": "mission-1",
                    "route_id": "route-inactive",
                }
            ),
            scheduled_poi().model_copy(
                update={
                    "id": "legacy-parent-poi",
                    "mission_id": "mission-1",
                    "route_id": None,
                }
            ),
        ]
    )
    monkeypatch.setattr(
        overview_api,
        "get_flight_state_manager",
        lambda: SimpleNamespace(
            get_status=lambda: SimpleNamespace(
                phase=SimpleNamespace(value="pre_departure")
            )
        ),
    )

    response = client.get("/api/overview/upcoming-pois")

    assert response.status_code == 200, response.text
    assert {poi["poi_id"] for poi in response.json()["pois"]} == {
        "active-leg-poi",
        "legacy-parent-poi",
    }


def test_api_returns_unavailable_without_in_flight_telemetry(client, monkeypatch):
    import app.api.overview_upcoming_pois as overview_api

    active_route = route([(40.0, -73.0), (40.0, -71.0)])
    arrange_active_v2_context(client, active_route=active_route)
    client.app.dependency_overrides[get_poi_manager] = lambda: SimpleNamespace(
        list_pois=lambda mission_id=None: [scheduled_poi()]
    )
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
    poi = scheduled_poi()
    coordinator = SimpleNamespace(
        get_current_telemetry=lambda: SimpleNamespace(
            position=SimpleNamespace(latitude=40.0, longitude=-73.0, speed=200)
        )
    )
    client.app.state.coordinator = coordinator
    arrange_active_v2_context(client, active_route=direct_route)
    client.app.dependency_overrides[get_poi_manager] = lambda: SimpleNamespace(
        list_pois=lambda mission_id=None: [poi]
    )
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
    client.app.state.route_manager.add_route("test-route", detour_route)
    detour_response = client.get("/api/overview/upcoming-pois")
    detour_eta = detour_response.json()["pois"][0]["eta_seconds"]

    assert direct_response.status_code == 200, direct_response.text
    assert direct_eta == pytest.approx(1324.5896)
    assert scheduled_eta == pytest.approx(direct_eta)
    assert detour_eta == pytest.approx(12188.2341)
    assert detour_eta > direct_eta + 10_000
