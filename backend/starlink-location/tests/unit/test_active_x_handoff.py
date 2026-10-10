from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.mission.models import Mission, MissionLeg, TransportConfig, XTransition
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
        metric_availability=MetricAvailability(
            latency_ms=True,
            throughput_down_mbps=True,
            throughput_up_mbps=True,
            packet_loss_percent=True,
            obstruction_percent=True,
        ),
        timestamp=timestamp or datetime(2026, 1, 1, tzinfo=timezone.utc),
        position=PositionData(
            observed_at=datetime.now(timezone.utc),
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


@pytest.mark.parametrize("longitude", [10.0, 10.1])
def test_active_x_link_commits_at_transition_without_exiting_preparation_zone(
    tmp_path, monkeypatch, longitude
):
    from app.mission import storage

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path)
    _save_active_mission(tmp_path)
    _build_link_at(0.0, 9.0)

    result = _build_link_at(0.0, longitude)

    assert result["satellite_id"] == "X-2"
    assert result["pending_satellite_id"] is None
    assert result["handoff"]["phase"] == "committed"
    assert result["handoff"]["in_handoff_zone"] is True
    assert [link["satellite_id"] for link in result["links"]] == ["X-2"]


@pytest.mark.parametrize("longitude", [10.1, 12.0])
def test_active_x_link_catches_up_when_first_observation_is_after_transition(
    tmp_path, monkeypatch, longitude
):
    """Restarting or skipping polls must not leave the starting satellite active."""
    from app.mission import storage

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path)
    _save_active_mission(tmp_path)

    result = _build_link_at(0.0, longitude)

    assert result["satellite_id"] == "X-2"
    assert result["pending_satellite_id"] is None
    assert result["handoff"]["phase"] == "committed"


def test_active_x_link_does_not_revert_when_jitter_crosses_back_before_transition(
    tmp_path, monkeypatch
):
    from app.mission import storage

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path)
    _save_active_mission(tmp_path)
    _build_link_at(0.0, 9.0)
    _build_link_at(0.0, 10.1)

    result = _build_link_at(0.0, 9.99)

    assert result["satellite_id"] == "X-2"
    assert result["pending_satellite_id"] is None
    assert result["handoff"]["phase"] == "committed"


@pytest.mark.parametrize("provenance", ["missing", "stale", "future", "naive"])
def test_active_x_link_does_not_catch_up_from_unusable_position(
    tmp_path, monkeypatch, provenance
):
    """Unavailable GPS defaults or old fixes cannot commit a sticky handoff."""
    from app.mission import storage

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path)
    _save_active_mission(tmp_path)
    reversed_route = _route().model_copy(
        update={"points": list(reversed(_route().points))}
    )
    telemetry = _telemetry(0.0, 0.0, 270.0)
    observed_at = datetime.now(timezone.utc)
    telemetry.position.observed_at = {
        "missing": None,
        "stale": observed_at - timedelta(seconds=30),
        "future": observed_at + timedelta(seconds=30),
        "naive": observed_at.replace(tzinfo=None),
    }[provenance]

    result = build_active_x_link(
        StaticCoordinator(telemetry),
        StaticRouteManager(reversed_route),
        StaticPOIManager([_satellite("X-1", 0.0), _satellite("X-2", 30.0)]),
    )

    assert result["satellite_id"] == "X-1"
    assert result["pending_satellite_id"] is None
    assert result["handoff"]["route_progress_percent"] is None


def test_active_x_link_preserves_committed_satellite_during_gps_loss(
    tmp_path, monkeypatch
):
    from app.mission import storage

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path)
    _save_active_mission(tmp_path)
    _build_link_at(0.0, 10.1)
    telemetry = _telemetry(0.0, 0.0, 90.0)
    telemetry.position.observed_at = None

    result = build_active_x_link(
        StaticCoordinator(telemetry),
        StaticRouteManager(_route()),
        StaticPOIManager([_satellite("X-1", 0.0), _satellite("X-2", 30.0)]),
    )

    assert result["satellite_id"] == "X-2"
    assert result["pending_satellite_id"] is None
    assert result["handoff"]["phase"] == "committed"
    assert result["handoff"]["route_progress_percent"] is None


def test_active_x_link_accepts_verified_zero_coordinates(tmp_path, monkeypatch):
    """Real zero coordinates with provenance are not unavailable GPS defaults."""
    from app.mission import storage

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path)
    _save_active_mission(tmp_path)
    reversed_route = _route().model_copy(
        update={"points": list(reversed(_route().points))}
    )

    result = build_active_x_link(
        StaticCoordinator(_telemetry(0.0, 0.0, 270.0)),
        StaticRouteManager(reversed_route),
        StaticPOIManager([_satellite("X-1", 0.0), _satellite("X-2", 30.0)]),
    )

    assert result["satellite_id"] == "X-2"
    assert result["handoff"]["phase"] == "committed"


def _repeated_route_and_leg():
    from app.mission.planning.match import _candidates
    from app.models.route import RouteTimingProfile

    start = datetime(2026, 10, 25, 9, tzinfo=timezone.utc)
    route = ParsedRoute(
        route_id="repeat",
        content_hash="b" * 64,
        ingestion_profile="planning_v1",
        source_departure_time=start,
        metadata=RouteMetadata(
            name="Repeated visit", file_path="repeat.kml", point_count=5
        ),
        points=[
            RoutePoint(
                latitude=lat,
                longitude=lon,
                altitude=1000,
                sequence=n,
                expected_arrival_time=start + timedelta(seconds=seconds),
                occurrence_id=f"p{n}",
            )
            for n, (lon, lat, seconds) in enumerate(
                [(0, 0, 0), (1, 0, 3620), (2, 1, 5400), (1, 0, 7240), (3, 0, 10800)]
            )
        ],
        timing_profile=RouteTimingProfile(
            departure_time=start, arrival_time=start + timedelta(hours=3)
        ),
    )
    transitions = [
        XTransition(
            id=f"t{n}",
            latitude=0,
            longitude=1,
            target_satellite_id=satellite,
            anchor=_candidates(start + timedelta(seconds=seconds), "second", route)[0],
        )
        for n, (seconds, satellite) in enumerate([(3620, "WEST"), (7240, "SOUTH")])
    ]
    return route, MissionLeg(
        id="repeat",
        name="Repeat",
        route_id="repeat",
        transports=TransportConfig(
            initial_x_satellite_id="SOUTH", x_transitions=transitions
        ),
    )


def test_anchored_handoff_tracks_both_observed_visits_without_planned_time():
    from app.services.active_x_handoff import resolve_active_x_context

    route, leg = _repeated_route_and_leg()
    # Deliberately unrelated mission timestamp; only observed position traverses the route.
    late = datetime(2030, 1, 1, tzinfo=timezone.utc)
    first = resolve_active_x_context(leg, route, _telemetry(0, 1, 90, late))
    assert first.current_satellite_id == "WEST"
    assert first.handoff["route_progress_percent"] == pytest.approx(17.157499)
    repeated_poll = resolve_active_x_context(leg, route, _telemetry(0, 1, 90, late))
    assert repeated_poll.current_satellite_id == "WEST"
    assert (
        repeated_poll.handoff["route_progress_percent"]
        == first.handoff["route_progress_percent"]
    )
    resolve_active_x_context(leg, route, _telemetry(0.0001, 1.0001, 45, late))
    jitter = resolve_active_x_context(leg, route, _telemetry(0, 1, 45, late))
    assert jitter.current_satellite_id == "WEST"
    assert (
        jitter.handoff["route_progress_percent"]
        == first.handoff["route_progress_percent"]
    )
    middle = resolve_active_x_context(leg, route, _telemetry(1, 2, 225, late))
    assert middle.current_satellite_id == "WEST"
    assert middle.handoff["route_progress_percent"] == pytest.approx(41.421251)
    second = resolve_active_x_context(leg, route, _telemetry(0, 1, 90, late))
    assert second.current_satellite_id == "SOUTH"
    assert second.pending_satellite_id is None
    assert second.handoff["phase"] == "committed"
    assert second.handoff["route_progress_percent"] == pytest.approx(65.685002)


@pytest.mark.parametrize("provenance", ["missing", "stale", "future", "naive"])
def test_anchored_handoff_unusable_position_does_not_advance_occurrence(provenance):
    from app.services.active_x_handoff import resolve_active_x_context

    route, leg = _repeated_route_and_leg()
    resolve_active_x_context(leg, route, _telemetry(0, 1, 45))
    bad = _telemetry(1, 2, 225)
    now = datetime.now(timezone.utc)
    bad.position.observed_at = {
        "missing": None,
        "stale": now - timedelta(seconds=30),
        "future": now + timedelta(seconds=30),
        "naive": now.replace(tzinfo=None),
    }[provenance]
    unavailable = resolve_active_x_context(leg, route, bad)
    assert unavailable.current_satellite_id == "WEST"
    assert unavailable.handoff["route_progress_percent"] is None
    first_again = resolve_active_x_context(leg, route, _telemetry(0, 1, 45))
    assert first_again.current_satellite_id == "WEST"
    assert first_again.handoff["route_progress_percent"] == pytest.approx(17.157499)


def test_anchored_handoff_duplicate_observation_cannot_commit_later_visit():
    from app.services.active_x_handoff import resolve_active_x_context

    route, leg = _repeated_route_and_leg()
    resolve_active_x_context(leg, route, _telemetry(0, 1, 45))
    middle = _telemetry(1, 2, 225)
    resolve_active_x_context(leg, route, middle)
    duplicate = _telemetry(0, 1, 90)
    duplicate.position.observed_at = middle.position.observed_at
    result = resolve_active_x_context(leg, route, duplicate)
    assert result.current_satellite_id == "WEST"
    assert result.handoff["route_progress_percent"] is None
    fresh = resolve_active_x_context(leg, route, _telemetry(0, 1, 90))
    assert fresh.current_satellite_id == "SOUTH"


@pytest.mark.parametrize("replacement", ["route", "transitions", "initial"])
def test_anchored_handoff_replacement_does_not_reuse_observed_progress(replacement):
    from app.services.active_x_handoff import resolve_active_x_context

    route, leg = _repeated_route_and_leg()
    resolve_active_x_context(leg, route, _telemetry(0, 1, 45))
    resolve_active_x_context(leg, route, _telemetry(1, 2, 225))
    if replacement == "route":
        route.points[-1].longitude = 4
    elif replacement == "transitions":
        leg.transports.x_transitions[1].target_satellite_id = "EAST"
    else:
        leg.transports.initial_x_satellite_id = "EAST"
    result = resolve_active_x_context(leg, route, _telemetry(0, 1, 45))
    assert result.current_satellite_id == "WEST"
    assert result.handoff["route_progress_percent"] < 20
