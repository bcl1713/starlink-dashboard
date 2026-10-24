"""Manual settings must persist safely and never hide an active mission."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
DESTINATION = {"name": "Destination", "latitude": 0, "longitude": 1}
URL = "/api/overview/manual-destination"


@pytest.fixture
def manual_client(client, tmp_path, monkeypatch):
    from app.services.manual_destination import ManualDestinationStore

    client.app.state.manual_destination_store = ManualDestinationStore(
        tmp_path / "destination.json"
    )
    monkeypatch.setattr("app.api.overview_upcoming_pois._utc_now", lambda: NOW)
    client.app.state.coordinator = SimpleNamespace(
        get_current_telemetry=lambda: SimpleNamespace(
            position=SimpleNamespace(
                latitude=0,
                longitude=0,
                speed=300,
                observed_at=NOW,
                speed_observed_at=NOW,
            )
        )
    )
    yield client
    client.app.dependency_overrides.clear()
    del client.app.state.coordinator


def test_manual_setting_save_replace_clear_and_reopen(client, tmp_path):
    # Missing endpoint is a behavioral failure before the store is implemented.
    assert client.get(URL).json() == {"destination": None}
    from app.services.manual_destination import ManualDestinationStore

    path = tmp_path / "destination.json"
    client.app.state.manual_destination_store = ManualDestinationStore(path)
    assert client.put(URL, json={"destination": DESTINATION}).status_code == 200
    client.app.state.manual_destination_store = ManualDestinationStore(path)
    assert client.get(URL).json() == {
        "destination": {**DESTINATION, "airport_code": None}
    }
    replacement = {
        **DESTINATION,
        "name": "Tokyo",
        "airport_code": "RJTT",
        "longitude": 139.78,
    }
    assert (
        client.put(URL, json={"destination": replacement}).json()["destination"]
        == replacement
    )
    assert client.put(URL, json={"destination": None}).json() == {"destination": None}
    client.app.state.manual_destination_store = ManualDestinationStore(path)
    assert client.get(URL).json() == {"destination": None}


@pytest.mark.parametrize(
    "invalid",
    [
        {},
        {"name": " "},
        {"name": "x" * 121},
        {"latitude": 91},
        {"longitude": -181},
        {"latitude": True},
        {"airport_code": "too-long-code"},
    ],
)
def test_invalid_settings_do_not_overwrite_saved_destination(manual_client, invalid):
    assert manual_client.put(URL, json={"destination": DESTINATION}).status_code == 200
    payload = {} if invalid == {} else {"destination": {**DESTINATION, **invalid}}
    assert manual_client.put(URL, json=payload).status_code == 422
    assert manual_client.get(URL).json()["destination"]["name"] == "Destination"


@pytest.mark.parametrize(
    "query,code",
    [
        ("kjfk", "KJFK"),
        ("JFK", "KJFK"),
        ("Heathrow", "EGLL"),
        ("RJTT", "RJTT"),
        ("YSSY", "YSSY"),
        ("FAOR", "FAOR"),
        ("SBGR", "SBGR"),
    ],
)
def test_airports_search_worldwide_code_and_name(client, query, code):
    response = client.get("/api/overview/airports", params={"q": query})
    assert response.status_code == 200
    matches = response.json()["airports"]
    assert len(matches) <= 20
    assert any(a["ident"] == code and isinstance(a["latitude"], float) for a in matches)


def test_airports_empty_and_unmatched_queries(client):
    assert client.get("/api/overview/airports", params={"q": ""}).json() == {
        "airports": []
    }
    assert client.get(
        "/api/overview/airports", params={"q": "qzx-nonexistent-airport"}
    ).json() == {"airports": []}


def test_manual_eta_uses_direct_distance_fresh_speed_without_flight_phase(
    manual_client, monkeypatch
):
    def forbidden():
        raise AssertionError("Manual destination must not read mission flight state")

    monkeypatch.setattr(
        "app.api.overview_upcoming_pois.get_flight_state_manager", forbidden
    )
    manual_client.put(URL, json={"destination": DESTINATION})
    payload = manual_client.get("/api/overview/upcoming-pois").json()
    assert payload["source"] == "manual"
    assert payload["state"] == "available"
    assert payload["flight_phase"] is None
    assert payload["current_route_progress"] is None
    poi = payload["pois"][0]
    assert poi["kind"] == "arrival"
    assert poi["projected_route_progress"] is None
    assert poi["eta_seconds"] == pytest.approx(720.485486, abs=0.00001)
    assert poi["expected_arrival_time"] is None
    assert datetime.fromisoformat(poi["estimated_arrival_time"]) == NOW + timedelta(
        seconds=poi["eta_seconds"]
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"speed": 0},
        {"speed": -1},
        {"speed": None},
        {"speed": float("nan")},
        {"speed": float("inf")},
        {"speed": True},
        {"speed_observed_at": None},
        {"speed_observed_at": NOW - timedelta(seconds=10)},
        {"observed_at": None},
        {"observed_at": NOW - timedelta(seconds=10)},
        {"latitude": 91},
        {"longitude": float("nan")},
    ],
)
def test_manual_bad_or_stale_telemetry_keeps_point_without_eta(manual_client, changes):
    manual_client.put(URL, json={"destination": DESTINATION})
    position = {
        "latitude": 0,
        "longitude": 0,
        "speed": 300,
        "observed_at": NOW,
        "speed_observed_at": NOW,
    }
    position.update(changes)
    manual_client.app.state.coordinator = SimpleNamespace(
        get_current_telemetry=lambda: SimpleNamespace(
            position=SimpleNamespace(**position)
        )
    )
    payload = manual_client.get("/api/overview/upcoming-pois").json()
    assert payload["source"] == "manual"
    assert payload["state"] == "unavailable"
    assert payload["pois"][0]["map_retained"] is True
    assert payload["pois"][0]["eta_seconds"] is None
    assert payload["pois"][0]["estimated_arrival_time"] is None


def test_manual_missing_telemetry_keeps_point(manual_client):
    manual_client.put(URL, json={"destination": DESTINATION})
    del manual_client.app.state.coordinator
    payload = manual_client.get("/api/overview/upcoming-pois").json()
    assert payload["source"] == "manual"
    assert payload["state"] == "unavailable"
    assert payload["pois"][0]["eta_seconds"] is None
    manual_client.app.state.coordinator = None


@pytest.mark.parametrize("state", ["route_unavailable", "inconsistent_active_mission"])
def test_manual_never_hides_inconsistent_active_mission(
    manual_client, monkeypatch, state
):
    from app.mission.active_context import ActiveMissionLegResolution

    manual_client.put(URL, json={"destination": DESTINATION})
    monkeypatch.setattr(
        "app.api.overview_upcoming_pois.resolve_active_mission_leg_context",
        lambda _: ActiveMissionLegResolution(state),
    )
    payload = manual_client.get("/api/overview/upcoming-pois").json()
    assert payload["state"] == state
    assert payload["pois"] == []


def test_active_mission_precedes_manual_and_deactivation_restores_it(manual_client):
    from app.mission.models import Mission, MissionLeg, TransportConfig
    from app.mission.storage import save_mission_v2
    from app.models.route import ParsedRoute, RouteMetadata, RoutePoint

    manual_client.put(URL, json={"destination": DESTINATION})
    route_manager = manual_client.app.state.route_manager
    route_manager.add_route(
        "manual-test-route",
        ParsedRoute(
            metadata=RouteMetadata(name="r", file_path="r.kml", point_count=2),
            points=[RoutePoint(latitude=0, longitude=x, sequence=x) for x in (0, 1)],
        ),
    )
    route_manager.activate_route("manual-test-route")
    # An uploaded route alone does not block the manual destination.
    assert manual_client.get("/api/overview/upcoming-pois").json()["source"] == "manual"
    mission = Mission(
        id="manual-test-mission",
        name="m",
        legs=[
            MissionLeg(
                id="leg",
                name="leg",
                route_id="manual-test-route",
                is_active=True,
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            )
        ],
    )
    save_mission_v2(mission)
    payload = manual_client.get("/api/overview/upcoming-pois").json()
    assert payload.get("source") != "manual"
    assert payload["state"] == "no_generated_pois"
    mission.legs[0].is_active = False
    save_mission_v2(mission)
    assert manual_client.get("/api/overview/upcoming-pois").json()["source"] == "manual"


def test_airport_search_does_not_treat_coordinates_as_identifiers(client):
    assert client.get("/api/overview/airports", params={"q": "51.470748"}).json() == {
        "airports": []
    }


def test_failed_atomic_save_preserves_existing_destination(
    manual_client, monkeypatch, tmp_path
):
    assert manual_client.put(URL, json={"destination": DESTINATION}).status_code == 200

    def fail_replace(*_):
        raise OSError("disk unavailable")

    monkeypatch.setattr("app.services.manual_destination.os.replace", fail_replace)
    response = manual_client.put(
        URL, json={"destination": {**DESTINATION, "name": "Replacement"}}
    )
    assert response.status_code == 503
    assert manual_client.get(URL).json()["destination"]["name"] == "Destination"
    assert not list(tmp_path.glob(".destination.json.*.tmp"))
