"""Airborne restrictions share existing live route ETA and one occurrence."""

from datetime import timedelta

import pytest

from app.operator.errors import OperatorError
from app.operator.event_feed import build_snapshot
from app.operator.runtime import OperatorRuntime


def runtime_for(production, clock):
    adapter, publication, *_ = production
    runtime = OperatorRuntime(adapter.service.store.settings, clock)
    runtime.service, runtime.event_publication = adapter.service, publication
    return runtime, adapter


def restriction(snapshot):
    return next(e for e in snapshot.events if e.transport == "X" and e.active)


@pytest.mark.parametrize(
    "delay,speed,latitude",
    [(2100, 300, 0), (-900, 600, 0), (2100, 1200, 0), (2100, 300, 1)],
)
def test_airborne_boundary_reuses_actual_route_eta(
    production, clock, delay, speed, latitude
):
    from app.models.poi import POI
    from app.operator.production_event_inputs import capture_current
    from app.services.eta_calculator import ETACalculator

    runtime, adapter = runtime_for(production, clock)
    state, leg = production[2], production[5]
    position = state["telemetry"].position
    clock.advance(delay)
    position.latitude, position.longitude, position.speed = latitude, -10, speed
    position.observed_at = position.speed_observed_at = clock.now()
    inputs = capture_current(adapter, "demo-mission", as_of=clock.now())
    artifacts = inputs.prepare(leg)
    event = restriction(build_snapshot(runtime, "demo-mission", adapter))
    assert event.time_basis == "live_route_eta"
    assert event.planned_due_at is not None
    distance = artifacts.projector.distance_for_timestamp(event.planned_due_at)
    boundary = artifacts.projector.sample_at_distance(distance)
    projection = artifacts.projector.calculator.project_poi_to_route(
        boundary.latitude, boundary.longitude
    )
    destination = POI(
        id="boundary",
        name="Boundary",
        latitude=boundary.latitude,
        longitude=boundary.longitude,
        projected_latitude=boundary.latitude,
        projected_longitude=boundary.longitude,
        projected_waypoint_index=projection["projected_waypoint_index"],
        projected_route_progress=100 * distance / artifacts.projector.total_distance,
    )
    seconds = ETACalculator()._calculate_route_aware_eta_estimated(
        latitude, -10, destination, artifacts.route, speed
    )
    assert seconds is not None
    assert event.due_at == clock.now() + timedelta(seconds=seconds)
    assert event.notification.threshold_at == event.due_at - timedelta(minutes=5)
    assert event.notification.eligible == (seconds <= 300)


def test_progress_changes_guard_and_threshold_without_new_occurrence(production, clock):
    runtime, adapter = runtime_for(production, clock)
    position = production[2]["telemetry"].position
    position.longitude, position.speed = -10, 300
    first_snapshot = build_snapshot(runtime, "demo-mission", adapter)
    first = restriction(first_snapshot)
    assert not first.notification.eligible
    source = next(s for s in first_snapshot.sources if s.source == first.source_ref)
    position.speed = 1200
    with pytest.raises(OperatorError), adapter.publication.guard([source]):
        pass
    second = restriction(build_snapshot(runtime, "demo-mission", adapter))
    assert second.notification.eligible
    assert second.event_id == first.event_id
    assert second.notification.generation == first.notification.generation
    position.speed = 300
    third = restriction(build_snapshot(runtime, "demo-mission", adapter))
    assert not third.notification.eligible
    assert third.notification.generation == first.notification.generation


def test_preflight_uses_plan_and_missing_airborne_progress_is_explicit(
    production, clock
):
    runtime, adapter = runtime_for(production, clock)
    context = adapter.context_provider
    adapter.context_provider = lambda: context() | {"phase": "pre_departure"}
    planned = restriction(build_snapshot(runtime, "demo-mission", adapter))
    assert planned.time_basis == "planned_utc"
    adapter.context_provider = context
    production[2]["telemetry"].position.speed = 0
    unavailable = build_snapshot(runtime, "demo-mission", adapter)
    event = next(e for e in unavailable.events if e.transport == "X" and e.active)
    assert event.time_basis == "live_unavailable"
    assert event.due_at is None and event.state == "unknown"
    assert not event.notification.eligible
    assert event.planned_due_at == planned.due_at


def test_ack_survives_large_eta_refresh_and_restart(production, clock):
    from uuid import uuid4

    from app.operator.event_ack import acknowledge
    from app.operator.event_models import AckRequest

    runtime, adapter = runtime_for(production, clock)
    snapshot = build_snapshot(runtime, "demo-mission", adapter)
    event = restriction(snapshot)
    receipt, _ = acknowledge(
        AckRequest(
            occurrence_id=event.notification.generation,
            severity_generation=event.notification.severity_generation,
            snapshot_token=snapshot.snapshot_token,
        ),
        key=str(uuid4()),
        epoch=str(runtime.health().api_epoch),
        runtime=runtime,
        adapter=adapter,
    )
    clock.advance(2700)
    position = production[2]["telemetry"].position
    position.observed_at = position.speed_observed_at = clock.now()
    position.longitude, position.speed = -10, 300
    updated = restriction(build_snapshot(runtime, "demo-mission", adapter))
    assert updated.due_at > event.due_at + timedelta(minutes=40)
    assert updated.notification.generation == receipt.occurrence_id
    assert updated.notification.acknowledged
    runtime.event_stability.candidates.clear()
    adapter.cache.clear()
    restarted = restriction(build_snapshot(runtime, "demo-mission", adapter))
    assert restarted.notification.acknowledged
    with runtime.service.store.connect() as db:
        assert (
            db.execute("SELECT count(*) FROM event_acknowledgments").fetchone()[0] == 1
        )


def test_ka_boundary_and_deviation_rejoin_use_live_progress(production, clock):
    import json
    from pathlib import Path

    coverage = Path("data/sat_coverage/commka.geojson")
    raw = json.loads(coverage.read_text())
    raw["features"][0]["geometry"]["coordinates"] = [
        [[-20, -10], [-8, -10], [-8, 10], [-20, 10], [-20, -10]]
    ]
    coverage.write_text(json.dumps(raw))
    runtime, adapter = runtime_for(production, clock)
    position = production[2]["telemetry"].position
    position.longitude, position.speed = -10, 600
    first = build_snapshot(runtime, "demo-mission", adapter)
    ka = next(e for e in first.events if e.transport == "Ka" and e.active)
    assert ka.time_basis == "live_route_eta"
    assert ka.due_at > clock.now()
    position.latitude, position.longitude = 1, -9
    deviated = build_snapshot(runtime, "demo-mission", adapter)
    moved = next(e for e in deviated.events if e.event_id == ka.event_id)
    assert moved.due_at < ka.due_at
    position.latitude = 0
    rejoined = build_snapshot(runtime, "demo-mission", adapter)
    # Spherical projection changes slightly off-route; both use the same engine.
    assert (
        abs(
            (
                next(e for e in rejoined.events if e.event_id == ka.event_id).due_at
                - moved.due_at
            ).total_seconds()
        )
        < 1
    )


def test_passed_restriction_is_retired_without_planned_clock_resurrection(
    production, clock
):
    runtime, adapter = runtime_for(production, clock)
    first = restriction(build_snapshot(runtime, "demo-mission", adapter))
    position = production[2]["telemetry"].position
    position.longitude = 10
    after = build_snapshot(runtime, "demo-mission", adapter)
    ended = next(e for e in after.events if e.event_id == first.event_id)
    assert not ended.active and not ended.notification.eligible
    position.longitude = -9.5
    returned = build_snapshot(runtime, "demo-mission", adapter)
    assert not any(
        e.notification.eligible for e in returned.events if e.event_id == first.event_id
    )


def test_preflight_changed_boundary_supersedes_overlapping_occurrence(
    production, clock
):
    import json
    from pathlib import Path

    runtime, adapter = runtime_for(production, clock)
    context = adapter.context_provider
    adapter.context_provider = lambda: context() | {"phase": "pre_departure"}
    path = Path("data/sat_coverage/commka.geojson")
    raw = json.loads(path.read_text())

    def boundary(east):
        raw["features"][0]["geometry"]["coordinates"] = [
            [[-20, -10], [east, -10], [east, 10], [-20, 10], [-20, -10]]
        ]
        path.write_text(json.dumps(raw))

    boundary(-8)
    first = build_snapshot(runtime, "demo-mission", adapter)
    previous = next(e for e in first.events if e.transport == "Ka" and e.active)
    boundary(-7)
    changed = build_snapshot(runtime, "demo-mission", adapter)
    current = next(e for e in changed.events if e.transport == "Ka" and e.active)
    assert current.event_id != previous.event_id
    assert current.notification.generation != previous.notification.generation
    assert any(e.event_id == previous.event_id and not e.active for e in changed.events)


def test_airborne_stale_capture_does_not_restore_planned_pop_windows(production, clock):
    from app.mission.pop_status import PopStatusService

    runtime, adapter = runtime_for(production, clock)
    adapter.pop_service = PopStatusService(production[4], lambda: production[3])
    before = build_snapshot(runtime, "demo-mission", adapter)
    assert any(
        e.kind == "pop_advisory" and e.source_ref.endswith(":live-pop")
        for e in before.events
    )
    clock.advance(31)
    after = build_snapshot(runtime, "demo-mission", adapter)
    assert not any(
        e.kind == "pop_advisory" and e.source_ref == "model:leg-a" and e.active
        for e in after.events
    )
