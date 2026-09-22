"""Tests for persisted, typed POIs generated from mission timelines."""

from datetime import datetime, timedelta, timezone

from app.mission.models import AARWindow, MissionLeg, TransportConfig, XTransition
from app.mission.timeline_builder.aar import ResolvedAARWindow
from app.mission.timeline_builder.coverage import CoverageAnalysisResult
from app.mission.timeline_builder.pois import sync_mission_pois
from app.models.poi import POI, POICreate
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint, RouteWaypoint
from app.services.poi_manager import POIManager


BASE = datetime(2025, 10, 27, 12, 0, tzinfo=timezone.utc)


def _route() -> ParsedRoute:
    return ParsedRoute(
        metadata=RouteMetadata(
            name="Test route",
            file_path="test.kml",
            imported_at=BASE,
            point_count=2,
        ),
        points=[
            RoutePoint(latitude=38.8, longitude=-76.9, sequence=0),
            RoutePoint(latitude=37.5, longitude=126.5, sequence=1),
        ],
        waypoints=[
            RouteWaypoint(
                name="KADW",
                latitude=38.8,
                longitude=-76.9,
                order=0,
                role="departure",
            ),
            RouteWaypoint(
                name="AAR Start",
                latitude=39.0,
                longitude=-77.0,
                order=1,
            ),
            RouteWaypoint(
                name="AAR End",
                latitude=39.1,
                longitude=-77.1,
                order=2,
            ),
            RouteWaypoint(
                name="RKSO",
                latitude=37.5,
                longitude=126.5,
                order=3,
                role="arrival",
            ),
        ],
    )


def _mission() -> MissionLeg:
    return MissionLeg(
        id="mission-1",
        name="Test mission",
        route_id="route-1",
        transports=TransportConfig(
            initial_x_satellite_id="X-1",
            aar_windows=[
                AARWindow(
                    id="AAR-1",
                    start_waypoint_name="AAR Start",
                    end_waypoint_name="AAR End",
                )
            ],
            x_transitions=[
                XTransition(
                    id="x-1",
                    latitude=39.2,
                    longitude=-77.2,
                    target_satellite_id="X-2",
                )
            ],
        ),
    )


def test_sync_mission_pois_keeps_imported_endpoint_labels_and_typed_schedule(tmp_path):
    mission = _mission()
    route = _route()
    poi_manager = POIManager(tmp_path / "pois.json")
    mission_start = BASE
    mission_end = BASE + timedelta(hours=10)
    aar_window = ResolvedAARWindow(
        name="AAR-1",
        start_time=BASE + timedelta(hours=2),
        end_time=BASE + timedelta(hours=3),
    )
    transition_schedule = [(BASE + timedelta(hours=4), "X-2")]

    sync_mission_pois(
        mission,
        route,
        poi_manager,
        mission_start=mission_start,
        mission_end=mission_end,
        aar_windows=[aar_window],
        transition_schedule=transition_schedule,
        coverage=CoverageAnalysisResult(gaps=[], swaps=[]),
    )

    generated = {poi.kind: poi for poi in poi_manager.list_pois(mission_id=mission.id)}
    assert generated["departure"].name == "KADW"
    assert generated["departure"].expected_arrival_time == mission_start
    assert generated["arrival"].name == "RKSO"
    assert generated["arrival"].expected_arrival_time == mission_end
    assert generated["aar_start"].expected_arrival_time == aar_window.start_time
    assert generated["aar_end"].expected_arrival_time == aar_window.end_time
    assert generated["x_band_transition"].expected_arrival_time == transition_schedule[0][0]


def test_sync_mission_pois_replaces_only_generated_kinds(tmp_path):
    mission = _mission()
    route = _route()
    poi_manager = POIManager(tmp_path / "pois.json")
    manual = poi_manager.create_poi(
        POICreate(
            name="AAR\nStart",
            latitude=0,
            longitude=0,
            route_id=mission.route_id,
            mission_id=mission.id,
        )
    )
    sync_kwargs = {
        "mission_start": BASE,
        "mission_end": BASE + timedelta(hours=10),
        "aar_windows": [],
        "transition_schedule": [],
        "coverage": CoverageAnalysisResult(gaps=[], swaps=[]),
    }

    sync_mission_pois(mission, route, poi_manager, **sync_kwargs)
    sync_mission_pois(mission, route, poi_manager, **sync_kwargs)

    generated = [poi for poi in poi_manager.list_pois(mission_id=mission.id) if poi.kind]
    assert {poi.kind for poi in generated} == {"departure", "arrival"}
    assert len(generated) == 2
    assert poi_manager.get_poi(manual.id) is not None


def test_old_persisted_poi_without_generated_fields_loads(tmp_path):
    manager = POIManager(tmp_path / "pois.json")
    manager._pois["legacy"] = POI(id="legacy", name="Legacy", latitude=0, longitude=0)
    manager._save_pois()

    reloaded = POIManager(tmp_path / "pois.json")

    assert reloaded.get_poi("legacy").kind is None
    assert reloaded.get_poi("legacy").expected_arrival_time is None
