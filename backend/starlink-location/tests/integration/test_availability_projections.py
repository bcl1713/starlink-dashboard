"""Transport cues retain their identity while eligibility changes."""

import json
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.mission import storage
from app.mission.models import MissionLegTimeline, Transport
from app.models.poi import POICreate
from app.services.overview_upcoming_pois import project_overview_upcoming_pois
from tests.integration import test_transport_availability_routes as availability_routes

NOW = availability_routes.NOW
availability_api = availability_routes.availability_api
command = availability_routes.command


@pytest.fixture
def cues(availability_api):
    client, app, store, mission = availability_api
    # Stored points intentionally include X geometry no longer computable while down.
    points = {}
    for kind in (
        "x_band_transition",
        "ka_transition",
        "starshield_transition_start",
        "aar_start",
    ):
        points[kind] = store.poi_manager.create_poi(
            POICreate(
                name=kind,
                kind=kind,
                latitude=0.8,
                longitude=0,
                mission_id=mission.id,
                route_id="route-one",
                expected_arrival_time=NOW + timedelta(minutes=45),
            ),
            generated_source="mission-timeline",
        )
    points["manual"] = store.poi_manager.create_poi(
        POICreate(
            name="X manual note",
            latitude=0.8,
            longitude=0,
            mission_id=mission.id,
            route_id="route-one",
        )
    )
    return client, app, store, mission, points


@pytest.mark.parametrize(
    "transport,kind",
    [
        ("X", "x_band_transition"),
        ("Ka", "ka_transition"),
        ("Ku", "starshield_transition_start"),
    ],
)
def test_failure_retains_poi_ids_but_hides_active_cues(cues, transport, kind):
    client, _, store, mission, points = cues
    assert command(client, transport=transport).status_code == 200
    retained = store.poi_manager.get_poi(points[kind].id)
    assert retained is not None
    assert retained.transport_active is False
    assert retained.inactive_reason
    timeline = MissionLegTimeline.model_validate_json(
        storage.get_leg_timeline_path("leg-1", mission.id).read_bytes()
    )
    saved = next(p for p in timeline.map_pois if p.kind == kind)
    assert saved.transport_active is False
    projected = project_overview_upcoming_pois(
        pois=[retained],
        eta_results={retained.id: 300},
        flight_phase="in_flight",
        current_progress=10,
        calculated_at=NOW + timedelta(minutes=10),
    )
    assert projected.pois == []


def test_restore_returns_future_pois_without_duplicates(cues):
    client, app, store, mission, points = cues
    assert command(client).status_code == 200
    app.state.availability_clock = SimpleNamespace(
        now=lambda: NOW + timedelta(minutes=20)
    )
    assert (
        command(client, revision=1, command_id="restore", action="restore").status_code
        == 200
    )
    stored = store.poi_manager.list_pois(mission_id=mission.id)
    assert len([p for p in stored if p.kind == "ka_transition"]) == 1
    assert (
        store.poi_manager.get_poi(points["ka_transition"].id).transport_active is True
    )
    timeline = MissionLegTimeline.model_validate_json(
        storage.get_leg_timeline_path("leg-1", mission.id).read_bytes()
    )
    assert len([p for p in timeline.map_pois if p.kind == "ka_transition"]) == 1


def test_other_transports_and_manual_pois_survive(cues):
    client, _, store, _, points = cues
    assert command(client).status_code == 200
    for kind in ("starshield_transition_start", "aar_start", "manual"):
        retained = store.poi_manager.get_poi(points[kind].id)
        assert retained is not None and retained.transport_active is True


def test_restore_releases_failure_but_preserves_planned_unavailability(cues):
    client, _, store, _, points = cues
    assert command(client, transport="X").status_code == 200
    assert (
        command(
            client, transport="X", revision=1, command_id="restore", action="restore"
        ).status_code
        == 200
    )
    assert (
        store.poi_manager.get_poi(points["x_band_transition"].id).transport_active
        is False
    )


def test_projection_cache_invalidates_on_availability(cues):
    client, _, store, _, _ = cues
    before = store.poi_manager.metrics_input_identity()
    assert command(client).status_code == 200
    assert store.poi_manager.metrics_input_identity() != before


def test_live_delay_suppresses_cue_scheduled_before_failure(cues):
    client, _, store, mission, points = cues
    from app.mission.availability import resolved_leg_availability
    from app.mission.availability_context import for_run

    point = store.poi_manager.get_poi(points["ka_transition"].id)
    point.expected_arrival_time = NOW + timedelta(minutes=5)
    point.projected_route_progress = 80
    assert command(client).status_code == 200
    parent = storage.load_mission_v2(mission.id)
    snapshot = resolved_leg_availability(for_run(parent), parent.legs[0])
    response = project_overview_upcoming_pois(
        pois=[point],
        eta_results={point.id: 300},
        flight_phase="in_flight",
        current_progress=10,
        calculated_at=NOW + timedelta(minutes=10),
        availability=snapshot,
    )
    assert response.pois == []


def test_export_map_uses_captured_parent_availability(cues):
    client, _, store, mission, _ = cues
    from app.mission.exporter.snapshot import capture_export_snapshot

    assert command(client).status_code == 200
    exported = capture_export_snapshot(
        mission.id, store.route_manager, store.poi_manager
    )
    leg = next(leg for leg in exported.legs if leg.leg_id == "leg-1")
    markers = [json.loads(raw) for raw in leg.map_pois]
    assert any(
        p["kind"] == "ka_transition" and p["transport_active"] is False for p in markers
    )
    timeline = json.loads(leg.timeline_json)
    assert all(
        segment["ka_state"] == "offline"
        for segment in timeline["segments"]
        if segment["start_time"] >= "2035-03-01T12:10:00Z"
    )


def test_ineligible_active_x_link_is_empty(cues):
    _, _, store, _, _ = cues
    from app.services.active_x_handoff import ActiveXContext, empty_handoff_context
    from app.services.active_x_link import build_active_x_link

    store.poi_manager.create_poi(
        POICreate(name="X-1", category="satellite", icon="X", latitude=0, longitude=0)
    )
    result = build_active_x_link(
        None,
        store.route_manager,
        store.poi_manager,
        paced_context=ActiveXContext("X-1", None, empty_handoff_context()),
    )
    assert result["coordinates"] == []
    assert result["satellite_id"] is None
    assert result["transport_active"] is False
    assert store.poi_manager.find_global_poi_by_name("X-1") is not None


def test_transport_events_suppressed_but_shared_call_outage_remains():
    from app.mission.availability_context import snapshot_for_leg
    from app.mission.models import Mission, MissionLeg, TransportConfig
    from app.operator.restriction_windows import restriction_windows

    mission = Mission(
        id="events",
        name="events",
        legs=[
            MissionLeg(
                id="leg",
                name="leg",
                route_id="route",
                transports=TransportConfig(initial_x_satellite_id=""),
            )
        ],
    )
    mission.availability.defaults[Transport.KA] = False
    snapshot = snapshot_for_leg(mission, mission.legs[0])
    model = {
        "transport_availability": snapshot.model_dump(mode="json"),
        "transport_as_of": NOW.isoformat(),
        "capability_spans": [
            {
                "start_utc": NOW.isoformat(),
                "end_utc": (NOW + timedelta(minutes=10)).isoformat(),
                "ka": "unavailable",
                "x": "available",
                "starshield": "available",
            }
        ],
        "call_continuity": {
            "intervals": [
                {
                    "classification": "existing_outage",
                    "source_ids": [],
                    "start_utc": NOW.isoformat(),
                    "end_utc": (NOW + timedelta(minutes=10)).isoformat(),
                }
            ]
        },
    }
    windows = list(restriction_windows(model))
    assert len(windows) == 1 and windows[0][0] is None


def test_republication_preserves_generated_identity(cues):
    _, _, store, mission, _ = cues
    from app.mission.availability_context import snapshot_for_leg
    from app.mission.timeline_preparation import (
        prepare_mission_timeline,
        publish_mission_pois,
    )

    artifacts = prepare_mission_timeline(
        mission.legs[0],
        store.route_manager,
        store.poi_manager,
        parent_mission_id=mission.id,
        availability=snapshot_for_leg(mission, mission.legs[0]),
    )
    publish_mission_pois(artifacts, store.poi_manager, mission.id, "route-one")
    first = {
        p.id: p.created_at for p in store.poi_manager.list_pois(mission_id=mission.id)
    }
    publish_mission_pois(artifacts, store.poi_manager, mission.id, "route-one")
    second = {
        p.id: p.created_at for p in store.poi_manager.list_pois(mission_id=mission.id)
    }
    assert first == second


def test_new_simulation_plan_excludes_live_failure(cues):
    client, _, store, mission, _ = cues
    from app.models.simulation_run import MultiplierPacing
    from app.simulation.run_runtime import SimulationRunRuntime
    from app.simulation.run_service import SimulationRunService

    assert command(client).status_code == 200
    parent = storage.load_mission_v2(mission.id)
    runtime = SimulationRunRuntime(lambda: 0, lambda: NOW, service_mode="simulation")
    service = SimulationRunService(runtime, store.route_manager, store.poi_manager)
    plan = service.prepare_plan(
        mission.id, parent.legs[0], MultiplierPacing(mode="multiplier", multiplier=10)
    )
    snapshot = plan.artifacts.timeline.statistics["_transport_availability"]
    assert snapshot["failures"] == []


def test_live_export_fallback_does_not_trust_simulation_poi_flags(cues, monkeypatch):
    client, app, store, mission, points = cues
    from app.mission.exporter.snapshot import capture_export_snapshot
    from app.mission.exporter.snapshot_views import SnapshotViews

    app.state.availability_source_mode = "simulation"
    app.state.simulation_run_service = SimpleNamespace(
        status=lambda: SimpleNamespace(
            state="running",
            run=SimpleNamespace(
                run_id="simulation-one",
                mission_id=mission.id,
                leg_id="leg-1",
                simulation_time=NOW + timedelta(minutes=10),
            ),
        )
    )
    assert command(client).status_code == 200
    assert (
        store.poi_manager.get_poi(points["ka_transition"].id).transport_active is False
    )

    def unavailable(*args, **kwargs):
        raise ValueError("coverage source unavailable")

    monkeypatch.setattr(
        "app.mission.exporter.snapshot.prepare_mission_timeline", unavailable
    )
    exported = capture_export_snapshot(
        mission.id, store.route_manager, store.poi_manager
    )
    projected = SnapshotViews(exported).map_poi_manager("leg-1").list_pois()
    assert (
        next(
            p for p in projected if p.id == points["ka_transition"].id
        ).transport_active
        is True
    )
    saved = SnapshotViews(exported).timeline("leg-1")
    assert (
        next(p for p in saved.map_pois if p.kind == "ka_transition").transport_active
        is True
    )


def test_delayed_upcoming_cue_returns_after_restore(cues):
    client, app, store, mission, points = cues
    from app.mission.availability_context import snapshot_for_leg
    from app.mission.availability_pois import apply_poi_availability

    point = store.poi_manager.get_poi(points["ka_transition"].id)
    point.expected_arrival_time = NOW + timedelta(minutes=15)
    point.projected_route_progress = 80
    assert command(client).status_code == 200
    app.state.availability_clock = SimpleNamespace(
        now=lambda: NOW + timedelta(minutes=20)
    )
    assert (
        command(client, revision=1, command_id="restore", action="restore").status_code
        == 200
    )
    parent = storage.load_mission_v2(mission.id)
    snapshot = snapshot_for_leg(parent, parent.legs[0])
    # Static historical modeling retains the outage at its original instant.
    assert apply_poi_availability(point, snapshot).transport_active is False
    response = project_overview_upcoming_pois(
        pois=[point],
        eta_results={point.id: 300},
        flight_phase="in_flight",
        current_progress=10,
        calculated_at=NOW + timedelta(minutes=25),
        availability=snapshot,
    )
    assert len(response.pois) == 1 and response.pois[0].upcoming is True
    passed = project_overview_upcoming_pois(
        pois=[point],
        eta_results={point.id: 0},
        flight_phase="in_flight",
        current_progress=90,
        calculated_at=NOW + timedelta(minutes=25),
        availability=snapshot,
    )
    assert not any(p.upcoming for p in passed.pois)


def test_future_x_swap_during_failure_is_audit_only_in_briefing(cues):
    client, _, store, mission, _ = cues
    from app.mission.exporter.customer_projection import project_briefing_leg
    from app.mission.exporter.snapshot import capture_export_snapshot
    from app.mission.models import XTransition

    parent = storage.load_mission_v2(mission.id)
    parent.availability = parent.availability.model_copy(update={"defaults": {}})
    for leg in parent.legs:
        leg.transports.initial_x_satellite_id = "X-1"
        leg.transports.x_transitions = [
            XTransition(
                id="future-swap", latitude=0.8, longitude=0, target_satellite_id="X-1"
            )
        ]
    storage.save_mission_v2(parent)
    assert command(client, transport="X").status_code == 200
    snapshot = capture_export_snapshot(
        mission.id, store.route_manager, store.poi_manager
    )
    leg = next(leg for leg in snapshot.legs if leg.leg_id == "leg-1")
    raw = [json.loads(s) for s in leg.source_records]
    assert any(s.get("event_type") == "x_transition_start" for s in raw)
    projected = project_briefing_leg(leg)
    for interval in projected.intervals:
        if interval.start_time >= NOW + timedelta(minutes=10):
            assert interval.decisions[2].value == "Down"
            assert "future-swap" not in interval.active_source_ids
            assert not any("transition" in cause.lower() for cause in interval.causes)
