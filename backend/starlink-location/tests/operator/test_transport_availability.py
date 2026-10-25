"""Authoritative transport state retires stale heads through existing event history."""

from datetime import timedelta
from pathlib import Path

import pytest

from app.mission import storage
from app.mission.availability_models import AvailabilityChange
from app.mission.models import KaOutage, KuOutageOverride, Transport, XTransition
from app.operator.event_feed import build_snapshot
from app.operator.runtime import OperatorRuntime


def fail(mission, clock, transport, restore=False, *, run_id=None):
    mission.availability = mission.availability.model_copy(
        update={
            "revision": mission.availability.revision + 1,
            "history": (
                *mission.availability.history,
                AvailabilityChange(
                    id=str(mission.availability.revision + 1),
                    transport=transport,
                    unavailable=not restore,
                    effective_at=clock.now(),
                    simulation_run_id=run_id,
                ),
            ),
        }
    )
    # Fixture publication uses the command-owned writer; generic saves preserve old settings.
    with storage.get_active_leg_lock(), storage.get_mission_lock(mission.id):
        storage._save_mission_v2_unlocked(mission)


EVENT_TRANSPORTS = [
    (Transport.X, "X"),
    (Transport.KA, "Ka"),
    (Transport.KU, "Starshield"),
]


def lifecycle_runtime(production, clock):
    adapter, publication, *_ = production
    # Real planned outage inputs near the current route position produce eligible
    # Ka and Starshield restrictions through the normal capability calculation.
    mission = storage.load_mission_v2("demo-mission")
    start = clock.now() - timedelta(minutes=9)
    mission.legs[0].transports.ka_outages = [
        KaOutage(id="ka-input", start_time=start, duration_seconds=180)
    ]
    mission.legs[0].transports.ku_overrides = [
        KuOutageOverride(id="ku-input", start_time=start, duration_seconds=180)
    ]
    Path("data/satellites/catalog.yaml").write_text(
        "satellites:\n  - id: X-1\n    transport: X\n    longitude: 90\n"
        "  - id: X-2\n    transport: X\n    longitude: 20\n"
    )
    mission.legs[0].transports.x_transitions = [
        XTransition(
            id="x-visible", latitude=0, longitude=-9, target_satellite_id="X-2"
        ),
        XTransition(id="x-later", latitude=0, longitude=9, target_satellite_id="X-1"),
    ]
    storage.save_mission_v2(mission)
    runtime = OperatorRuntime(adapter.service.store.settings, clock)
    runtime.service, runtime.event_publication = adapter.service, publication
    return runtime, adapter


def assert_no_transport_notifications(events, label):
    assert not any(e.transport == label and e.notification.eligible for e in events)


def assert_transport_retired(events, label):
    assert not any(e.transport == label and e.active for e in events)
    assert_no_transport_notifications(events, label)


@pytest.mark.parametrize("transport,label", EVENT_TRANSPORTS)
@pytest.mark.parametrize("broken_optional", [False, True])
def test_event_heads_and_local_cues_retire(
    production, clock, broken_optional, transport, label
):
    _, _, state, _, _, _, catalog_path = production
    runtime, adapter = lifecycle_runtime(production, clock)
    before = build_snapshot(runtime, "demo-mission", adapter)
    heads = [e for e in before.events if e.transport == label and e.active]
    assert heads and any(e.notification.eligible for e in heads)
    mission = storage.load_mission_v2("demo-mission")
    with pytest.raises(AssertionError):
        assert_transport_retired(heads, label)
    with pytest.raises(AssertionError):
        assert_no_transport_notifications(heads, label)
    fail(mission, clock, transport)
    if broken_optional:
        catalog_path.write_text("{broken")
        state["telemetry"] = None
    after = build_snapshot(runtime, mission.id, adapter)
    assert_transport_retired(after.events, label)
    for head in heads:
        assert any(
            e.event_id == head.event_id
            and e.notification.generation == head.notification.generation
            and e.notification.retired
            for e in after.events
        )


@pytest.mark.parametrize("transport,label", EVENT_TRANSPORTS)
def test_restore_does_not_revive_elapsed_actions(production, clock, transport, label):
    _, _, state, *_ = production
    runtime, adapter = lifecycle_runtime(production, clock)
    before = build_snapshot(runtime, "demo-mission", adapter)
    old = [e for e in before.events if e.transport == label and e.active]
    assert old
    mission = storage.load_mission_v2("demo-mission")
    fail(mission, clock, transport)
    build_snapshot(runtime, mission.id, adapter)
    # Move to the end of the route; route-aware timing must not revive old alerts.
    clock.advance(7200)
    state["telemetry"].position.observed_at = clock.now()
    state["telemetry"].position.speed_observed_at = clock.now()
    state["telemetry"].position.longitude = 10
    fail(storage.load_mission_v2(mission.id), clock, transport, restore=True)
    after = build_snapshot(runtime, mission.id, adapter)
    assert not any(
        e.transport == label and e.notification.eligible for e in after.events
    )


@pytest.mark.parametrize("transport,label", EVENT_TRANSPORTS)
def test_restore_returns_future_events_with_fresh_occurrence(
    production, clock, transport, label
):
    runtime, adapter = lifecycle_runtime(production, clock)
    before = build_snapshot(runtime, "demo-mission", adapter)
    old = [e for e in before.events if e.transport == label and e.active]
    assert old
    fail(storage.load_mission_v2("demo-mission"), clock, transport)
    build_snapshot(runtime, "demo-mission", adapter)
    fail(storage.load_mission_v2("demo-mission"), clock, transport, restore=True)
    after = build_snapshot(runtime, "demo-mission", adapter)
    future = [
        e
        for e in after.events
        if e.transport == label and e.active and not e.notification.retired
    ]
    assert future
    assert any(e.due_at and e.due_at > clock.now() for e in future)
    assert all(e.end_at and e.end_at > clock.now() for e in future)
    assert not any(e.state == "overdue" and e.notification.eligible for e in future)
    for head in old:
        assert any(
            e.notification.generation == head.notification.generation
            and e.notification.retired
            for e in after.events
        )
    assert {e.notification.generation for e in old}.isdisjoint(
        e.notification.generation for e in future
    )


def test_same_geometry_restoration_renews_only_affected_transport(service, clock):
    from datetime import timedelta

    from app.mission.availability_context import snapshot_for_leg
    from app.mission.availability_models import FailureWindow
    from tests.operator.test_event_projection import derive

    parent = storage.load_mission_v2("demo-mission")
    snapshot = snapshot_for_leg(parent, parent.legs[0])
    start, end = clock.now() + timedelta(minutes=5), clock.now() + timedelta(minutes=15)
    model = {
        "transport_availability": snapshot.model_dump(mode="json"),
        "transport_as_of": clock.now().isoformat(),
        "capability_spans": [
            {
                "start_utc": start.isoformat(),
                "end_utc": end.isoformat(),
                "ka": "unavailable",
                "x": "unavailable",
                "starshield": "available",
            }
        ],
    }
    before = {e.transport: e for e in derive(service, clock, models={"leg-a": model})}
    restored = snapshot.model_copy(
        update={
            "revision": 2,
            "failures": (
                FailureWindow(
                    transport=Transport.X,
                    start=clock.now() - timedelta(minutes=2),
                    end=clock.now(),
                ),
            ),
        }
    )
    model["transport_availability"] = restored.model_dump(mode="json")
    after = {e.transport: e for e in derive(service, clock, models={"leg-a": model})}
    assert after["X"].schedule_key != before["X"].schedule_key
    assert after["Ka"].schedule_key == before["Ka"].schedule_key


def test_unreadable_parent_keeps_source_uncertainty_without_crashing(
    production, clock, monkeypatch
):
    adapter, *_ = production
    adapter.capture("demo-mission", as_of=clock.now())

    def unavailable(*args, **kwargs):
        raise OSError("mission storage unavailable")

    monkeypatch.setattr(storage, "load_mission_v2", unavailable)
    captured = adapter.capture("demo-mission", as_of=clock.now())
    assert any(source.freshness == "unknown" for source in captured.sources)


@pytest.mark.parametrize("transport,label", EVENT_TRANSPORTS)
def test_selected_replay_projects_capability_events_and_link_without_live_leak(
    production, clock, transport, label, tmp_path
):
    from types import SimpleNamespace

    from app.mission.availability_context import snapshot_for_leg
    from app.operator.production_event_inputs import capture_current
    from app.operator.production_event_sources import ProductionEventSources
    from app.operator.settings import OperatorSettings
    from app.services.active_x_link import build_active_x_link

    lifecycle_runtime(production, clock)
    _, _, state, config, routes, _, _ = production
    config.mode = "simulation"
    run_id = "selected-replay"
    runtime = OperatorRuntime.start(
        OperatorSettings(
            root=tmp_path / "replay-operator",
            source_mode="simulation",
            simulation_run_id=run_id,
        ),
        clock=clock,
    )
    try:
        runtime.provision(expected_mode="simulation", expected_run=run_id)
        adapter = ProductionEventSources(
            runtime.service,
            clock=clock,
            publication=runtime.event_publication,
            route_manager=routes,
            config_provider=lambda: config,
            telemetry_provider=lambda: state["telemetry"],
            context_provider=lambda: {
                "source_mode": "simulation",
                "simulation_run_id": run_id,
                "active_route_id": routes.get_active_route_id(),
                "phase": "in_flight",
            },
        )
        baseline = build_snapshot(runtime, "demo-mission", adapter)
        heads = [e for e in baseline.events if e.transport == label and e.active]
        assert heads and any(e.notification.eligible for e in heads)
        fail(storage.load_mission_v2("demo-mission"), clock, transport, run_id=run_id)
        failed = build_snapshot(runtime, "demo-mission", adapter)
        assert_transport_retired(failed.events, label)
        with storage.get_active_leg_lock():
            inputs = capture_current(adapter, "demo-mission", as_of=clock.now())
        artifacts = inputs.prepare(inputs.mission.legs[0])
        field = {Transport.X: "x", Transport.KA: "ka", Transport.KU: "starshield"}[
            transport
        ]
        remaining = [
            span
            for span in artifacts.call_capabilities.spans
            if span.end_utc > clock.now()
        ]
        assert remaining and all(
            getattr(span, field) == "unavailable" for span in remaining
        )
        live = snapshot_for_leg(inputs.mission, inputs.mission.legs[0])
        assert live.resolve(clock.now())[transport] is True
        if transport == Transport.X:
            coordinator = SimpleNamespace(
                get_current_telemetry=lambda: state["telemetry"]
            )
            assert (
                build_active_x_link(
                    coordinator=coordinator,
                    route_manager=routes,
                    poi_manager=None,
                    run_id=run_id,
                    operating_time=clock.now(),
                )["transport_active"]
                is False
            )
            assert (
                build_active_x_link(
                    coordinator=coordinator,
                    route_manager=routes,
                    poi_manager=None,
                    operating_time=clock.now(),
                ).get("transport_active", True)
                is True
            )
        fail(
            storage.load_mission_v2("demo-mission"),
            clock,
            transport,
            restore=True,
            run_id=run_id,
        )
        restored = build_snapshot(runtime, "demo-mission", adapter)
        future = [
            e
            for e in restored.events
            if e.transport == label and e.active and e.due_at and e.due_at > clock.now()
        ]
        assert future
        assert not any(
            e.state == "overdue" and e.notification.eligible for e in restored.events
        )
    finally:
        runtime.close()


@pytest.mark.parametrize("transport,label", EVENT_TRANSPORTS)
def test_capture_started_before_restore_keeps_future_cues(
    production, clock, monkeypatch, transport, label
):
    runtime, adapter = lifecycle_runtime(production, clock)
    build_snapshot(runtime, "demo-mission", adapter)
    fail(storage.load_mission_v2("demo-mission"), clock, transport)
    started_at = clock.now()
    build_snapshot(runtime, "demo-mission", adapter)
    clock.advance(1)
    fail(storage.load_mission_v2("demo-mission"), clock, transport, restore=True)
    capture = adapter.capture
    # A request can enter before restore and acquire repository admission after it.
    with monkeypatch.context() as patch:
        patch.setattr(
            adapter,
            "capture",
            lambda mission_id, *, as_of: capture(mission_id, as_of=started_at),
        )
        build_snapshot(runtime, "demo-mission", adapter)
    # The accepted revision is cached. A normal subsequent read must still recover
    # future cues with live timing, without repeating preparation or emitting overdue.
    result = build_snapshot(runtime, "demo-mission", adapter)
    future = [
        event
        for event in result.events
        if event.transport == label
        and event.active
        and event.due_at
        and event.due_at > clock.now()
    ]
    assert future
    assert any(
        event.freshness == "fresh" and event.state == "upcoming" for event in future
    )
    assert not any(
        event.state == "overdue" and event.notification.eligible
        for event in result.events
    )
