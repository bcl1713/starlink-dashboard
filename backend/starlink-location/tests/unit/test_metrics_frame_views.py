"""Narrow staged setters: binding a label must never publish a child."""

import pytest
from app.core.metrics.frames import (
    FrameGaugeView,
    FrameIdentity,
    FrameStore,
    GaugeDefinition,
    TelemetryFrameCollector,
)
from prometheus_client import CollectorRegistry


def setup_views():
    definition = GaugeDefinition("eta", "ETA", ("poi", "kind"))
    store = FrameStore((definition,))
    return store, FrameGaugeView(store, definition)


def test_labels_bind_without_visible_child():
    store, view = setup_views()
    child = view.labels("new", "estimated")
    registry = CollectorRegistry()
    registry.register(TelemetryFrameCollector(store, store.schema))
    assert registry.get_sample_value("eta", {"poi": "new", "kind": "estimated"}) is None
    with pytest.raises(RuntimeError):
        child.set(3)
    with store.prepare(FrameIdentity(), 0) as builder:
        child.set(3)
        view.labels(kind="estimated", poi="new").set(4)
        assert not next(view.collect()).samples
        frame = builder.seal()
    assert store.publish(store.read(), frame)
    assert registry.get_sample_value("eta", {"poi": "new", "kind": "estimated"}) == 4
    assert next(child.collect()).samples == next(view.collect()).samples
    assert not hasattr(view, "_value") and not hasattr(view, "_metrics")


@pytest.mark.parametrize(
    "args,kwargs",
    [
        (("a",), {}),
        ((), {"poi": "a"}),
        (("a", "b"), {"poi": "a"}),
        ((), {"poi": "a", "wrong": "b"}),
    ],
)
def test_invalid_label_binding(args, kwargs):
    _, view = setup_views()
    with pytest.raises(ValueError):
        view.labels(*args, **kwargs)


def test_abandoned_builder_and_foreign_store_cannot_leak_labels():
    store, view = setup_views()
    _other, other_view = setup_views()
    with store.prepare(FrameIdentity(), 0):
        view.labels("abandoned", "estimated").set(10)
        with pytest.raises(RuntimeError):
            other_view.labels("foreign", "estimated").set(20)
    with pytest.raises(RuntimeError):
        view.labels("late", "estimated").set(30)
    assert not next(view.collect()).samples
    assert not next(other_view.collect()).samples


def test_unlabelled_and_incomplete_preparation():
    definition = GaugeDefinition("x", "X", ())
    store = FrameStore((definition,))
    view = FrameGaugeView(store, definition)
    with pytest.raises(ValueError):
        view.labels("extra")
    with store.prepare(FrameIdentity(), 0) as builder:
        with pytest.raises(ValueError):
            builder.seal()
        view.set(6)
        frame = builder.seal()
        with pytest.raises(RuntimeError):
            view.set(7)
    assert store.publish(store.read(), frame)
    assert next(view.collect()).samples[0].value == 6


@pytest.mark.asyncio
async def test_inherited_async_context_cannot_write_another_producers_frame():
    import asyncio

    store, view = setup_views()

    async def child():
        with pytest.raises(RuntimeError):
            view.labels("child", "estimated").set(99)

    with store.prepare(FrameIdentity(), 0) as builder:
        view.labels("owner", "estimated").set(1)
        await asyncio.create_task(child())
        assert store.publish(store.read(), builder.seal())
    assert [s.labels["poi"] for s in next(view.collect()).samples] == ["owner"]


def test_sync_preparation_rejects_nested_event_loop_producer():
    import asyncio

    store, view = setup_views()

    async def child():
        with pytest.raises(RuntimeError):
            view.labels("child", "estimated").set(99)

    with store.prepare(FrameIdentity(), 0) as builder:
        view.labels("owner", "estimated").set(1)
        asyncio.run(child())
        assert store.publish(store.read(), builder.seal())
    assert [s.labels["poi"] for s in next(view.collect()).samples] == ["owner"]
