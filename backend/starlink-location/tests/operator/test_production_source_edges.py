"""Current independent restrictions and per-leg retirement survive source edges."""

from pathlib import Path

import pytest

from app.mission import storage
from app.operator.event_feed import build_snapshot
from app.operator.runtime import OperatorRuntime


@pytest.mark.parametrize("remove", [False, True])
def test_switch_or_remove_leg_retires_old_heads_even_after_adapter_restart(
    production, clock, remove
):
    adapter, publication, *_ = production
    runtime = OperatorRuntime(adapter.service.store.settings, clock)
    runtime.service, runtime.event_publication = adapter.service, publication
    before = build_snapshot(runtime, "demo-mission", adapter)
    assert any(
        e.leg_id == "leg-a" and e.kind == "restriction" and e.active
        for e in before.events
    )
    mission = storage.load_mission_v2("demo-mission")
    old = mission.legs[0]
    new = old.model_copy(update={"id": "leg-b", "is_active": True}, deep=True)
    old.is_active = False
    mission.legs = [new] if remove else [old, new]
    storage.save_mission_v2(mission)
    # Runtime memory is not authority for retirement after a restart.
    adapter.close()
    after = build_snapshot(runtime, "demo-mission", adapter)
    assert not any(e.leg_id == "leg-a" and e.active for e in after.events)
    assert any(
        e.leg_id == "leg-b" and e.kind == "restriction" and e.active
        for e in after.events
    )


@pytest.mark.parametrize(
    "content", ["{malformed", '{"type":"FeatureCollection","features":[]}']
)
def test_invalid_optional_ka_keeps_current_x_alert(production, clock, content):
    adapter, publication, *_ = production
    Path("data/sat_coverage/commka.geojson").write_text(content)
    runtime = OperatorRuntime(adapter.service.store.settings, clock)
    runtime.service, runtime.event_publication = adapter.service, publication
    snapshot = build_snapshot(runtime, "demo-mission", adapter)
    assert snapshot.coverage == "partial"
    assert any("Ka coverage" in (s.reason or "") for s in snapshot.sources)
    assert any(e.transport == "X" and e.notification.eligible for e in snapshot.events)
    assert all(
        not e.notification.eligible for e in snapshot.events if e.transport == "Ka"
    )


def test_unpublished_inactive_leg_keeps_saved_planning_rows(production, clock):
    adapter, publication, *_ = production
    mission = storage.load_mission_v2("demo-mission")
    future = mission.legs[0].model_copy(
        update={"id": "leg-b", "is_active": False}, deep=True
    )
    mission.legs.append(future)
    storage.save_mission_v2(mission)
    from app.operator.production_event_inputs import capture_current

    with storage.get_active_leg_lock():
        captured = capture_current(adapter, mission.id, as_of=clock.now())
    timeline = captured.prepare(future).timeline
    storage.save_mission_timeline(future.id, timeline, mission.id)
    runtime = OperatorRuntime(adapter.service.store.settings, clock)
    runtime.service, runtime.event_publication = adapter.service, publication
    snapshot = build_snapshot(runtime, mission.id, adapter)
    assert any(
        e.leg_id == future.id and e.active and e.freshness == "unknown"
        for e in snapshot.events
    )
    assert all(
        not e.notification.eligible for e in snapshot.events if e.leg_id == future.id
    )
