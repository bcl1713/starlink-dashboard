from datetime import datetime, timezone

import pytest
from app.api import active_x_link as active_x_link_api
from app.mission.dependencies import get_poi_manager, get_route_manager
from app.mission.models import Mission, MissionLeg, TransportConfig
from app.mission.storage import save_mission_v2
from app.models.poi import POI
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
from app.models.telemetry import (
    EnvironmentalData,
    NetworkData,
    ObstructionData,
    PositionData,
    TelemetryData,
)
from app.services.active_x_link import build_active_x_link
from fastapi.testclient import TestClient
from main import app


class StaticCoordinator:
    def __init__(self, telemetry: TelemetryData):
        self.telemetry = telemetry

    def get_current_telemetry(self) -> TelemetryData:
        return self.telemetry


class StaticRouteManager:
    def __init__(self, route: ParsedRoute | None):
        self.route = route

    def get_active_route(self) -> ParsedRoute | None:
        return self.route


class StaticPOIManager:
    def __init__(self, pois: list[POI]):
        self.pois = pois

    def list_pois(self):
        return self.pois


def _telemetry(
    latitude: float,
    longitude: float,
    heading: float,
    timestamp: datetime | None = None,
) -> TelemetryData:
    return TelemetryData(
        timestamp=timestamp or datetime(2026, 1, 1, tzinfo=timezone.utc),
        position=PositionData(
            latitude=latitude,
            longitude=longitude,
            altitude=35000.0,
            speed=450.0,
            heading=heading,
        ),
        network=NetworkData(
            latency_ms=40.0,
            throughput_down_mbps=120.0,
            throughput_up_mbps=20.0,
            packet_loss_percent=0.0,
        ),
        obstruction=ObstructionData(obstruction_percent=0.0),
        environmental=EnvironmentalData(),
    )


def _route() -> ParsedRoute:
    return ParsedRoute(
        metadata=RouteMetadata(
            name="Test route",
            file_path="/tmp/test-route.kml",
            point_count=3,
        ),
        points=[
            RoutePoint(latitude=0.0, longitude=0.0, sequence=0),
            RoutePoint(latitude=0.0, longitude=10.0, sequence=1),
            RoutePoint(latitude=0.0, longitude=20.0, sequence=2),
        ],
    )


def _satellite(name: str, longitude: float) -> POI:
    return POI(
        id=name.lower(),
        name=name,
        latitude=0.0,
        longitude=longitude,
        icon="X",
        category="satellite",
    )


def test_active_x_link_endpoint_is_registered() -> None:
    assert any(
        getattr(route, "path", None) == "/api/active-x-link" for route in app.routes
    )


def test_active_x_link_prefers_active_leg_matching_active_route(tmp_path, monkeypatch):
    from app.mission import storage

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path)
    save_mission_v2(
        Mission(
            id="a-other-mission",
            name="Other Mission",
            legs=[
                MissionLeg(
                    id="other-leg",
                    name="Other Leg",
                    route_id="other-route",
                    is_active=True,
                    transports=TransportConfig(initial_x_satellite_id="X-1"),
                )
            ],
        )
    )
    save_mission_v2(
        Mission(
            id="z-current-mission",
            name="Current Mission",
            legs=[
                MissionLeg(
                    id="current-leg",
                    name="Current Leg",
                    route_id="test-route",
                    is_active=True,
                    transports=TransportConfig(initial_x_satellite_id="X-2"),
                )
            ],
        )
    )

    result = build_active_x_link(
        coordinator=StaticCoordinator(
            _telemetry(latitude=0.0, longitude=0.0, heading=90.0)
        ),
        route_manager=StaticRouteManager(_route()),
        poi_manager=StaticPOIManager([_satellite("X-1", 0.0), _satellite("X-2", 30.0)]),
    )

    assert result["satellite_id"] == "X-2"


def test_active_x_link_marks_green_outside_normal_forbidden_window(
    tmp_path, monkeypatch
):
    from app.mission import storage

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path)
    mission = Mission(
        id="mission-85",
        name="Mission 85",
        legs=[
            MissionLeg(
                id="leg-1",
                name="Leg 1",
                route_id="test-route",
                is_active=True,
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            )
        ],
    )
    save_mission_v2(mission)

    result = build_active_x_link(
        coordinator=StaticCoordinator(
            _telemetry(latitude=0.0, longitude=0.0, heading=90.0)
        ),
        route_manager=StaticRouteManager(_route()),
        poi_manager=StaticPOIManager([_satellite("X-1", 30.0)]),
    )

    assert result["state"] == "normal"
    assert result["color"] == "green"
    assert result["in_forbidden_window"] is False


def test_active_x_link_marks_warning_inside_normal_forbidden_window(
    tmp_path, monkeypatch
):
    from app.mission import storage

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path)
    mission = Mission(
        id="mission-85",
        name="Mission 85",
        legs=[
            MissionLeg(
                id="leg-1",
                name="Leg 1",
                route_id="test-route",
                is_active=True,
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            )
        ],
    )
    save_mission_v2(mission)

    result = build_active_x_link(
        coordinator=StaticCoordinator(
            _telemetry(latitude=0.0, longitude=0.0, heading=270.0)
        ),
        route_manager=StaticRouteManager(_route()),
        poi_manager=StaticPOIManager([_satellite("X-1", 30.0)]),
    )

    assert result["state"] == "warning"
    assert result["color"] == "yellow"
    assert result["in_forbidden_window"] is True


def test_active_x_link_endpoint_is_typed_and_reports_truthful_freshness(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.mission import storage

    observed_at = datetime(2026, 8, 29, 11, 55, tzinfo=timezone.utc)
    generated_at = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path)
    monkeypatch.setattr(active_x_link_api, "_utc_now", lambda: generated_at)
    save_mission_v2(
        Mission(
            id="mission",
            name="Mission",
            legs=[
                MissionLeg(
                    id="leg",
                    name="Leg",
                    route_id="test-route",
                    is_active=True,
                    transports=TransportConfig(initial_x_satellite_id="X-1"),
                )
            ],
        )
    )
    app.dependency_overrides[active_x_link_api.get_coordinator] = (
        lambda: StaticCoordinator(
            _telemetry(latitude=0.0, longitude=0.0, heading=90.0, timestamp=observed_at)
        )
    )
    app.dependency_overrides[get_route_manager] = lambda: StaticRouteManager(_route())
    app.dependency_overrides[get_poi_manager] = lambda: StaticPOIManager(
        [_satellite("X-1", 30.0)]
    )

    with TestClient(app) as client:
        response = client.get("/api/active-x-link")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["observed_at"] == "2026-08-29T11:55:00Z"
    assert body["generated_at"] == "2026-08-29T12:00:00Z"
    assert body["coordinates"][0]["latitude"] == 0.0
    assert body["coordinates"][0]["observed_at"] == "2026-08-29T11:55:00Z"


def test_active_x_link_cached_observation_stays_stable_while_generated_advances(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.mission import storage

    observed_at = datetime(2026, 8, 29, 11, 55, tzinfo=timezone.utc)
    generated_times = iter(
        [
            datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 8, 29, 12, 1, tzinfo=timezone.utc),
        ]
    )
    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path)
    monkeypatch.setattr(active_x_link_api, "_utc_now", lambda: next(generated_times))
    save_mission_v2(
        Mission(
            id="mission",
            name="Mission",
            legs=[
                MissionLeg(
                    id="leg",
                    name="Leg",
                    route_id="test-route",
                    is_active=True,
                    transports=TransportConfig(initial_x_satellite_id="X-1"),
                )
            ],
        )
    )
    app.dependency_overrides[active_x_link_api.get_coordinator] = (
        lambda: StaticCoordinator(
            _telemetry(latitude=0.0, longitude=0.0, heading=90.0, timestamp=observed_at)
        )
    )
    app.dependency_overrides[get_route_manager] = lambda: StaticRouteManager(_route())
    app.dependency_overrides[get_poi_manager] = lambda: StaticPOIManager(
        [_satellite("X-1", 30.0)]
    )

    with TestClient(app) as client:
        first = client.get("/api/active-x-link").json()
        second = client.get("/api/active-x-link").json()

    app.dependency_overrides.clear()
    assert first["observed_at"] == second["observed_at"]
    assert first["generated_at"] == "2026-08-29T12:00:00Z"
    assert second["generated_at"] == "2026-08-29T12:01:00Z"
