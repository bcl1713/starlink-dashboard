"""Atomicity, ownership and public-registry compatibility for unwired frames."""

import dataclasses
import gc
import math
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor

import pytest
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from prometheus_client.openmetrics.exposition import generate_latest as openmetrics

from app.core.metrics.frames import (
    FrameIdentity,
    FrameStore,
    GaugeDefinition,
    GaugeFrame,
    TelemetryFrameCollector,
)
from tests.unit.metrics_frame_support import actual_schema


def prepared(store, value=1, label="old", mode="live", revision=None):
    head = store.read()
    identity = FrameIdentity(
        mode=mode,
        observation_id=str(value),
        input_revision=head.input_revision if revision is None else revision,
    )
    with store.prepare(identity, 123.0) as builder:
        for definition in store.schema:
            labels = [label] * len(definition.labelnames)
            builder.set(definition, labels, value)
        return builder.seal()


def registered(store):
    registry = CollectorRegistry(auto_describe=True)
    registry.register(TelemetryFrameCollector(store, store.schema))
    return registry


def test_old_frame_survives_pointer_and_label_change():
    store = FrameStore(actual_schema())
    old = prepared(store)
    assert store.publish(store.read(), old)
    reader = iter(TelemetryFrameCollector(store, store.schema).collect())
    first = next(reader)
    assert store.publish(store.read(), prepared(store, 2, "new"))
    samples = first.samples + [s for family in reader for s in family.samples]
    assert all(s.value == 1 for s in samples)
    assert "new" not in repr(samples)
    with pytest.raises(dataclasses.FrozenInstanceError):
        old.identity.mode = "simulation"


def test_reader_paused_between_families_sees_one_frame():
    store = FrameStore(actual_schema())
    store.publish(store.read(), prepared(store))
    paused, resume = threading.Event(), threading.Event()

    def scrape():
        iterator = iter(TelemetryFrameCollector(store, store.schema).collect())
        first = next(iterator)
        paused.set()
        assert resume.wait(5)
        return first.samples + [s for f in iterator for s in f.samples]

    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(scrape)
        try:
            assert paused.wait(5)
            assert store.publish(store.read(), prepared(store, 7, "new"))
        finally:
            resume.set()
        assert {s.value for s in future.result(5)} == {1}


def test_all_29_schemas_and_position_alias_match_baseline():
    from app.core.metrics import prometheus_metrics as baseline

    store = FrameStore(actual_schema())
    registry = registered(store)
    for definition in store.schema:
        family = next(iter(getattr(baseline, definition.name).collect()))
        assert (family.name, family.documentation, family.type, family.unit) == (
            definition.name,
            definition.documentation,
            "gauge",
            "",
        )
    store.publish(store.read(), prepared(store, 9))
    families = list(registry.collect())
    assert len(families) == 30
    position = next(f for f in families if f.name == "starlink_aircraft_position")
    original = next(baseline.PositionCollector().collect())
    assert (position.name, position.documentation, position.type, position.unit) == (
        original.name,
        original.documentation,
        original.type,
        original.unit,
    )
    assert [s.labels for s in position.samples] == [
        {"dimension": "latitude"},
        {"dimension": "longitude"},
        {"dimension": "altitude"},
    ]
    assert registry.get_sample_value("starlink_dish_speed_knots") == 9
    assert b"# TYPE starlink_eta_poi_seconds gauge" in generate_latest(registry)
    assert openmetrics(registry).endswith(b"# EOF\n")


def test_superseded_prepare_cannot_publish_or_fail_new_head():
    store = FrameStore(actual_schema())
    expected = store.read()
    stale = prepared(store)
    pending = store.invalidate("source replacement")
    assert pending.input_revision == expected.input_revision + 1
    new = prepared(store, 2, mode="replay")
    assert store.publish(pending, new)
    assert not store.publish(expected, stale)
    assert not store.fail(expected, "late exception")
    assert store.read().frame is new
    assert store.read().frame.identity.mode == "replay"
    with pytest.raises(ValueError):
        store.publish(store.read(), stale)


def test_failed_preparation_preserves_frame_and_masks_without_renewing_time():
    store = FrameStore(actual_schema())
    store.publish(store.read(), prepared(store))
    head = store.read()
    with pytest.raises(RuntimeError), store.prepare(
        FrameIdentity(input_revision=0), 999
    ) as builder:
        builder.set(store.schema[0], (), 999)
        raise RuntimeError("incomplete")
    assert store.read() is head
    assert store.fail(head, "preparation failed")
    failed = store.read()
    assert failed.frame is head.frame
    assert failed.frame.last_observation_publication_time == 123
    families = list(registered(store).collect())
    for family in families:
        for sample in family.samples:
            if sample.name == "starlink_metrics_last_update_timestamp_seconds":
                assert (
                    sample.value == 1
                )  # prior metric, not wall clock or failed attempt
            else:
                assert math.isnan(sample.value)
    assert store.publish(failed, prepared(store, 2))
    assert store.read().status == "ready"


def test_frame_takes_ownership_and_retains_no_generation_history():
    definition = GaugeDefinition("x", "X", ["label"])
    store = FrameStore((definition,))
    mutable = [[(["before"], 3)]]
    frame = GaugeFrame(FrameIdentity(), mutable, 4)
    mutable[0][0][0][0] = "after"
    mutable[0].append((["other"], 5))
    assert frame.families == (((("before",), 3.0),),)
    refs = []
    for i in range(100):
        candidate = prepared(store, i)
        refs.append(weakref.ref(candidate))
        store.publish(store.read(), candidate)
    del candidate
    gc.collect()
    assert sum(ref() is not None for ref in refs) == 1
    assert frame.families[0][0][0] == ("before",)


@pytest.mark.parametrize("malformation", ["missing", "labels", "duplicate", "unknown"])
def test_invalid_frame_never_replaces_head(malformation):
    definition = GaugeDefinition("x", "X", ("label",))
    store = FrameStore((definition,))
    head = store.read()
    if malformation == "unknown":
        with store.prepare(FrameIdentity(), 0) as builder, pytest.raises(ValueError):
            builder.set(GaugeDefinition("y", "Y", ()), (), 1)
    else:
        families = {
            "missing": (),
            "labels": ((((), 1),),),
            "duplicate": (((("a",), 1), (("a",), 2)),),
        }[malformation]
        frame = GaugeFrame(FrameIdentity(), families, 0)
        with pytest.raises(ValueError):
            store.publish(head, frame)
    assert store.read() is head


def test_independent_instruments_survive_snapshot_abort_and_publish():
    store = FrameStore(actual_schema())
    registry = registered(store)
    count = Counter("events", "Events", ["source"], registry=registry)
    histogram = Histogram(
        "latency", "Latency", ["source"], buckets=[1, 2], registry=registry
    )
    callback = Gauge("independent", "Independent", registry=registry)
    callback.set_function(lambda: 42)
    count.labels(source="live").inc(2, exemplar={"trace": "counter"})
    histogram.labels(source="live").observe(1.5, exemplar={"trace": "histogram"})
    count.labels(source="idle")
    histogram.labels(source="idle")
    before = openmetrics(registry)
    head = store.read()
    assert store.fail(head, "abort")
    assert store.publish(store.read(), prepared(store))
    after = openmetrics(registry)
    independent = lambda data: [
        line
        for line in data.splitlines()
        if line.startswith((b"events", b"latency", b"independent"))
    ]
    assert independent(before) == independent(after)
    assert isinstance(count, Counter) and isinstance(histogram, Histogram)
    assert registry.get_sample_value("events_total", {"source": "idle"}) == 0
    assert registry.get_sample_value("latency_count", {"source": "idle"}) == 0
    assert b'latency_count{source="live"} 1.0' in after
    assert b'latency_sum{source="live"} 1.5' in after
    assert b'latency_bucket{le="2.0",source="live"} 1.0' in after
    assert b"events_created" in after and b"latency_created" in after
    assert b'trace="counter"' in after and b'trace="histogram"' in after


def test_collection_and_serialization_release_publication_mutex(monkeypatch):
    import app.core.metrics.frames as module

    store = FrameStore(actual_schema())
    store.publish(store.read(), prepared(store))
    original = module.GaugeMetricFamily

    def checked(*args, **kwargs):
        assert store._lock.acquire(blocking=False)
        store._lock.release()
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "GaugeMetricFamily", checked)
    registry = registered(store)
    assert b"starlink_aircraft_position" in generate_latest(registry)


def test_concurrent_publication_scrapes_and_invalidation():
    store = FrameStore(actual_schema())
    store.publish(store.read(), prepared(store))

    def writer():
        for i in range(100):
            head = store.read()
            frame = prepared(store, i + 2, f"poi-{i}", revision=head.input_revision)
            store.publish(head, frame)

    def invalidator():
        for _ in range(100):
            head = store.invalidate("mission/config")
            store.fail(head, "temporary")

    def reader():
        for _ in range(100):
            samples = [
                s
                for f in TelemetryFrameCollector(store, store.schema).collect()
                for s in f.samples
                if f.name != "starlink_metrics_last_update_timestamp_seconds"
            ]
            values = {s.value for s in samples if not math.isnan(s.value)}
            assert len(values) <= 1
            assert all(math.isnan(s.value) for s in samples) or len(values) == 1

    with ThreadPoolExecutor(5) as pool:
        futures = [pool.submit(reader) for _ in range(3)]
        futures += [pool.submit(writer), pool.submit(invalidator)]
        for future in futures:
            future.result(20)


def test_full_schema_exposition_matches_standard_gauges():
    schema = actual_schema()
    store = FrameStore(schema)
    registry = registered(store)
    control = CollectorRegistry()
    from app.core.metrics.prometheus_metrics import PositionCollector

    control.register(PositionCollector())
    with store.prepare(FrameIdentity(), 123) as builder:
        for definition in schema:
            gauge = Gauge(
                definition.name,
                definition.documentation,
                definition.labelnames,
                registry=control,
            )
            labels = tuple('a"\\\n' for _ in definition.labelnames)
            builder.set(definition, labels, 0)
            (gauge.labels(*labels) if labels else gauge).set(0)
        store.publish(store.read(), builder.seal())
    assert sorted(generate_latest(registry).splitlines()) == sorted(
        generate_latest(control).splitlines()
    )


@pytest.mark.parametrize("count", [0, 10, 100, 1100])
def test_dynamic_poi_replacement_is_bounded(count):
    definition = GaugeDefinition("eta", "ETA", ("poi",))
    store = FrameStore((definition,))
    for prefix in ("old", "new"):
        with store.prepare(FrameIdentity(mode="simulation"), 12) as builder:
            for i in range(count):
                builder.set(definition, (f"{prefix}-{i}",), i)
            assert store.publish(store.read(), builder.seal())
    samples = next(iter(registered(store).collect())).samples
    assert len(samples) == count
    assert all(s.labels["poi"].startswith("new-") for s in samples)


def test_retained_reader_owns_old_frame_until_iterator_released():
    store = FrameStore(actual_schema())
    frame = prepared(store)
    ref = weakref.ref(frame)
    store.publish(store.read(), frame)
    reader = iter(TelemetryFrameCollector(store, store.schema).collect())
    next(reader)
    store.publish(store.read(), prepared(store, 2))
    del frame
    gc.collect()
    assert ref() is not None
    reader.close()
    gc.collect()
    assert ref() is None


def test_replay_identity_is_detached_and_refresh_does_not_advance_source():
    store = FrameStore(actual_schema())
    identity = FrameIdentity(
        mode="replay",
        coordinator_id="c",
        observation_id="o",
        observation_timestamp=123,
        route_id="route",
        poi_id="pois",
        phase_id="phase",
        replay_runtime_id="runtime",
        replay_run_id="run",
        replay_revision="17",
        replay_mission_time=45,
    )
    for value in (1, 2):
        with store.prepare(identity, 123) as builder:
            for definition in store.schema:
                builder.set(definition, ["label"] * len(definition.labelnames), value)
            assert store.publish(store.read(), builder.seal())
    assert store.read().frame.identity is identity
    assert identity.observation_timestamp == 123
    assert identity.replay_mission_time == 45
    assert store.read().frame.last_observation_publication_time == 123


def test_position_alias_uses_correct_dimensions_from_one_frame():
    store = FrameStore(actual_schema())
    values = {
        "starlink_dish_latitude_degrees": 12.25,
        "starlink_dish_longitude_degrees": -45.5,
        "starlink_dish_altitude_feet": 32001.0,
    }
    with store.prepare(FrameIdentity(), 0) as builder:
        for definition in store.schema:
            builder.set(
                definition,
                ["label"] * len(definition.labelnames),
                values.get(definition.name, 7),
            )
        store.publish(store.read(), builder.seal())
    alias = next(
        f for f in registered(store).collect() if f.name == "starlink_aircraft_position"
    )
    assert [(s.labels["dimension"], s.value) for s in alias.samples] == [
        ("latitude", 12.25),
        ("longitude", -45.5),
        ("altitude", 32001.0),
    ]
