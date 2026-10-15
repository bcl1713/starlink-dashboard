"""Planned X-band shutdown cues use real route and satellite geometry."""

from datetime import datetime, timedelta, timezone

import pytest

from app.mission.models import (
    AARWindow,
    ManualAARTrack,
    ManualAARTrackPoint,
    ManualRouteSplice,
    MissionLeg,
    TransportConfig,
    XTransition,
)
from app.mission.timeline_preparation import (
    prepare_mission_timeline,
    publish_mission_pois,
)
from app.models.poi import POICreate
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint, RouteTimingProfile
from app.satellites.catalog import Satellite, SatelliteCatalog
from app.services.overview_upcoming_pois import project_overview_upcoming_pois
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager

BASE = datetime(2035, 3, 1, tzinfo=timezone.utc)


def prepare(
    tmp_path,
    monkeypatch,
    *,
    latitudes=(30, 31, 30, 31, 30),
    satellite_longitude=0,
    aar=False,
    transition_longitude=None,
    initial_satellite="X-test",
    departure=None,
    longitudes=None,
    aar_end_minute=8,
    manual_ar=None,
    diversion=False,
):
    route = ParsedRoute(
        metadata=RouteMetadata(
            name="Warning turns", file_path="turns.kml", point_count=len(latitudes)
        ),
        timing_profile=RouteTimingProfile(
            departure_time=BASE,
            arrival_time=BASE + timedelta(minutes=2 * (len(latitudes) - 1)),
            has_timing_data=True,
        ),
        points=[
            RoutePoint(
                latitude=lat,
                longitude=longitudes[i] if longitudes else 0,
                altitude=10000,
                sequence=i,
                expected_arrival_time=BASE + timedelta(minutes=2 * i),
            )
            for i, lat in enumerate(latitudes)
        ],
    )
    routes = RouteManager(routes_dir=tmp_path / "routes")
    routes.add_route("turns", route)
    catalog = SatelliteCatalog()
    catalog.add_satellite(Satellite("X-test", "X", longitude=satellite_longitude))
    monkeypatch.setattr("app.satellites.catalog._catalog", catalog)
    transports = TransportConfig(initial_x_satellite_id=initial_satellite)
    if manual_ar:
        transports.manual_aar_tracks = [
            ManualAARTrack(
                id="manual-ar",
                name="Manual AR",
                points=[
                    ManualAARTrackPoint(
                        latitude=lat, longitude=0.01 if diversion else 0
                    )
                    for lat in manual_ar
                ],
            )
        ]
        if diversion:
            transports.manual_route_splice = ManualRouteSplice(
                enabled_track_id="manual-ar", speed_knots=100
            )
    if aar:
        transports.aar_windows = [
            AARWindow(
                id="aar",
                start_waypoint_name="IN",
                end_waypoint_name="OUT",
                override_start_time=BASE,
                override_end_time=BASE + timedelta(minutes=aar_end_minute),
            )
        ]
    if transition_longitude is not None:
        catalog.add_satellite(Satellite("X-next", "X", longitude=transition_longitude))
        transports.x_transitions = [
            XTransition(
                id="swap", latitude=31.5, longitude=0, target_satellite_id="X-next"
            )
        ]
    leg = MissionLeg(
        id="leg",
        name="Leg",
        route_id="turns",
        transports=transports,
        adjusted_departure_time=departure,
    )
    manager = POIManager(tmp_path / "pois.json")
    artifacts = prepare_mission_timeline(
        leg, routes, manager, parent_mission_id="parent"
    )
    return artifacts, manager


def boundaries(artifacts):
    return [
        poi
        for poi in artifacts.generated_pois
        if poi.kind and poi.kind.startswith("x_band_warning_")
    ]


def test_interference_turns_generate_shutdown_and_turn_on_pois(tmp_path, monkeypatch):
    artifacts, _ = prepare(tmp_path, monkeypatch)
    pois = boundaries(artifacts)
    assert [poi.kind for poi in pois] == [
        "x_band_warning_start",
        "x_band_warning_end",
    ] * 2
    # Departure has no planned heading; the first evaluable sample is minute 1.
    assert [poi.expected_arrival_time for poi in pois] == [
        BASE + timedelta(minutes=m) for m in (1, 3, 5, 7)
    ]
    assert [(poi.latitude, poi.longitude) for poi in pois] == [(30.5, 0)] * 4
    assert all(poi.mission_id == "parent" and poi.route_id == "turns" for poi in pois)
    assert all("X-test" in poi.description for poi in pois)
    assert [poi.name for poi in pois] == ["X-Band Shut Down", "X-Band Turn On"] * 2


@pytest.mark.parametrize(
    "initial_satellite,satellite_longitude,latitudes",
    [
        ("", 0, (30, 31)),
        ("missing", 0, (30, 31)),
    ],
)
def test_missing_satellite_does_not_generate_warning_pois(
    tmp_path, monkeypatch, initial_satellite, satellite_longitude, latitudes
):
    artifacts, _ = prepare(
        tmp_path,
        monkeypatch,
        initial_satellite=initial_satellite,
        satellite_longitude=satellite_longitude,
        latitudes=latitudes,
    )
    assert boundaries(artifacts) == []


@pytest.mark.parametrize(
    "longitude,expected_kinds,minutes",
    [
        (60, ["x_band_warning_start", "x_band_warning_end"], [1, 3]),
        (0, ["x_band_warning_start"], [1]),
    ],
)
def test_satellite_swap_only_generates_poi_when_warning_status_changes(
    tmp_path, monkeypatch, longitude, expected_kinds, minutes
):
    artifacts, _ = prepare(
        tmp_path, monkeypatch, latitudes=(30, 31, 32), transition_longitude=longitude
    )
    pois = boundaries(artifacts)
    assert [poi.kind for poi in pois] == expected_kinds
    assert [poi.expected_arrival_time for poi in pois] == [
        BASE + timedelta(minutes=m) for m in minutes
    ]


def test_regeneration_replaces_warning_pois_and_preserves_manual_pois(
    tmp_path, monkeypatch
):
    artifacts, manager = prepare(tmp_path, monkeypatch)
    publish_mission_pois(artifacts, manager, "parent", "turns")
    manual = manager.create_poi(
        POICreate(
            name="Manual note",
            latitude=30,
            longitude=0,
            mission_id="parent",
            route_id="turns",
            kind="x_band_warning_start",
        )
    )
    assert len(boundaries(artifacts)) == 4
    for poi in artifacts.generated_pois:
        poi.expected_arrival_time += timedelta(hours=1)
    publish_mission_pois(artifacts, manager, "parent", "turns")
    reloaded = POIManager(tmp_path / "pois.json")
    generated = [
        poi
        for poi in reloaded.list_pois()
        if poi.kind
        and poi.kind.startswith("x_band_warning_")
        and poi.generated_source == "mission-timeline"
    ]
    assert len(generated) == 4
    assert all(poi.generated_source == "mission-timeline" for poi in generated)
    assert sorted(poi.expected_arrival_time for poi in generated) == [
        BASE + timedelta(hours=1, minutes=m) for m in (1, 3, 5, 7)
    ]
    assert reloaded.get_poi(manual.id) is not None


def test_departure_adjustment_shifts_interference_schedule(tmp_path, monkeypatch):
    artifacts, _ = prepare(tmp_path, monkeypatch, departure=BASE + timedelta(hours=1))
    assert [poi.expected_arrival_time for poi in boundaries(artifacts)] == [
        BASE + timedelta(hours=1, minutes=m) for m in (1, 3, 5, 7)
    ]


def test_low_elevation_generates_shutdown_until_elevation_recovers(
    tmp_path, monkeypatch
):
    artifacts, _ = prepare(
        tmp_path,
        monkeypatch,
        latitudes=(0, 0, 0),
        longitudes=(-5, 0, 5),
        satellite_longitude=72,
    )
    pois = boundaries(artifacts)
    assert [poi.kind for poi in pois] == ["x_band_warning_start", "x_band_warning_end"]
    assert [poi.expected_arrival_time for poi in pois] == [
        BASE + timedelta(minutes=m) for m in (1, 3)
    ]
    assert "elevation" in pois[0].description.lower()


def test_ar_forward_sector_generates_shutdown_and_turn_on_pois(tmp_path, monkeypatch):
    artifacts, _ = prepare(
        tmp_path, monkeypatch, latitudes=(31, 30, 29, 28), aar=True, aar_end_minute=2
    )
    pois = boundaries(artifacts)
    assert [poi.kind for poi in pois] == ["x_band_warning_start", "x_band_warning_end"]
    assert [poi.expected_arrival_time for poi in pois] == [
        BASE + timedelta(minutes=m) for m in (1, 3)
    ]
    assert "AR" in pois[0].description


def test_overlapping_ar_and_interference_do_not_generate_false_turn_on(
    tmp_path, monkeypatch
):
    artifacts, _ = prepare(tmp_path, monkeypatch, aar=True, aar_end_minute=6)
    pois = boundaries(artifacts)
    assert [poi.kind for poi in pois] == ["x_band_warning_start", "x_band_warning_end"]
    assert [poi.expected_arrival_time for poi in pois] == [
        BASE + timedelta(minutes=m) for m in (1, 7)
    ]


def test_landing_does_not_fabricate_clear_when_warning_remains(tmp_path, monkeypatch):
    artifacts, _ = prepare(tmp_path, monkeypatch, aar=True)
    assert [poi.kind for poi in boundaries(artifacts)] == ["x_band_warning_start"]


def test_repeated_route_locations_keep_future_cues_after_reprojection(
    tmp_path, monkeypatch
):
    artifacts, manager = prepare(tmp_path, monkeypatch)
    publish_mission_pois(artifacts, manager, "parent", "turns")
    manager = POIManager(tmp_path / "pois.json")
    manager.clear_poi_projections()
    # A different effective route can retain the same source route identifier.
    changed_basis = artifacts.route.model_copy(deep=True)
    changed_basis.points = changed_basis.points[:2]
    manager.calculate_poi_projections(changed_basis)
    assert all(
        poi.projected_waypoint_index == 0
        for poi in manager.list_pois()
        if poi.kind and poi.kind.startswith("x_band_warning_")
    )
    other_route = artifacts.route.model_copy(deep=True)
    other_route.metadata.file_path = "other-route.kml"
    other_route.points = other_route.points[:2]
    manager.calculate_poi_projections(other_route)
    manager = POIManager(tmp_path / "pois.json")
    manager.calculate_poi_projections(artifacts.route)
    cues = sorted(
        (
            poi
            for poi in manager.list_pois()
            if poi.kind and poi.kind.startswith("x_band_warning_")
        ),
        key=lambda poi: poi.expected_arrival_time,
    )
    assert [poi.projected_route_progress for poi in cues] == pytest.approx(
        [12.5, 37.5, 62.5, 87.5]
    )
    assert [poi.projected_waypoint_index for poi in cues] == [0, 1, 2, 3]
    projected = project_overview_upcoming_pois(
        pois=cues,
        eta_results={},
        flight_phase="in_flight",
        current_progress=20,
        calculated_at=BASE,
    )
    assert [poi.expected_arrival_time for poi in projected.pois if poi.upcoming] == [
        BASE + timedelta(minutes=m) for m in (3, 5, 7)
    ]


@pytest.mark.parametrize("diversion", [False, True])
def test_manual_ar_tracks_generate_shutdown_and_turn_on(
    tmp_path, monkeypatch, diversion
):
    artifacts, manager = prepare(
        tmp_path,
        monkeypatch,
        latitudes=(31, 30, 29, 28),
        manual_ar=(30.5, 29.5),
        diversion=diversion,
    )
    pois = boundaries(artifacts)
    assert [poi.kind for poi in pois] == ["x_band_warning_start", "x_band_warning_end"]
    assert "Manual AR" in pois[0].description
    if not diversion:
        assert [poi.expected_arrival_time for poi in pois] == [
            BASE + timedelta(minutes=m) for m in (1, 3)
        ]
    else:
        assert any(point.longitude != 0 for point in artifacts.route.points)
        publish_mission_pois(artifacts, manager, "parent", "turns")
        source = artifacts.route.model_copy(deep=True)
        source.points = [
            RoutePoint(latitude=lat, longitude=0, altitude=10000, sequence=i)
            for i, lat in enumerate((31, 30, 29, 28))
        ]
        manager.clear_poi_projections()
        manager.calculate_poi_projections(source)
        cues = sorted(
            (
                poi
                for poi in manager.list_pois()
                if poi.kind and poi.kind.startswith("x_band_warning_")
            ),
            key=lambda poi: poi.expected_arrival_time,
        )
        assert [poi.projected_waypoint_index for poi in cues] == [0, 1]


def test_interference_clear_during_manual_ar_does_not_generate_turn_on(
    tmp_path, monkeypatch
):
    artifacts, _ = prepare(
        tmp_path, monkeypatch, latitudes=(30, 31, 30, 29), manual_ar=(30.5, 29.5)
    )
    pois = boundaries(artifacts)
    assert [poi.kind for poi in pois] == ["x_band_warning_start", "x_band_warning_end"]
    assert [poi.expected_arrival_time for poi in pois] == [
        BASE + timedelta(minutes=m) for m in (1, 5)
    ]
