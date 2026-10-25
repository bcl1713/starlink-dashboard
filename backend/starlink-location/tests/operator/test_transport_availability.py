"""Authoritative transport state retires stale heads through existing event history."""

import pytest

from app.mission import storage
from app.mission.availability_models import AvailabilityChange
from app.mission.models import Transport
from app.operator.event_feed import build_snapshot
from app.operator.runtime import OperatorRuntime


def fail(mission, clock, transport, restore=False):
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
                ),
            ),
        }
    )
    # Fixture publication uses the command-owned writer; generic saves preserve old settings.
    with storage.get_active_leg_lock(), storage.get_mission_lock(mission.id):
        storage._save_mission_v2_unlocked(mission)


@pytest.mark.parametrize("broken_optional", [False, True])
def test_event_heads_and_local_cues_retire(production, clock, broken_optional):
    adapter, publication, state, _, _, _, catalog_path = production
    runtime = OperatorRuntime(adapter.service.store.settings, clock)
    runtime.service, runtime.event_publication = adapter.service, publication
    before = build_snapshot(runtime, "demo-mission", adapter)
    heads = [e for e in before.events if e.transport == "X" and e.active]
    assert heads and any(e.notification.eligible for e in heads)
    mission = storage.load_mission_v2("demo-mission")
    fail(mission, clock, Transport.X)
    if broken_optional:
        catalog_path.write_text("{broken")
        state["telemetry"] = None
    after = build_snapshot(runtime, mission.id, adapter)
    assert not any(e.transport == "X" and e.active for e in after.events)
    assert not any(e.transport == "X" and e.notification.eligible for e in after.events)
    assert any(
        e.event_id == heads[0].event_id and e.notification.retired for e in after.events
    )


def test_restore_does_not_revive_elapsed_actions(production, clock):
    adapter, publication, state, *_ = production
    runtime = OperatorRuntime(adapter.service.store.settings, clock)
    runtime.service, runtime.event_publication = adapter.service, publication
    before = build_snapshot(runtime, "demo-mission", adapter)
    old = [e for e in before.events if e.transport == "X" and e.active]
    assert old
    mission = storage.load_mission_v2("demo-mission")
    fail(mission, clock, Transport.X)
    build_snapshot(runtime, mission.id, adapter)
    # Move to the end of the route; route-aware timing must not revive old alerts.
    clock.advance(7200)
    state["telemetry"].position.observed_at = clock.now()
    state["telemetry"].position.speed_observed_at = clock.now()
    state["telemetry"].position.longitude = 10
    fail(storage.load_mission_v2(mission.id), clock, Transport.X, restore=True)
    after = build_snapshot(runtime, mission.id, adapter)
    assert not any(e.transport == "X" and e.notification.eligible for e in after.events)


def test_restore_returns_future_events_with_fresh_occurrence(production, clock):
    adapter, publication, *_ = production
    runtime = OperatorRuntime(adapter.service.store.settings, clock)
    runtime.service, runtime.event_publication = adapter.service, publication
    before = build_snapshot(runtime, "demo-mission", adapter)
    old = [e for e in before.events if e.transport == "X" and e.active]
    assert old
    fail(storage.load_mission_v2("demo-mission"), clock, Transport.X)
    build_snapshot(runtime, "demo-mission", adapter)
    fail(storage.load_mission_v2("demo-mission"), clock, Transport.X, restore=True)
    after = build_snapshot(runtime, "demo-mission", adapter)
    future = [
        e
        for e in after.events
        if e.transport == "X" and e.active and not e.notification.retired
    ]
    assert future
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
