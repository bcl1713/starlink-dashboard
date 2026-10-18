"""Actual #348 and #379 interfaces drive transport review using synthetic inputs."""

from datetime import timedelta

from app.mission.pop_status import PopStatusService
from app.operator.event_feed import build_snapshot
from tests.operator.service_helpers import create
from tests.operator.test_production_live_timing import restriction, runtime_for
from tests.operator.test_transport_contract import decision, row


def test_live_eta_pop_and_history_integrate(
    production, clock, record_data, monkeypatch
):
    from types import SimpleNamespace

    from app.services.flight_state import get_flight_state_manager

    monkeypatch.setattr(
        get_flight_state_manager(),
        "get_status",
        lambda: SimpleNamespace(
            phase=SimpleNamespace(value="in_flight"), departure_time=clock.now()
        ),
    )
    runtime, adapter = runtime_for(production, clock)
    adapter.pop_service = PopStatusService(production[4], lambda: production[3])
    position = production[2]["telemetry"].position
    position.longitude, position.speed = -10, 300
    clock.advance(2100)  # Initial fixture is +10 minutes, departure now +45.
    position.observed_at = position.speed_observed_at = clock.now()
    first = build_snapshot(runtime, "demo-mission", adapter)
    x = restriction(first)
    pop = next(
        e
        for e in first.events
        if e.kind == "pop_advisory" and e.due_at and e.end_at and e.active
    )
    start = min(x.due_at, pop.due_at) - timedelta(minutes=1)
    end = max(x.end_at, pop.end_at) + timedelta(minutes=1)
    customer = create(
        runtime.service,
        record_data,
        record_type="call",
        time={"planned_start_at": start, "planned_end_at": end},
        payload={
            "entry_type": "call",
            "title": "Synthetic customer",
            "prep_lead_minutes": 10,
        },
    )
    data = decision(
        record_data,
        row(requested={"transport": "X"}, applied={"transport": "Starshield"}),
    )
    data["payload"]["call_id"] = str(customer.record_id)
    saved = create(runtime.service, data)
    before = saved.model_dump_json()
    current = build_snapshot(runtime, "demo-mission", adapter)
    matched = [
        a
        for a in current.transport_review.assessments
        if a.decision_id == str(saved.record_id)
    ]
    assert any(x.event_id in a.event_ids for a in matched)
    assert any(pop.event_id in a.event_ids for a in matched)
    assert x.due_at > clock.now() and x.planned_due_at < clock.now()
    assert current.transport_review.actual_routing == "unknown"
    position.speed = 1200
    faster = build_snapshot(runtime, "demo-mission", adapter)
    assert restriction(faster).due_at < restriction(current).due_at
    assert restriction(faster).notification.threshold_at == restriction(
        faster
    ).due_at - timedelta(minutes=5)
    for latitude in (1, 0):
        position.latitude = latitude
        changed = build_snapshot(runtime, "demo-mission", adapter)
        assert restriction(changed).time_basis == "live_route_eta"
    clock.advance(31)
    stale = build_snapshot(runtime, "demo-mission", adapter)
    assert stale.transport_review.coverage != "available"
    assert not any(
        a.status == "no_overlap_found" for a in stale.transport_review.assessments
    )
    assert runtime.service.get(str(saved.record_id)).model_dump_json() == before
