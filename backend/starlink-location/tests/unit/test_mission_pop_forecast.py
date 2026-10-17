"""Mission timing and live ETA adapters must preserve existing service decisions."""

from datetime import datetime, timedelta, timezone
from math import pi

import pytest

from app.mission.models import KaOutage, MissionLeg, MissionLegTimeline, TransportConfig
from app.mission.pop_forecast import forecast_for_live, forecast_for_mission
from app.mission.timeline_builder.calculator import (
    RouteTemporalProjector,
    route_with_adjusted_departure,
)
from app.mission.timeline_preparation import prepare_mission_timeline
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint, RouteTimingProfile
from app.services.pop.models import PopCatalog, PopSite
from app.services.route_manager import RouteManager

BASE = datetime(2035, 1, 1, tzinfo=timezone.utc)


def sites(*locations):
    return PopCatalog(
        sites=tuple(
            PopSite(
                id=name,
                city=name,
                country="US",
                latitude=lat,
                longitude=lon,
                source="test",
                coordinate_source="test",
            )
            for name, lat, lon in locations
        ),
        fingerprint="fixture",
    )


def route(longitudes=(-10, 0, 10), minutes=(0, 10, 40)):
    return ParsedRoute(
        metadata=RouteMetadata(
            name="test", file_path="test.kml", point_count=len(longitudes)
        ),
        points=[
            RoutePoint(
                latitude=0,
                longitude=lon,
                sequence=i,
                expected_arrival_time=BASE + timedelta(minutes=minute),
                expected_segment_speed_knots=600,
            )
            for i, (lon, minute) in enumerate(zip(longitudes, minutes))
        ],
        timing_profile=RouteTimingProfile(
            departure_time=BASE,
            arrival_time=BASE + timedelta(minutes=minutes[-1]),
            has_timing_data=True,
        ),
    )


def planned(r, catalog=None, revision="r", enabled=True):
    p = RouteTemporalProjector(
        r, r.timing_profile.departure_time, r.timing_profile.arrival_time
    )
    return forecast_for_mission(
        r,
        p,
        catalog or sites(("a", 0, -5), ("b", 0, 15)),
        revision=revision,
        starshield_enabled=enabled,
    )


def live(r, **kwargs):
    values = {
        "revision": "r",
        "starshield_enabled": True,
        "now": BASE,
        "latitude": 0,
        "longitude": -5,
        "speed_knots": 300,
        "telemetry_valid": True,
    }
    values.update(kwargs)
    return forecast_for_live(r, sites(("a", 0, -5), ("b", 0, 15)), **values)


def test_interior_anchor_and_uniform_departure_shift():
    r = route()
    first = planned(r)
    assert first.status == "ready"
    assert first.transitions[0].crossing_utc == BASE + timedelta(minutes=25)
    shifted = planned(
        route_with_adjusted_departure(r, BASE + timedelta(hours=2)), revision="shifted"
    )
    for field in ("crossing_utc", "window_start_utc", "window_end_utc"):
        assert getattr(shifted.transitions[0], field) - getattr(
            first.transitions[0], field
        ) == timedelta(hours=2)
    assert r.points[1].expected_arrival_time == BASE + timedelta(minutes=10)


def test_dateline_with_unequal_segment_durations_and_duplicate_vertices():
    r = route((170, 170, 179, -170), (0, 0, 9, 42))
    result = planned(r, sites(("a", 0, 170), ("b", 0, -170)))
    assert result.status == "ready"
    assert result.transitions[0].crossing_utc == BASE + timedelta(minutes=12)
    assert abs(result.transitions[0].crossing.longitude) == pytest.approx(180)


def test_disabled_and_valid_no_crossing_are_distinct():
    assert planned(route(), enabled=False).status == "disabled"
    result = planned(route((-10, -9), (0, 10)))
    assert result.status == "ready"
    assert result.transitions == ()


def test_sustained_tie_is_indeterminate():
    result = planned(route(), sites(("a", 10, 0), ("b", -10, 0)))
    assert result.status == "indeterminate"
    assert result.reason
    assert result.transitions == ()


def test_invalid_route_and_superseded_projector_fail_closed():
    r = route()
    p = RouteTemporalProjector(r, BASE, BASE + timedelta(minutes=40))
    changed = route((-10, 0, 9))
    result = forecast_for_mission(
        changed,
        p,
        sites(("a", 0, -5), ("b", 0, 15)),
        revision="new",
        starshield_enabled=True,
    )
    assert result.status == "unavailable"
    assert result.reason
    r.points[0].latitude = float("nan")
    assert (
        forecast_for_mission(
            r, p, sites(("a", 0, -5)), revision="r", starshield_enabled=True
        ).status
        == "unavailable"
    )


def test_missing_catalog_and_invalid_timing_have_explicit_reasons():
    r = route()
    p = RouteTemporalProjector(r, BASE, BASE + timedelta(minutes=40))
    assert (
        forecast_for_mission(r, p, None, revision="r", starshield_enabled=True).status
        == "unavailable"
    )
    p.end_time = BASE
    result = forecast_for_mission(
        r, p, sites(("a", 0, -5)), revision="r", starshield_enabled=True
    )
    assert result.status == "unavailable"
    assert result.reason


def test_live_uses_current_speed_blend_then_future_segment_speed():
    result = live(route())
    assert result.status == "ready"
    # 5 degrees at (300+600)/2 kt, then 5 degrees at 600 kt.
    expected = 6371000 * pi / 36 / 1852 * 3600 * (1 / 450 + 1 / 600)
    assert result.transitions[0].crossing_utc.timestamp() == pytest.approx(
        BASE.timestamp() + expected, abs=0.001
    )
    assert result.transitions[0].crossing_utc != BASE + timedelta(minutes=25)


@pytest.mark.parametrize(
    "changes",
    [
        {"telemetry_valid": False},
        {"speed_knots": 0},
        {"speed_knots": float("nan")},
        {"latitude": float("nan")},
    ],
)
def test_live_invalid_or_stationary_inputs_have_no_forecast(changes):
    result = live(route(), **changes)
    assert result.status == "unavailable"
    assert result.reason
    assert result.transitions == ()


def test_live_off_route_rejected_by_existing_validity_input():
    result = live(route(), latitude=50, telemetry_valid=False)
    assert result.status == "unavailable"
    assert result.transitions == ()


def test_live_ambiguous_reentry_occurrence_is_unavailable():
    result = live(route((-10, 10, -10), (0, 20, 40)))
    assert result.status == "unavailable"
    assert result.reason


def test_live_filters_passed_crossings_without_backward_eta():
    result = live(route(), longitude=7)
    assert result.status == "ready"
    assert result.transitions == ()


def test_old_timeline_defaults_and_mission_revision_recomputation(
    tmp_path, monkeypatch
):
    assert MissionLegTimeline(mission_leg_id="old").pop_forecast is None
    manager = RouteManager(routes_dir=tmp_path / "routes")
    r = route((-100, -70), (0, 40))
    manager.add_route("r", r)
    leg = MissionLeg(
        id="leg",
        name="leg",
        route_id="r",
        transports=TransportConfig(initial_x_satellite_id="X-1"),
    )
    first = prepare_mission_timeline(
        leg, manager, discover_coverage=False
    ).timeline.pop_forecast
    assert first.status == "ready"
    assert first.transitions
    leg.adjusted_departure_time = BASE + timedelta(hours=1)
    second = prepare_mission_timeline(
        leg, manager, discover_coverage=False
    ).timeline.pop_forecast
    assert second.revision != first.revision
    assert second.transitions[0].crossing_utc - first.transitions[
        0
    ].crossing_utc == timedelta(hours=1)


def test_live_dateline_crossing_uses_current_occurrence_and_eta():
    r = route((170, 179, -160), (0, 9, 72))
    result = forecast_for_live(
        r,
        sites(("a", 0, 170), ("b", 0, -160)),
        revision="r",
        starshield_enabled=True,
        now=BASE,
        latitude=0,
        longitude=-179,
        speed_knots=300,
        telemetry_valid=True,
    )
    assert result.status == "ready"
    expected = 6371000 * pi / 45 / 1852 / 450 * 3600
    assert result.transitions[0].crossing_utc.timestamp() == pytest.approx(
        BASE.timestamp() + expected, abs=0.001
    )


def test_forecast_publication_preserves_transport_statistics_and_concurrency(
    tmp_path, monkeypatch
):
    import app.mission.pop_forecast as module
    from app.satellites.catalog import Satellite, SatelliteCatalog
    from app.services.pop.models import PopForecast

    r = route((0, 0), (0, 40))
    r.points[0].latitude, r.points[1].latitude = 10, 10.4
    manager = RouteManager(routes_dir=tmp_path / "routes")
    manager.add_route("r", r)
    catalog = SatelliteCatalog()
    catalog.add_satellite(Satellite("SOUTH", "X", longitude=0))
    monkeypatch.setattr("app.satellites.catalog._catalog", catalog)
    monkeypatch.setattr(
        "app.services.pop.catalog.load_catalog",
        lambda _: sites(("a", 9.9, 0), ("b", 10.5, 0)),
    )
    leg = MissionLeg(
        id="leg",
        name="leg",
        route_id="r",
        transports=TransportConfig(
            initial_x_satellite_id="SOUTH",
            ka_outages=[
                KaOutage(
                    id="real",
                    start_time=BASE + timedelta(minutes=15),
                    duration_seconds=600,
                )
            ],
        ),
    )
    actual_forecast = module.forecast_for_mission
    monkeypatch.setattr(
        module,
        "forecast_for_mission",
        lambda route, projector, catalog, **kw: PopForecast(
            revision=kw["revision"],
            catalog_fingerprint=catalog.fingerprint,
            status="disabled",
        ),
    )
    baseline = prepare_mission_timeline(leg, manager, discover_coverage=False).timeline
    monkeypatch.setattr(module, "forecast_for_mission", actual_forecast)
    result = prepare_mission_timeline(leg, manager, discover_coverage=False).timeline
    assert result.pop_forecast.status == "ready"
    assert len(result.pop_forecast.transitions) == 1
    assert [s.model_dump() for s in result.segments] == [
        s.model_dump() for s in baseline.segments
    ]
    assert result.statistics == baseline.statistics
    assert result.advisories == baseline.advisories
    assert any(s.ka_state.value == "offline" for s in result.segments)
    assert any("conflict" in str(s.model_dump()).lower() for s in result.segments)
    assert all(s.ku_state.value == "available" for s in result.segments)


def test_changed_geometry_and_catalog_replace_revision_and_occurrence_ids(
    tmp_path, monkeypatch
):
    r = route((-100, -70), (0, 40))
    manager = RouteManager(routes_dir=tmp_path / "routes")
    manager.add_route("r", r)
    leg = MissionLeg(
        id="leg",
        name="leg",
        route_id="r",
        transports=TransportConfig(initial_x_satellite_id="X-1"),
    )
    original = prepare_mission_timeline(
        leg, manager, discover_coverage=False
    ).timeline.pop_forecast
    changed = route((-100, -65), (0, 40))
    manager.add_route("r", changed)
    revised = prepare_mission_timeline(
        leg, manager, discover_coverage=False
    ).timeline.pop_forecast
    assert revised.revision != original.revision
    assert {t.crossing.id for t in original.transitions}.isdisjoint(
        t.crossing.id for t in revised.transitions
    )
    catalog = sites(("a", 0, -100), ("b", 0, -65)).model_copy(
        update={"fingerprint": "new-catalog"}
    )
    monkeypatch.setattr("app.services.pop.catalog.load_catalog", lambda _: catalog)
    updated = prepare_mission_timeline(
        leg, manager, discover_coverage=False
    ).timeline.pop_forecast
    assert updated.catalog_fingerprint == "new-catalog"
    assert updated.revision != revised.revision
    assert {t.crossing.id for t in revised.transitions}.isdisjoint(
        t.crossing.id for t in updated.transitions
    )


def test_forecasting_preserves_planning_preference_with_real_ka_outage(monkeypatch):
    from tests.planning.test_policy import START, scenario

    inputs, draft, context, evaluate, manager, *_ = scenario(
        monkeypatch,
        ka_outages=[{"id": "real", "start_time": START, "duration_seconds": 60}],
    )
    before = evaluate(inputs, draft, context)
    r = manager.get_route("owned")
    p = RouteTemporalProjector(r, START, START + timedelta(seconds=60))
    advisory = forecast_for_mission(
        r,
        p,
        sites(("a", 9.999, 0), ("b", 10.011, 0)),
        revision="r",
        starshield_enabled=True,
    )
    after = evaluate(inputs, draft, context)
    assert advisory.status == "ready"
    assert len(advisory.transitions) == 1
    assert after == before
    assert after.intervals[0].policy_x_state == "offline"
    assert after.intervals[0].policy_ku_state == "available"
    assert after.intervals[0].policy_ka_state == "offline"


def test_live_eta_updates_keep_occurrence_ids_for_overdue_tracking():
    initial = live(route())
    updated = live(
        route(), now=BASE + timedelta(minutes=2), longitude=-4, speed_knots=400
    )
    assert initial.transitions[0].crossing.id == updated.transitions[0].crossing.id
    assert initial.transitions[0].crossing_utc != updated.transitions[0].crossing_utc


@pytest.mark.parametrize("enabled,status", [(True, "unavailable"), (False, "disabled")])
def test_invalid_configured_catalog_cannot_publish_old_forecast(
    tmp_path, monkeypatch, enabled, status
):
    def invalid_catalog(_):
        raise ValueError("invalid catalog")

    monkeypatch.setattr("app.services.pop.catalog.load_catalog", invalid_catalog)
    manager = RouteManager(routes_dir=tmp_path / "routes")
    manager.add_route("r", route())
    leg = MissionLeg(
        id="leg",
        name="leg",
        route_id="r",
        transports=TransportConfig(
            initial_x_satellite_id="X-1", starshield_enabled=enabled
        ),
    )
    result = prepare_mission_timeline(
        leg, manager, discover_coverage=False
    ).timeline.pop_forecast
    assert result.status == status
    assert result.transitions == ()
    if enabled:
        assert result.reason


def test_mutated_route_cannot_reuse_obsolete_projector_anchors():
    r = route()
    p = RouteTemporalProjector(r, BASE, BASE + timedelta(minutes=40))
    r.points[1].expected_arrival_time = BASE + timedelta(minutes=20)
    result = forecast_for_mission(
        r, p, sites(("a", 0, -5), ("b", 0, 15)), revision="new", starshield_enabled=True
    )
    assert result.status == "unavailable"
    assert result.transitions == ()
