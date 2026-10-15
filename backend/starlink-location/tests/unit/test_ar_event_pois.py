"""AR and transport map cues use the resolved mission route and timing."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.mission.models import (
    AARWindow,
    KaOutage,
    KuOutageOverride,
    ManualAARTrack,
    MissionLeg,
    TransportConfig,
)
from app.mission.timeline_builder.aar import ResolvedAARWindow
from app.mission.timeline_builder.coverage import CoverageAnalysisResult
from app.mission.timeline_builder.pois import construct_mission_pois, sync_mission_pois
from app.mission.timeline_preparation import prepare_mission_timeline
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint, RouteWaypoint
from app.services.poi_manager import POIManager

BASE = datetime(2026, 10, 14, 12, tzinfo=timezone.utc)


def route():
    return ParsedRoute(
        metadata=RouteMetadata(name="Route", file_path="route.kml", point_count=2),
        points=[
            RoutePoint(latitude=0, longitude=0, sequence=0),
            RoutePoint(latitude=0, longitude=10, sequence=1),
        ],
        waypoints=[],
    )


def mission(**changes):
    return MissionLeg(
        id="leg",
        name="Leg",
        route_id="route",
        transports=TransportConfig(initial_x_satellite_id="X-1", **changes),
    )


def construct(leg, source_route=None, windows=()):
    return construct_mission_pois(
        leg,
        source_route or route(),
        mission_start=BASE,
        mission_end=BASE + timedelta(hours=10),
        aar_windows=windows,
        transition_schedule=[],
        coverage=CoverageAnalysisResult(gaps=[], swaps=[]),
    )


def test_resolved_ar_without_named_waypoints_generates_both_boundaries():
    leg = mission(
        aar_windows=[
            AARWindow(
                id="ar",
                start_waypoint_name="missing start",
                end_waypoint_name="missing end",
            )
        ]
    )
    cues = {
        p.kind: p
        for p in construct(
            leg,
            windows=[
                ResolvedAARWindow(
                    name="ar",
                    start_time=BASE + timedelta(hours=2),
                    end_time=BASE + timedelta(hours=3),
                )
            ],
        )
    }
    assert cues["aar_start"].longitude == pytest.approx(2)
    assert cues["aar_end"].longitude == pytest.approx(3)
    assert cues["aar_start"].expected_arrival_time == BASE + timedelta(hours=2)
    assert cues["aar_end"].expected_arrival_time == BASE + timedelta(hours=3)


def test_ar_time_override_moves_map_cues_to_effective_route_positions():
    source = route()
    source.waypoints = [
        RouteWaypoint(name="start", latitude=0, longitude=1, order=0),
        RouteWaypoint(name="end", latitude=0, longitude=2, order=1),
    ]
    leg = mission(
        aar_windows=[
            AARWindow(
                id="ar",
                start_waypoint_name="start",
                end_waypoint_name="end",
                override_start_elapsed="T+04:00",
            )
        ]
    )
    cues = {
        p.kind: p
        for p in construct(
            leg,
            source,
            [
                ResolvedAARWindow(
                    name="ar",
                    start_time=BASE + timedelta(hours=4),
                    end_time=BASE + timedelta(hours=5),
                )
            ],
        )
    }
    assert cues["aar_start"].longitude == pytest.approx(4)
    assert cues["aar_end"].longitude == pytest.approx(5)


def test_manual_ar_pois_follow_temporal_order_and_resync_without_duplicates(tmp_path):
    leg = mission(
        manual_aar_tracks=[
            ManualAARTrack(
                id="track",
                name="Refuel",
                points=[
                    {"latitude": 0, "longitude": 7},
                    {"latitude": 0, "longitude": 2},
                ],
            )
        ]
    )
    store = POIManager(tmp_path / "pois.json")
    for _ in range(2):
        sync_mission_pois(
            leg,
            route(),
            store,
            mission_start=BASE,
            mission_end=BASE + timedelta(hours=10),
            aar_windows=[],
            transition_schedule=[],
            coverage=CoverageAnalysisResult(gaps=[], swaps=[]),
        )
    cues = {p.kind: p for p in store.list_pois(mission_id="leg")}
    assert len(store.list_pois(mission_id="leg")) == 4
    assert cues["aar_start"].longitude == pytest.approx(2)
    assert cues["aar_end"].longitude == pytest.approx(7)
    assert cues["aar_start"].expected_arrival_time == BASE + timedelta(hours=2)
    assert cues["aar_end"].expected_arrival_time == BASE + timedelta(hours=7)
    leg.transports.manual_aar_tracks = []
    sync_mission_pois(
        leg,
        route(),
        store,
        mission_start=BASE,
        mission_end=BASE + timedelta(hours=10),
        aar_windows=[],
        transition_schedule=[],
        coverage=CoverageAnalysisResult(gaps=[], swaps=[]),
    )
    assert {p.kind for p in store.list_pois(mission_id="leg")} == {
        "departure",
        "arrival",
    }


def test_degenerate_manual_ar_track_does_not_invent_an_operation():
    leg = mission(
        manual_aar_tracks=[
            ManualAARTrack(
                id="track",
                name="Off route",
                points=[
                    {"latitude": 1, "longitude": -2},
                    {"latitude": 2, "longitude": -3},
                ],
            )
        ]
    )
    assert {p.kind for p in construct(leg)} == {"departure", "arrival"}


@pytest.mark.parametrize(
    "transport, outage_type, prefix",
    [
        ("ku_overrides", KuOutageOverride, "starshield"),
        ("ka_outages", KaOutage, "ka"),
    ],
)
def test_outage_pois_merge_overlaps_and_ignore_outside_mission(
    transport, outage_type, prefix
):
    outages = [
        outage_type(
            id=str(i),
            start_time=BASE + timedelta(hours=start),
            duration_seconds=duration * 3600,
        )
        for i, (start, duration) in enumerate([(2, 2), (3, 2), (-2, 1), (11, 1)])
    ]
    cues = {p.kind: p for p in construct(mission(**{transport: outages}))}
    assert cues[f"{prefix}_outage_start"].longitude == pytest.approx(2)
    assert cues[f"{prefix}_outage_end"].longitude == pytest.approx(5)
    assert len(cues) == 4


def test_timeline_preview_exposes_the_same_resolved_pois_as_persistence():
    source = route()
    source.points[0].expected_arrival_time = BASE
    source.points[-1].expected_arrival_time = BASE + timedelta(hours=10)
    leg = mission(
        ku_overrides=[
            KuOutageOverride(
                id="outage",
                start_time=BASE + timedelta(hours=2),
                duration_seconds=3600,
            )
        ]
    )
    artifacts = prepare_mission_timeline(
        leg,
        SimpleNamespace(get_route=lambda route_id: source),
        discover_coverage=False,
    )
    payload = artifacts.timeline.model_dump(mode="json")
    cues = {p["kind"]: p for p in payload["map_pois"]}
    assert cues["starshield_outage_start"]["longitude"] == pytest.approx(2)
    assert cues["starshield_outage_end"]["longitude"] == pytest.approx(3)
    assert (
        cues["starshield_outage_start"]["expected_arrival_time"]
        == "2026-10-14T14:00:00Z"
    )


def test_reactivating_loop_route_keeps_timed_event_visit(tmp_path):
    source = route()
    source.points = [
        RoutePoint(
            latitude=0,
            longitude=lon,
            sequence=i,
            expected_arrival_time=BASE + timedelta(hours=i),
        )
        for i, lon in enumerate([0, 10, 0, 10])
    ]
    leg = mission(
        aar_windows=[
            AARWindow(
                id="ar", start_waypoint_name="missing", end_waypoint_name="missing"
            )
        ],
        ku_overrides=[
            KuOutageOverride(
                id="ku", start_time=BASE + timedelta(hours=2.5), duration_seconds=360
            )
        ],
        ka_outages=[
            KaOutage(
                id="ka", start_time=BASE + timedelta(hours=2.5), duration_seconds=360
            )
        ],
    )
    store = POIManager(tmp_path / "pois.json")
    sync_mission_pois(
        leg,
        source,
        store,
        mission_start=BASE,
        mission_end=BASE + timedelta(hours=3),
        aar_windows=[
            ResolvedAARWindow(
                name="ar",
                start_time=BASE + timedelta(hours=2.5),
                end_time=BASE + timedelta(hours=2.6),
            )
        ],
        transition_schedule=[],
        coverage=CoverageAnalysisResult(gaps=[], swaps=[]),
    )
    store = POIManager(tmp_path / "pois.json")
    store.clear_poi_projections()
    store.calculate_poi_projections(source)
    cues = {p.kind: p for p in store.list_pois()}
    for kind in [
        "aar_start",
        "aar_end",
        "ka_outage_start",
        "ka_outage_end",
        "starshield_outage_start",
        "starshield_outage_end",
    ]:
        assert cues[kind].projected_waypoint_index == 2
        assert cues[kind].projected_route_progress > 80


@pytest.mark.parametrize(
    "field, outage_type, state_field, prefix",
    [
        ("ku_overrides", KuOutageOverride, "ku_state", "starshield"),
        ("ka_outages", KaOutage, "ka_state", "ka"),
    ],
)
def test_map_restoration_matches_timeline_for_overlapping_outages(
    field, outage_type, state_field, prefix
):
    source = route()
    source.points[0].expected_arrival_time = BASE
    source.points[-1].expected_arrival_time = BASE + timedelta(hours=10)
    leg = mission(
        **{
            field: [
                outage_type(
                    id="first",
                    start_time=BASE + timedelta(hours=2),
                    duration_seconds=7200,
                ),
                outage_type(
                    id="second",
                    start_time=BASE + timedelta(hours=3),
                    duration_seconds=7200,
                ),
            ]
        }
    )
    artifacts = prepare_mission_timeline(
        leg, SimpleNamespace(get_route=lambda route_id: source), discover_coverage=False
    )
    segment = next(
        s
        for s in artifacts.timeline.segments
        if s.start_time <= BASE + timedelta(hours=4.5) < s.end_time
    )
    assert getattr(segment, state_field) == "offline"
    restored = next(
        p for p in artifacts.generated_pois if p.kind == f"{prefix}_outage_end"
    )
    assert restored.expected_arrival_time == BASE + timedelta(hours=5)
