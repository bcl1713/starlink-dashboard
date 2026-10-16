"""Status consumes captured call evidence only on a matching mission clock."""

import pytest

from tests.unit.test_mission_pop_continuity import timeline


def prepared_status_inputs():
    from app.mission.pop_capabilities import capture_call_capabilities
    from app.mission.pop_forecast import forecast_for_mission, mission_forecast_revision
    from app.mission.timeline_builder.calculator import RouteTemporalProjector
    from tests.unit.test_mission_pop_forecast import route, sites

    r, catalog = route(), sites(("a", 0, -5), ("b", 0, 15))
    p = RouteTemporalProjector(
        r, r.timing_profile.departure_time, r.timing_profile.arrival_time
    )
    t = timeline(raw=("x_elevation",), physical="degraded", x="degraded")
    t.pop_forecast = forecast_for_mission(
        r,
        p,
        catalog,
        revision=mission_forecast_revision(r, p, catalog),
        starshield_enabled=True,
    )
    t.segments[0].start_time, t.segments[0].end_time = p.start_time, p.end_time
    i = t.segments[0].metadata["planning_interval"]
    i.update(start_time=p.start_time.isoformat(), end_time=p.end_time.isoformat())
    return r, catalog, p, t, capture_call_capabilities(t, r, p)


def test_status_captured_mission_clock_counts_and_completion_clears():
    from datetime import timedelta

    from app.mission.pop_status import PopStatusService
    from tests.integration.test_pop_status import known, telemetry

    r, catalog, p, t, captured = prepared_status_inputs()
    service = PopStatusService(observation_provider=lambda *args: known("a"))
    kwargs = {
        "route": r,
        "catalog": catalog,
        "enabled": True,
        "mode": "simulation",
        "now": p.start_time,
        "observed_now": p.start_time,
        "projector": p,
        "call_capabilities": captured,
        "lifecycle_token": "run",
    }
    first = service.snapshot(telemetry(), **kwargs)
    assert first["call_continuity"]["pop_call_outage_seconds"] == 600
    service.observation_provider = lambda *args: known("b", source="simulation")
    complete = service.snapshot(telemetry(), **kwargs)
    assert complete["call_continuity"]["pop_call_outage_seconds"] == 0
    assert t.pop_forecast.transitions[0].window_end_utc == p.start_time + timedelta(
        minutes=30
    )
    service.observation_provider = lambda *args: known("a", source="simulation")
    reset = service.snapshot(telemetry(), **dict(kwargs, lifecycle_token="reset"))
    assert reset["call_continuity"]["pop_call_outage_seconds"] == 600


@pytest.mark.parametrize("change", ["route", "live_clock", "input"])
def test_status_rejects_stale_or_misaligned_capability(change):
    from dataclasses import replace

    from app.mission.pop_status import PopStatusService
    from tests.integration.test_pop_status import telemetry
    from tests.unit.test_mission_pop_forecast import route

    r, catalog, p, _, captured = prepared_status_inputs()
    kwargs = {
        "route": r,
        "catalog": catalog,
        "enabled": True,
        "mode": "simulation",
        "now": p.start_time,
        "observed_now": p.start_time,
        "projector": p,
        "call_capabilities": captured,
    }
    if change == "route":
        kwargs["route"] = route((-10, 1, 10))
    elif change == "live_clock":
        kwargs.update(projector=None, mode="live")
    else:
        kwargs["call_capabilities"] = replace(captured, capability_revision="stale")
    payload = PopStatusService().snapshot(telemetry(), **kwargs)
    assert payload["call_continuity"] is None


def test_status_missing_capabilities_does_not_report_confirmed_zero():
    from app.mission.pop_status import PopStatusService
    from tests.integration.test_pop_status import CATALOG, NOW, telemetry
    from tests.unit.test_mission_pop_forecast import route

    payload = PopStatusService().snapshot(
        telemetry(), route=route(), catalog=CATALOG, enabled=True, mode="live", now=NOW
    )
    assert payload["pop_forecast"]["status"] == "ready"
    assert payload["call_continuity"] is None


def test_replay_late_entry_preserves_post_center_window():
    from datetime import timedelta

    from app.mission.pop_status import PopStatusService
    from tests.integration.test_pop_status import telemetry

    r, catalog, p, _, captured = prepared_status_inputs()
    payload = PopStatusService().snapshot(
        telemetry(),
        route=r,
        catalog=catalog,
        enabled=True,
        mode="simulation",
        now=p.start_time + timedelta(minutes=26),
        observed_now=p.start_time,
        projector=p,
        call_capabilities=captured,
    )
    assert payload["call_continuity"]["pop_call_outage_seconds"] == 240


def test_overdue_advice_never_extends_fixed_communications_outage():
    from datetime import timedelta

    from app.mission.pop_status import PopStatusService
    from tests.integration.test_pop_status import known, telemetry

    r, catalog, p, _, captured = prepared_status_inputs()
    service = PopStatusService(
        observation_provider=lambda *args: known("a", "simulation")
    )
    kwargs = {
        "route": r,
        "catalog": catalog,
        "enabled": True,
        "mode": "simulation",
        "observed_now": p.start_time,
        "projector": p,
        "call_capabilities": captured,
    }
    service.snapshot(telemetry(), now=p.start_time, **kwargs)
    overdue = service.snapshot(
        telemetry(), now=p.start_time + timedelta(minutes=31), **kwargs
    )
    assert overdue["call_continuity"]["pop_call_outage_seconds"] == 0
    assert "overdue" in {a["kind"] for a in overdue["pop_advisories"]}


def test_saved_predeparture_inputs_reject_transport_edits(tmp_path, monkeypatch):
    from app.mission import storage
    from app.mission.models import MissionLeg, TransportConfig
    from app.mission.pop_capabilities import saved_call_capabilities
    from app.mission.timeline_preparation import prepare_mission_timeline
    from app.services.route_manager import RouteManager
    from tests.unit.test_mission_pop_forecast import route

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    manager = RouteManager(routes_dir=tmp_path / "routes")
    manager.add_route("r", route())
    leg = MissionLeg(
        id="leg",
        name="Leg",
        route_id="r",
        transports=TransportConfig(initial_x_satellite_id="X-1"),
    )
    artifacts = prepare_mission_timeline(leg, manager, discover_coverage=False)
    storage.save_mission_timeline(leg.id, artifacts.timeline, "mission")
    captured = saved_call_capabilities(leg, "mission", artifacts.route)
    assert captured is not None
    assert captured.input_revision == artifacts.timeline.call_capability_revision
    leg.transports.starshield_enabled = False
    assert saved_call_capabilities(leg, "mission", artifacts.route) is None


def test_catalog_only_change_reuses_transport_capability_with_new_windows():
    from app.mission.pop_status import PopStatusService
    from tests.integration.test_pop_status import telemetry
    from tests.unit.test_mission_pop_forecast import sites

    r, catalog, p, _, captured = prepared_status_inputs()
    service = PopStatusService()
    kwargs = {
        "route": r,
        "enabled": True,
        "mode": "simulation",
        "now": p.start_time,
        "observed_now": p.start_time,
        "projector": p,
        "call_capabilities": captured,
    }
    first = service.snapshot(telemetry(), catalog=catalog, **kwargs)
    changed = sites(("a", 0, -5), ("b", 0, 5)).model_copy(
        update={"fingerprint": "updated"}
    )
    second = service.snapshot(telemetry(), catalog=changed, **kwargs)
    assert second["call_continuity"] is not None
    assert second["call_continuity"]["pop_call_outage_seconds"] == 600
    assert (
        first["pop_forecast"]["transitions"][0]["crossing_utc"]
        == "2035-01-01T00:25:00Z"
    )
    assert (
        second["pop_forecast"]["transitions"][0]["crossing_utc"]
        == "2035-01-01T00:10:00Z"
    )
    assert second["call_continuity"]["revision"] != first["call_continuity"]["revision"]


@pytest.mark.parametrize("source", ["x", "ka"])
def test_saved_capability_rejects_changed_independent_source(
    tmp_path, monkeypatch, source
):
    import copy

    from app.mission import pop_capabilities, storage
    from app.mission.models import MissionLeg, TransportConfig
    from app.mission.timeline_preparation import prepare_mission_timeline
    from app.satellites.catalog import get_satellite_catalog
    from app.services.route_manager import RouteManager
    from tests.unit.test_mission_pop_forecast import route

    coverage = tmp_path / "coverage.json"
    monkeypatch.setattr(pop_capabilities, "Path", lambda path: coverage)
    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    manager = RouteManager(routes_dir=tmp_path / "routes")
    manager.add_route("r", route())
    leg = MissionLeg(
        id="leg",
        name="Leg",
        route_id="r",
        transports=TransportConfig(initial_x_satellite_id="X-1"),
    )
    artifacts = prepare_mission_timeline(leg, manager, discover_coverage=False)
    storage.save_mission_timeline(leg.id, artifacts.timeline, "mission")
    assert (
        pop_capabilities.saved_call_capabilities(leg, "mission", artifacts.route)
        is not None
    )
    if source == "x":
        changed = copy.deepcopy(get_satellite_catalog(read_only=True))
        changed.get_satellite("X-1").longitude = 5
        monkeypatch.setattr(
            pop_capabilities, "get_satellite_catalog", lambda **kwargs: changed
        )
    else:
        coverage.write_text("changed coverage")
    assert (
        pop_capabilities.saved_call_capabilities(leg, "mission", artifacts.route)
        is None
    )
