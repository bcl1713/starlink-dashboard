"""Tests for durable mission timeline POI replacement."""

from datetime import datetime, timezone

from app.mission.models import AARWindow, MissionLeg, TransportConfig, XTransition
from app.mission.timeline_builder.coverage import (
    CoverageAnalysisResult,
    KaCoverageGap,
    KaCoverageSwap,
    RouteSample,
)
from app.mission.timeline_builder.pois import (
    collect_ka_pois,
    collect_x_aar_pois,
    sync_ka_pois,
    sync_x_aar_pois,
)
from app.models.poi import POICreate
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint, RouteWaypoint
from app.services.poi_manager import POIManager

BASE = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _route() -> ParsedRoute:
    return ParsedRoute(
        metadata=RouteMetadata(name="Route", file_path="/tmp/route.kml", point_count=2),
        points=[
            RoutePoint(latitude=0.0, longitude=0.0, sequence=0),
            RoutePoint(latitude=0.0, longitude=10.0, sequence=1),
        ],
        waypoints=[
            RouteWaypoint(name="ARIP", latitude=0.0, longitude=2.0, order=0),
            RouteWaypoint(name="ARCP", latitude=0.0, longitude=8.0, order=1),
        ],
    )


def _sample(name_offset: float) -> RouteSample:
    return RouteSample(
        distance_meters=0.0,
        timestamp=BASE,
        latitude=0.0,
        longitude=name_offset,
        altitude=10000.0,
        heading=90.0,
    )


def test_collect_timeline_pois_is_pure_payload_collection(tmp_path):
    """Timeline builder helpers should not write directly to POI storage."""
    manager = POIManager(pois_file=tmp_path / "pois.json")
    mission = MissionLeg(
        id="leg-1",
        name="Leg 1",
        route_id="route-1",
        transports=TransportConfig(
            initial_x_satellite_id="X-1",
            x_transitions=[
                XTransition(
                    id="x-1",
                    latitude=0.0,
                    longitude=5.0,
                    target_satellite_id="X-2",
                    target_beam_id=None,
                    is_same_satellite_transition=False,
                )
            ],
            aar_windows=[
                AARWindow(
                    id="aar-1",
                    name="AAR",
                    start_waypoint_name="ARIP",
                    end_waypoint_name="ARCP",
                )
            ],
        ),
    )
    coverage = CoverageAnalysisResult(
        gaps=[
            KaCoverageGap(
                start=_sample(1.0),
                end=_sample(2.0),
                lost_satellite="AOR",
                regained_satellite="POR",
            )
        ],
        swaps=[
            KaCoverageSwap(
                midpoint=_sample(3.0),
                from_satellite="AOR",
                to_satellite="POR",
            )
        ],
    )

    payloads = [
        *collect_ka_pois(mission, _route(), coverage, parent_mission_id="mission-1"),
        *collect_x_aar_pois(mission, _route(), parent_mission_id="mission-1"),
    ]

    assert len(payloads) == 6
    assert manager.list_pois() == []


def test_replace_timeline_event_pois_is_atomic_and_scope_exact(tmp_path):
    """Only generated Ka/X/AAR POIs for the exact route+mission are replaced."""
    manager = POIManager(pois_file=tmp_path / "pois.json")
    manager.create_poi(POICreate(name="User", latitude=1, longitude=1))
    manager.create_poi(
        POICreate(
            name="CommKa\nExit",
            latitude=1,
            longitude=1,
            category="mission-event",
            route_id="route-1",
            mission_id="mission-1",
        )
    )
    manager.create_poi(
        POICreate(
            name="CommKa\nExit",
            latitude=2,
            longitude=2,
            category="mission-event",
            route_id="route-2",
            mission_id="mission-1",
        )
    )
    manager.create_poi(
        POICreate(
            name="Planner Note",
            latitude=3,
            longitude=3,
            category="mission-event",
            route_id="route-1",
            mission_id="mission-1",
        )
    )

    first = manager.replace_timeline_event_pois(
        route_id="route-1",
        mission_id="mission-1",
        generated_pois=[
            POICreate(
                name="X-Band\nSwap",
                latitude=0.0,
                longitude=5.0,
                icon="satellite",
                category="mission-event",
                route_id="route-1",
                mission_id="mission-1",
            )
        ],
        route=_route(),
    )
    second = manager.replace_timeline_event_pois(
        route_id="route-1",
        mission_id="mission-1",
        generated_pois=[],
        route=_route(),
    )

    reopened = POIManager(pois_file=tmp_path / "pois.json")
    names = sorted(
        ((poi.route_id, poi.mission_id, poi.name) for poi in reopened.list_pois()),
        key=lambda item: (item[0] or "", item[1] or "", item[2]),
    )
    assert [poi.id for poi in first] == ["route-1-mission-1-x-band-swap"]
    assert first[0].generated_provenance == "timeline-event/all"
    assert second == []
    assert names == [
        (None, None, "User"),
        ("route-1", "mission-1", "CommKa\nExit"),
        ("route-1", "mission-1", "Planner Note"),
        ("route-2", "mission-1", "CommKa\nExit"),
    ]


def test_legacy_ka_then_x_sync_preserves_both_generated_families(tmp_path):
    """Compatibility wrappers must not replace each other's generated events."""
    manager = POIManager(pois_file=tmp_path / "pois.json")
    mission = MissionLeg(
        id="leg-1",
        name="Leg 1",
        route_id="route-1",
        transports=TransportConfig(
            initial_x_satellite_id="X-1",
            x_transitions=[
                XTransition(
                    id="x-1",
                    latitude=0.0,
                    longitude=5.0,
                    target_satellite_id="X-2",
                    target_beam_id=None,
                    is_same_satellite_transition=False,
                )
            ],
        ),
    )
    coverage = CoverageAnalysisResult(
        gaps=[
            KaCoverageGap(
                start=_sample(1.0),
                end=None,
                lost_satellite="AOR",
                regained_satellite=None,
            )
        ],
        swaps=[],
    )

    sync_ka_pois(mission, _route(), manager, coverage, parent_mission_id="mission-1")
    sync_x_aar_pois(mission, _route(), manager, parent_mission_id="mission-1")

    assert sorted(poi.name for poi in manager.list_pois()) == [
        "CommKa\nExit",
        "X-Band\nSwap",
    ]
