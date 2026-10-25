from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.mission.models import Mission, MissionLeg, TransportConfig
from app.mission.storage import save_mission_v2
from app.models.poi import POI
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
from app.models.telemetry import (
    EnvironmentalData,
    MetricAvailability,
    NetworkData,
    ObstructionData,
    PositionData,
    TelemetryData,
)
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

    def get_active_route_id(self):
        return Path(self.route.metadata.file_path).stem if self.route else None

    def get_route(self, route_id):
        return self.route if route_id == self.get_active_route_id() else None


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
        metric_availability=MetricAvailability(
            latency_ms=True,
            throughput_down_mbps=True,
            throughput_up_mbps=True,
            packet_loss_percent=True,
            obstruction_percent=True,
        ),
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


def test_active_x_link_endpoint_returns_public_response(test_client) -> None:
    response = test_client.get("/api/active-x-link")
    assert response.status_code == 200
    assert response.json() == {
        "coordinates": [],
        "links": [],
        "total": 0,
        "satellite_id": None,
        "manual_satellite_id": None,
        "selection_source": "none",
        "manual_selection_invalid": False,
        "pending_satellite_id": None,
        "handoff": {
            "phase": "outside",
            "transition_id": None,
            "transition_satellite_id": None,
            "radius_meters": 200000.0,
            "distance_to_transition_meters": None,
            "in_handoff_zone": False,
            "route_progress_percent": None,
            "transition_progress_percent": None,
        },
        "state": None,
        "color": None,
        "relative_azimuth_degrees": None,
        "in_forbidden_window": None,
    }


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


def _availability_link(
    monkeypatch,
    *,
    transport="X",
    restored=False,
    explicit_time=False,
    legacy=True,
    override_outage=False,
    satellite_longitude=30,
):
    from datetime import timedelta

    from app.mission.availability_models import (
        FailureWindow,
        LegAvailability,
        Transport,
    )

    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=90 if restored else 30)
    end = now - timedelta(seconds=30) if restored else None
    observed = now - timedelta(seconds=60)
    leg = MissionLeg(
        id="clock-leg",
        name="Clock leg",
        route_id="test-route",
        is_active=True,
        transports=TransportConfig(
            initial_x_satellite_id="X-1",
            starshield_enabled=legacy,
            planning_policy="prefer_starshield_v1" if transport == "Ku" else None,
            ku_overrides=(
                [
                    {
                        "id": "independent",
                        "start_time": observed - timedelta(seconds=1),
                        "duration_seconds": 120,
                    }
                ]
                if override_outage
                else []
            ),
        ),
    )
    monkeypatch.setattr(
        "app.services.active_x_link._find_active_mission_leg",
        lambda route=None: (None, leg),
    )
    snapshot = LegAvailability(
        mission_id="clock-mission",
        leg_id=leg.id,
        revision=2,
        planned=tuple((key, True) for key in Transport),
        failures=(
            ()
            if not legacy
            else (FailureWindow(transport=transport, start=start, end=end),)
        ),
    )
    return build_active_x_link(
        StaticCoordinator(_telemetry(0, 0, 270 if transport == "Ku" else 90, observed)),
        StaticRouteManager(_route()),
        StaticPOIManager([_satellite("X-1", satellite_longitude)]),
        availability=snapshot,
        **({"operating_time": observed} if explicit_time else {}),
    )


def test_live_x_failure_suppresses_link_before_next_sensor_sample(monkeypatch):
    result = _availability_link(monkeypatch)
    assert result["transport_active"] is False
    assert result["coordinates"] == []


def test_live_x_restore_releases_link_before_next_sensor_sample(monkeypatch):
    result = _availability_link(monkeypatch, restored=True)
    assert result["satellite_id"] == "X-1"
    assert len(result["coordinates"]) == 2


def test_explicit_replay_time_keeps_captured_x_failure(monkeypatch):
    result = _availability_link(monkeypatch, restored=True, explicit_time=True)
    assert result["transport_active"] is False


def test_live_ku_failure_releases_concurrency_with_stale_sensor_sample(monkeypatch):
    result = _availability_link(monkeypatch, transport="Ku")
    assert result["in_forbidden_window"] is True
    assert result["state"] == "normal"


def test_live_ku_restore_applies_concurrency_before_next_sensor_sample(monkeypatch):
    result = _availability_link(monkeypatch, transport="Ku", restored=True)
    assert result["state"] == "warning"


def test_explicit_ku_setting_supersedes_legacy_disabled_for_link_concurrency(
    monkeypatch,
):
    result = _availability_link(monkeypatch, transport="Ku", legacy=False)
    assert result["state"] == "warning"


def test_explicit_replay_time_preserves_ku_concurrency_state(monkeypatch):
    result = _availability_link(
        monkeypatch, transport="Ku", restored=True, explicit_time=True
    )
    assert result["state"] == "normal"


def test_independent_ku_override_still_releases_link_concurrency(monkeypatch):
    result = _availability_link(
        monkeypatch, transport="Ku", legacy=False, override_outage=True
    )
    assert result["state"] == "normal"


def test_unavailable_ku_does_not_release_physical_x_block(monkeypatch):
    result = _availability_link(monkeypatch, transport="Ku", satellite_longitude=150)
    assert result["state"] == "warning"


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("explicit", [False, True])
def test_same_leg_id_uses_actual_active_parent(tmp_path, enabled, explicit):
    from app.mission.availability_context import snapshot_for_leg

    routes, pois, active, _inactive = _same_leg_parents(
        tmp_path, {"X": enabled}, {"X": not enabled}
    )
    result = build_active_x_link(
        StaticCoordinator(_telemetry(0, 0, 90)),
        routes,
        pois,
        **(
            {"availability": snapshot_for_leg(active, active.legs[0])}
            if explicit
            else {}
        ),
    )
    assert len(result["coordinates"]) == (2 if enabled else 0)
    assert (
        result.get("transport_active") is not False
        if enabled
        else result["transport_active"] is False
    )


def _same_leg_parents(
    tmp_path,
    active_defaults,
    inactive_defaults,
    *,
    policy=None,
    active_history=(),
    inactive_history=(),
):
    from app.mission import storage
    from app.mission.active_context import resolve_active_mission_leg_context
    from app.mission.availability_models import MissionAvailability
    from app.models.poi import POICreate
    from app.services.poi_manager import POIManager
    from app.services.route_manager import RouteManager

    routes = RouteManager(tmp_path / "routes")
    routes.add_route("test-route", _route())
    routes.activate_route("test-route")
    pois = POIManager(tmp_path / "pois.json")
    pois.create_poi(
        POICreate(name="X-1", category="satellite", icon="X", latitude=0, longitude=30)
    )
    active = Mission(
        id="z-active-parent",
        name="Active",
        availability=MissionAvailability(
            defaults=active_defaults, history=active_history
        ),
        legs=[
            MissionLeg(
                id="leg-1",
                name="Active leg",
                route_id="test-route",
                is_active=True,
                transports=TransportConfig(
                    initial_x_satellite_id="X-1", planning_policy=policy
                ),
            )
        ],
    )
    inactive = Mission(
        id="a-inactive-parent",
        name="Inactive",
        availability=MissionAvailability(
            defaults=inactive_defaults, history=inactive_history
        ),
        legs=[
            MissionLeg(
                id="leg-1",
                name="Other leg",
                route_id="other-route",
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            )
        ],
    )
    storage.save_mission_v2(active)
    storage.save_mission_v2(inactive)
    assert storage.list_mission_metadata_v2()[0].id == inactive.id
    assert (
        resolve_active_mission_leg_context(routes).context.parent_mission_id
        == active.id
    )
    return routes, pois, active, inactive


@pytest.mark.parametrize("enabled", [True, False])
def test_same_leg_parent_owns_ku_concurrency(tmp_path, enabled):
    routes, pois, _, _ = _same_leg_parents(
        tmp_path, {"Ku": enabled}, {"Ku": not enabled}, policy="prefer_starshield_v1"
    )
    result = build_active_x_link(StaticCoordinator(_telemetry(0, 0, 270)), routes, pois)
    assert result["in_forbidden_window"] is True
    assert result["state"] == ("warning" if enabled else "normal")


@pytest.mark.parametrize("failure_in_active", [True, False])
def test_same_leg_parent_owns_failure_history(tmp_path, failure_in_active):
    from app.mission.availability_models import AvailabilityChange

    failure = AvailabilityChange(
        id="parent-failure",
        transport="X",
        unavailable=True,
        effective_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    routes, pois, _, _ = _same_leg_parents(
        tmp_path,
        {},
        {},
        active_history=(failure,) if failure_in_active else (),
        inactive_history=() if failure_in_active else (failure,),
    )
    result = build_active_x_link(StaticCoordinator(_telemetry(0, 0, 90)), routes, pois)
    assert len(result["coordinates"]) == (0 if failure_in_active else 2)
