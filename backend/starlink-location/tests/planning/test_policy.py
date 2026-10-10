"""Real geometry and shared operating policy on finite synthetic routes."""

import importlib.util
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.mission.planning.models import ExpectedLeg, PlanningDraft, RouteBinding
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint, RouteTimingProfile
from app.satellites.catalog import Satellite, SatelliteCatalog
from app.satellites.rules import ConstraintConfig

START = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)


def planning_api():
    assert importlib.util.find_spec(
        "app.mission.planning.inputs"
    ), "Shared input capture is missing"
    from app.mission.planning.evaluate import evaluate_context
    from app.mission.planning.grid import build_context
    from app.mission.planning.inputs import build_inputs

    return build_inputs, build_context, evaluate_context


def scenario(monkeypatch, seconds=60, **draft_changes):
    end = START + timedelta(seconds=seconds)
    route = ParsedRoute(
        route_id="owned",
        content_hash="a" * 64,
        ingestion_profile="planning_v1",
        source_departure_time=START,
        metadata=RouteMetadata(name="Synthetic", file_path="owned.kml", point_count=2),
        points=[
            RoutePoint(
                latitude=lat,
                longitude=0,
                altitude=10000,
                sequence=i,
                occurrence_id=f"p{i}",
                expected_arrival_time=time,
            )
            for i, (lat, time) in enumerate([(10, START), (10.01, end)])
        ],
        timing_profile=RouteTimingProfile(departure_time=START, arrival_time=end),
    )
    catalog = SatelliteCatalog()
    catalog.add_satellite(Satellite("SOUTH", "X", longitude=0))
    catalog.add_satellite(Satellite("WEST", "X", longitude=-30))
    monkeypatch.setattr(
        "app.satellites.catalog.get_satellite_catalog", lambda **kw: catalog
    )
    monkeypatch.setattr(
        "app.mission.planning.service.get_satellite_catalog", lambda **kw: catalog
    )
    # Catalog itself is real; managers are read-only fixture views.
    manager = SimpleNamespace(get_route=lambda _: route)
    pois = SimpleNamespace(find_global_poi_by_name=lambda _: None)
    draft = PlanningDraft(
        permitted_satellite_ids=("SOUTH", "WEST"),
        initial_x_satellite_id="SOUTH",
        **draft_changes,
    )
    leg = ExpectedLeg(
        id="card",
        ordinal=1,
        departure_airport="AAAA",
        arrival_airport="BBBB",
        departure_time=START,
        arrival_time=end,
        route=RouteBinding(
            route_id="owned",
            source_id="source",
            content_hash="a" * 64,
            filename="owned.kml",
        ),
        draft=draft,
    )
    build, grid, evaluate = planning_api()
    inputs = build(leg, draft, manager, pois, ConstraintConfig())
    return inputs, draft, grid(inputs, draft), evaluate, manager, pois, leg


def test_ku_preference_counts_conflict_shutdown(monkeypatch):
    inputs, draft, context, evaluate, *_ = scenario(monkeypatch)
    result = evaluate(inputs, draft, context)
    assert result.outage_seconds == 60
    assert result.intervals[0].physical_x_state == "available"
    assert result.intervals[0].policy_x_state == "offline"
    assert "x_aft_cone" in result.intervals[0].raw_constraints
    assert result.intervals[0].policy_ku_state == "available"


@pytest.mark.parametrize(
    "enabled,overrides",
    [(False, []), (True, [{"id": "ku", "start_time": START, "duration_seconds": 60}])],
)
def test_ku_outage_or_disabled_releases_only_concurrency_constraint(
    monkeypatch, enabled, overrides
):
    inputs, draft, context, evaluate, *_ = scenario(
        monkeypatch, starshield_enabled=enabled, ku_overrides=overrides
    )
    result = evaluate(inputs, draft, context)
    assert result.outage_seconds == 0
    assert result.intervals[0].physical_x_state == "available"
    assert result.intervals[0].policy_x_state == "available"
    assert result.intervals[0].policy_ku_state == "offline"
    assert "x_aft_cone" in result.intervals[0].raw_constraints


def test_safety_advice_adds_no_outage(monkeypatch):
    inputs, draft, context, evaluate, *_ = scenario(
        monkeypatch, starshield_enabled=False
    )
    result = evaluate(inputs, draft, context)
    assert result.outage_seconds == 0
    assert result.intervals[0].safety_reasons


def test_missing_satellite_position_rejected(monkeypatch):
    scenario(monkeypatch)
    from app.mission.planning.inputs import build_inputs

    _inputs, draft, _, _, manager, pois, leg = scenario(monkeypatch)
    draft.permitted_satellite_ids = ("MISSING",)
    draft.initial_x_satellite_id = "MISSING"
    with pytest.raises(ValueError, match="position"):
        build_inputs(leg, draft, manager, pois, ConstraintConfig())


def test_ar_half_open_height_and_geometry(monkeypatch):
    from app.mission.planning.match import _candidates
    from app.mission.planning.models import ItineraryAR

    inputs, draft, _, evaluate, manager, pois, leg = scenario(
        monkeypatch, seconds=120, starshield_enabled=False
    )
    route = manager.get_route("owned")
    entry, exit = START + timedelta(seconds=30), START + timedelta(seconds=90)
    draft.ar_corrections = [
        ItineraryAR(
            id="ar",
            track="Synthetic",
            entry_time=entry,
            exit_time=exit,
            source_time_precision="second",
            start_anchor=_candidates(entry, "second", route)[0],
            end_anchor=_candidates(exit, "second", route)[0],
            match_status="matched",
            source_altitude=210,
            confirmed_units="flight_level",
        )
    ]
    build, grid, _ = planning_api()
    inputs = build(leg, draft, manager, pois, ConstraintConfig())
    monkeypatch.setattr(
        "app.mission.planning.evaluate.look_angles", lambda *args: (0, 50)
    )
    context = grid(inputs, draft)
    result = evaluate(inputs, draft, context)
    at = {i.start_time: i for i in result.intervals}
    assert result.outage_seconds == 60
    assert at[entry].altitude_meters == pytest.approx(6400.8)
    assert at[entry].policy_x_state == "degraded"
    assert at[exit].altitude_meters == 10000
    assert at[exit].policy_x_state == "available"
    assert any("pressure-altitude" in a for a in context.assumptions)
    from app.mission.planning.inputs import draft_to_mission_leg
    from app.mission.timeline_preparation import prepare_mission_timeline

    mission = draft_to_mission_leg(inputs, draft, context, leg_id="installed")
    artifacts = prepare_mission_timeline(
        mission, manager, pois, include_samples=True, discover_coverage=False
    )
    assert artifacts.planning_evaluation == result
    assert next(
        s for s in artifacts.timeline.samples if s.timestamp == entry
    ).altitude == pytest.approx(6400.8)


def test_ku_release_does_not_release_elevation(monkeypatch):
    inputs, draft, context, evaluate, *_ = scenario(
        monkeypatch, starshield_enabled=False
    )
    monkeypatch.setattr(
        "app.mission.planning.evaluate.look_angles", lambda *args: (180, 5)
    )
    result = evaluate(inputs, draft, context)
    assert result.outage_seconds == 60
    assert result.intervals[0].raw_constraints == ["x_aft_cone", "x_elevation"]
    assert result.intervals[0].physical_x_state == "degraded"


def test_manual_overlay_blocks_without_ku(monkeypatch):
    from app.mission.models import ManualAARTrack

    track = ManualAARTrack(
        id="track",
        name="Track",
        points=[
            {"latitude": 10.0025, "longitude": 0},
            {"latitude": 10.0075, "longitude": 0},
        ],
    )
    inputs, draft, context, evaluate, *_ = scenario(
        monkeypatch, seconds=120, starshield_enabled=False, manual_aar_tracks=[track]
    )
    result = evaluate(inputs, draft, context)
    assert result.outage_seconds == pytest.approx(60, abs=0.001)
    assert any("manual_ar:track" in i.raw_constraints for i in result.intervals)


def test_fallback_and_unknown_ar_units_are_disclosed(monkeypatch):
    from app.mission.planning.match import _candidates
    from app.mission.planning.models import ItineraryAR

    inputs, draft, _, evaluate, manager, pois, leg = scenario(
        monkeypatch, seconds=120, starshield_enabled=False
    )
    route = manager.get_route("owned")
    for point in route.points:
        point.altitude = None
    draft.ar_corrections = [
        ItineraryAR(
            id="ar",
            track="Unknown units",
            entry_time=START,
            exit_time=leg.arrival_time,
            source_time_precision="second",
            start_anchor=_candidates(START, "second", route)[0],
            end_anchor=_candidates(leg.arrival_time, "second", route)[0],
            match_status="matched",
            source_altitude=210,
        )
    ]
    build, grid, _ = planning_api()
    inputs = build(leg, draft, manager, pois, ConstraintConfig())
    context = grid(inputs, draft)
    result = evaluate(inputs, draft, context)
    assert result.errors and result.errors[0].code == "unresolved_ar"
    assert all(i.altitude_meters == 10668 for i in result.intervals)
    assert any("cruise" in a for a in context.assumptions)


def test_live_policy_releases_concurrency_with_disabled_ku(monkeypatch):
    from app.services.active_x_link import _evaluate_link_state
    from tests.unit.test_active_x_handoff import _satellite, _telemetry

    inputs, draft, context, *_ = scenario(monkeypatch, starshield_enabled=False)
    from app.mission.planning.inputs import draft_to_mission_leg

    mission = draft_to_mission_leg(inputs, draft, context, leg_id="installed")
    telemetry = _telemetry(10, 0, 0, START)
    state, _, _, raw = _evaluate_link_state(
        telemetry, _satellite("SOUTH", 0), mission=mission
    )
    assert raw is True
    assert state == "normal"


def test_longest_outage_ignores_safety_only_call_gaps(monkeypatch):
    inputs, draft, context, evaluate, *_ = scenario(
        monkeypatch, starshield_enabled=False
    )
    result = evaluate(inputs, draft, context)
    assert result.outage_seconds == 0
    assert result.longest_gap_seconds == 0
    assert not result.backup_gaps  # Safety remains advice, not an RF backup gap.


def test_backup_gaps_count_ka_as_a_remaining_transport(monkeypatch):
    from app.mission import timeline_service
    from app.satellites.coverage import CoverageSampler

    coverage = CoverageSampler.from_geojson(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"satellite_id": "AOR"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[-5, 5], [5, 5], [5, 15], [-5, 15], [-5, 5]]],
                    },
                }
            ],
        }
    )
    monkeypatch.setattr(timeline_service, "_COVERAGE_SAMPLER", coverage)
    inputs, draft, context, evaluate, *_ = scenario(monkeypatch)
    result = evaluate(inputs, draft, context)
    assert result.outage_seconds == 60
    assert result.backup_gaps == []  # Ka and preferred Ku remain usable.
    inputs, draft, context, evaluate, *_ = scenario(
        monkeypatch,
        starshield_enabled=False,
        ka_outages=[{"id": "ka", "start_time": START, "duration_seconds": 60}],
    )
    result = evaluate(inputs, draft, context)
    assert result.outage_seconds == result.longest_gap_seconds == 0
    assert len(result.backup_gaps) == 1  # Only X remains usable.


def test_partial_route_height_uses_valid_endpoint_before_cruise(monkeypatch):
    from app.mission.planning.grid import build_context
    from app.mission.planning.inputs import build_inputs

    inputs, draft, _, evaluate, manager, pois, leg = scenario(monkeypatch)
    manager.get_route("owned").points[0].altitude = None
    inputs = build_inputs(leg, draft, manager, pois, ConstraintConfig())
    context = build_context(inputs, draft)
    assert evaluate(inputs, draft, context).intervals[0].altitude_meters == 10000
    assert context.height_profile[0].source == "route"


def test_live_elevation_warning_does_not_invent_concurrency(monkeypatch):
    from app.mission.planning.inputs import draft_to_mission_leg
    from app.services.active_x_link import _evaluate_link_state
    from tests.unit.test_active_x_handoff import _satellite, _telemetry

    inputs, draft, context, *_ = scenario(monkeypatch, starshield_enabled=False)
    leg = draft_to_mission_leg(inputs, draft, context, leg_id="installed")
    monkeypatch.setattr("app.satellites.rules.look_angles", lambda *args: (90, 5))
    state, _, _, raw = _evaluate_link_state(
        _telemetry(10, 0, 0, START), _satellite("SOUTH", 0), mission=leg
    )
    assert state == "warning"
    assert raw is False
