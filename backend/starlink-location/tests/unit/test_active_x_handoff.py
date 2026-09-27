from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.mission.models import Mission, MissionLeg, TransportConfig, XTransition
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
from app.services.active_x_handoff import reset_x_handoff_state
from app.services.active_x_link import build_active_x_link


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


@pytest.fixture(autouse=True)
def _reset_handoff_state():
    reset_x_handoff_state()
    yield
    reset_x_handoff_state()


def _save_active_mission(tmp_path: Path) -> None:
    mission = Mission(
        id="mission-85",
        name="Mission 85",
        legs=[
            MissionLeg(
                id="leg-1",
                name="Leg 1",
                route_id="test-route",
                is_active=True,
                transports=TransportConfig(
                    initial_x_satellite_id="X-1",
                    x_transitions=[
                        XTransition(
                            id="x-swap",
                            latitude=0.0,
                            longitude=10.0,
                            target_satellite_id="X-2",
                        )
                    ],
                ),
            )
        ],
    )
    save_mission_v2(mission)


def _build_link_at(
    latitude: float,
    longitude: float,
    *,
    timestamp: datetime | None = None,
) -> dict:
    return build_active_x_link(
        coordinator=StaticCoordinator(
            _telemetry(
                latitude=latitude,
                longitude=longitude,
                heading=90.0,
                timestamp=timestamp,
            )
        ),
        route_manager=StaticRouteManager(_route()),
        poi_manager=StaticPOIManager([_satellite("X-1", 0.0), _satellite("X-2", 30.0)]),
    )


def test_active_x_link_does_not_switch_on_late_mission_time_before_zone(
    tmp_path, monkeypatch
):
    from app.mission import storage

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path)
    _save_active_mission(tmp_path)

    result = _build_link_at(
        0.0,
        7.0,
        timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
    )

    assert result["satellite_id"] == "X-1"
    assert result["pending_satellite_id"] is None
    assert result["handoff"]["phase"] == "outside"


def test_active_x_link_shows_dual_context_inside_zone_without_commit(
    tmp_path, monkeypatch
):
    from app.mission import storage

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path)
    _save_active_mission(tmp_path)

    result = _build_link_at(0.0, 9.0)

    assert result["satellite_id"] == "X-1"
    assert result["pending_satellite_id"] == "X-2"
    assert result["handoff"]["phase"] == "in_handoff_zone"
    assert result["handoff"]["transition_id"] == "x-swap"
    assert {link["satellite_id"] for link in result["links"]} == {"X-1", "X-2"}
    assert result["total"] == 4


def test_active_x_link_keeps_current_satellite_for_route_deviation_while_approaching(
    tmp_path, monkeypatch
):
    from app.mission import storage

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path)
    _save_active_mission(tmp_path)

    result = _build_link_at(1.0, 8.8)

    assert result["satellite_id"] == "X-1"
    assert result["pending_satellite_id"] == "X-2"
    assert result["handoff"]["phase"] == "in_handoff_zone"
    assert (
        result["handoff"]["route_progress_percent"]
        < result["handoff"]["transition_progress_percent"]
    )


def test_active_x_link_commits_after_passing_through_and_exiting_zone(
    tmp_path, monkeypatch
):
    from app.mission import storage

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path)
    _save_active_mission(tmp_path)

    _build_link_at(0.0, 9.0)
    result = _build_link_at(0.0, 12.0)

    assert result["satellite_id"] == "X-2"
    assert result["pending_satellite_id"] is None
    assert result["handoff"]["phase"] == "committed"
    assert result["coordinates"][1]["longitude"] == 30.0


def test_active_x_link_does_not_flap_after_commit_on_reentry_jitter(
    tmp_path, monkeypatch
):
    from app.mission import storage

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path)
    _save_active_mission(tmp_path)

    _build_link_at(0.0, 9.0)
    _build_link_at(0.0, 12.0)
    result = _build_link_at(0.0, 10.5)

    assert result["satellite_id"] == "X-2"
    assert result["pending_satellite_id"] is None
    assert result["handoff"]["phase"] == "committed"
