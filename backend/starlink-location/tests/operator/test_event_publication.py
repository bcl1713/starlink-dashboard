"""Capture leases pin only proven local publication generations."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from app.operator.errors import OperatorError


def test_replaced_publication_rejects_stale_guard(clock):
    from app.operator.event_publication import EventPublication
    from app.operator.event_models import SourceCapture

    gate = EventPublication()
    old = SourceCapture(
        source="model",
        revision="one",
        generation="one",
        aligned=True,
        guardable=True,
        freshness="fresh",
        captured_at=clock.now(),
    )
    gate.publish(old)
    gate.publish(old.model_copy(update={"generation": "two"}))
    with pytest.raises(OperatorError, match="event_snapshot_changed"):
        with gate.guard((old,)):
            pytest.fail("stale publication was admitted")


def test_publisher_waits_until_lease_released(clock):
    from app.operator.event_publication import EventPublication
    from app.operator.event_models import SourceCapture

    gate = EventPublication()
    old = SourceCapture(
        source="model",
        generation="one",
        guardable=True,
        aligned=True,
        freshness="fresh",
        captured_at=clock.now(),
    )
    gate.publish(old)
    started, finished = Event(), Event()

    def publish():
        started.set()
        gate.publish(old.model_copy(update={"generation": "two"}))
        finished.set()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with gate.guard((old,)):
            future = pool.submit(publish)
            assert started.wait(2)
            assert not finished.is_set()
        future.result(timeout=2)
    assert finished.is_set()


def test_unknown_or_unguardable_sources_fail_closed(clock):
    from app.operator.event_publication import EventPublication
    from app.operator.event_models import SourceCapture

    gate = EventPublication()
    source = SourceCapture(source="saved", generation="one")
    gate.publish(source)
    with pytest.raises(OperatorError, match="event_source_unavailable"):
        with gate.guard((source,)):
            pytest.fail("unguardable source admitted")


def test_registry_is_pinned_expires_and_is_bounded(clock):
    from app.operator.event_publication import SnapshotRegistry
    from app.operator.event_models import EventSnapshot

    registry = SnapshotRegistry(clock=clock, capacity=2)
    original = EventSnapshot(
        store_id="store",
        api_epoch="epoch",
        mission_id="demo-mission",
        source_mode="live",
        as_of=clock.now(),
        H=0,
        generation="one",
    )
    token = registry.issue(original)
    original.generation = "mutated"
    assert registry.resolve(token).generation == "one"
    clock.advance(120)
    with pytest.raises(OperatorError, match="event_snapshot_changed"):
        registry.resolve(token)
    tokens = [registry.issue(original) for _ in range(3)]
    with pytest.raises(OperatorError):
        registry.resolve(tokens[0])
    assert registry.resolve(tokens[-1]).generation == "mutated"
