"""Isolated design probe, not an application implementation or release benchmark.

Uses only public prometheus-client APIs and fictional values. No app imports,
network, files except the requested result, or background workers after exit.
"""

import argparse
import contextvars
import gc
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import signal
import threading
import time
import tracemalloc
import weakref
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from prometheus_client.core import GaugeMetricFamily

SCHEMA = (
    ("probe_position", "Fictional position", ("dimension",)),
    ("probe_latitude", "Fictional latitude", ()),
    ("probe_eta", "Fictional ETA", ("name", "eta_type")),
)
STAGING = contextvars.ContextVar("staging", default=None)


@dataclass(frozen=True)
class Frame:
    version: int
    position: tuple
    eta: tuple


def prepare(version, pois):
    return Frame(
        version,
        (float(version),) * 3,
        tuple(((f"fictional-{i}", "estimated"), float(version)) for i in range(pois)),
    )


class Store:
    def __init__(self, frame):
        self.lock, self.frame = threading.Lock(), frame

    def read(self):
        with self.lock:
            return self.frame

    def publish(self, frame, expected=None):
        with self.lock:
            if expected is not None and self.frame is not expected:
                return False
            self.frame = frame
            return True


def families(frame):
    position = GaugeMetricFamily(*SCHEMA[0][:2], labels=SCHEMA[0][2])
    for dimension, value in zip(("latitude", "longitude", "altitude"), frame.position):
        position.add_metric((dimension,), value)
    latitude = GaugeMetricFamily(*SCHEMA[1][:2])
    latitude.add_metric((), frame.position[0])
    eta = GaugeMetricFamily(*SCHEMA[2][:2], labels=SCHEMA[2][2])
    for labels, value in frame.eta:
        eta.add_metric(labels, value)
    return position, latitude, eta


class Collector:
    def __init__(self, store):
        self.store = store

    def describe(self):
        return tuple(
            GaugeMetricFamily(name, help_text, labels=labels)
            for name, help_text, labels in SCHEMA
        )

    def collect(self):
        return families(self.store.read())


class GaugeView:
    """Probe only: label/set compatibility stages values, never stores a copy."""

    def __init__(self, name, labels=(), labelnames=()):
        self.name, self.labelvalues, self.labelnames = name, labels, labelnames

    def labels(self, *labels, **kwargs):
        assert not (labels and kwargs)
        if kwargs:
            assert set(kwargs) == set(self.labelnames)
            labels = tuple(kwargs[name] for name in self.labelnames)
        assert len(labels) == len(self.labelnames)
        return GaugeView(self.name, tuple(labels), self.labelnames)

    def set(self, value):
        staging = STAGING.get()
        if staging is None:
            raise RuntimeError("coupled write requires a producer frame")
        staging[(self.name, self.labelvalues)] = float(value)


@contextmanager
def staging_values():
    values = {}
    token = STAGING.set(values)
    try:
        yield values
    finally:
        STAGING.reset(token)


def make_registry(pois, snapshot):
    registry = CollectorRegistry()
    store = Store(prepare(1, pois))
    if snapshot:
        registry.register(Collector(store))
    else:
        position = Gauge(*SCHEMA[0][:2], SCHEMA[0][2], registry=registry)
        latitude = Gauge(*SCHEMA[1][:2], registry=registry)
        eta = Gauge(*SCHEMA[2][:2], SCHEMA[2][2], registry=registry)
        for dimension in ("latitude", "longitude", "altitude"):
            position.labels(dimension).set(1)
        latitude.set(1)
        for i in range(pois):
            eta.labels(f"fictional-{i}", "estimated").set(1)
    counter = Counter("probe_updates", "Independent updates", registry=registry)
    histogram = Histogram("probe_cost", "Independent duration", registry=registry)
    gep = Gauge("probe_gep", "Independent GEP", registry=registry)
    return registry, store, counter, histogram, gep


def values(metrics):
    return [
        s.value
        for m in metrics
        if m.name.startswith(("probe_position", "probe_latitude", "probe_eta"))
        for s in m.samples
    ]


def proofs():
    registry, store, counter, histogram, gep = make_registry(10, True)
    captured = tuple(registry.collect())
    before = values(captured)
    store.publish(prepare(2, 11))
    assert values(captured) == before == [1.0] * 14
    assert set(values(registry.collect())) == {2.0}
    # Preparation failure and label creation do not touch the committed state.
    pending = prepare(3, 12)
    assert store.read().version == 2 and len(store.read().eta) == 11
    del pending
    view = GaugeView("probe_eta", labelnames=("name", "eta_type"))
    try:
        view.labels("x", "estimated").set(3)
    except RuntimeError:
        pass
    else:
        raise AssertionError("unguarded write accepted")
    with staging_values() as staged:
        view.labels(name="x", eta_type="estimated").set(3)
        assert staged[("probe_eta", ("x", "estimated"))] == 3
        assert store.read().version == 2
    counter.inc()
    histogram.observe(0.25, exemplar={"trace_id": "fictional"})
    gep.set(12)
    assert registry.get_sample_value("probe_updates_total") == 1
    assert registry.get_sample_value("probe_cost_count") == 1
    assert registry.get_sample_value("probe_cost_sum") == 0.25
    assert store.read().version == 2
    assert b"probe_updates_created" in generate_latest(registry)
    assert any(
        sample.exemplar is not None
        for metric in registry.collect()
        if metric.name == "probe_cost"
        for sample in metric.samples
    )
    callback = Gauge(
        "probe_independent_callback", "Read only callback", registry=registry
    )
    callback.set_function(lambda: 7.0)
    assert registry.get_sample_value("probe_independent_callback") == 7
    assert store.read().version == 2
    # Deterministic reader/writer overlap, with no lock held while collecting.
    entered, release = threading.Event(), threading.Event()
    retained = []

    def reader():
        frame = store.read()
        entered.set()
        assert release.wait(5)
        retained.extend(families(frame))

    thread = threading.Thread(target=reader)
    thread.start()
    try:
        assert entered.wait(5)
        store.publish(prepare(4, 13))
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive() and set(values(retained)) == {2.0}
    old = store.read()
    store.publish(prepare(5, 13))  # Configuration/mission changed during preparation.
    assert not store.publish(prepare(6, 14), expected=old)
    assert store.read().version == 5
    retained_frames, bounded = [], Store(prepare(0, 1))
    for version in range(100):
        frame = prepare(version, 1)
        retained_frames.append(weakref.ref(frame))
        bounded.publish(frame)
    del frame
    gc.collect()
    assert sum(ref() is not None for ref in retained_frames) == 1
    return {
        "detached_old_frame": True,
        "dynamic_labels": True,
        "failed_prepare_unchanged": True,
        "independent_client_types": True,
        "compatibility_staging": True,
        "barrier_overlap": True,
        "superseded_input_rejected": True,
        "standard_exemplars": True,
        "no_generation_history": True,
        "independent_readonly_callback": True,
    }


def benchmark(pois, snapshot, iterations):
    registry, store, *_ = make_registry(pois, snapshot)
    cpu, wall = [], []
    for _ in range(iterations):
        start, began = time.thread_time_ns(), time.perf_counter_ns()
        generate_latest(registry)
        cpu.append((time.thread_time_ns() - start) / 1e6)
        wall.append((time.perf_counter_ns() - began) / 1e6)
    gc.collect()
    tracemalloc.start()
    generate_latest(registry)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    tracemalloc.start()
    began = time.thread_time_ns()
    frame = prepare(2, pois)
    prepare_cpu_us = (time.thread_time_ns() - began) / 1000
    retained_bytes, frame_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    start = time.thread_time_ns()
    for _ in range(iterations):
        store.publish(frame)
    return {
        "pois": pois,
        "mode": "snapshot" if snapshot else "raw_client_unsafe_control",
        "samples": iterations,
        "cpu_p50_ms": sorted(cpu)[math.ceil(0.50 * len(cpu)) - 1],
        "cpu_p95_ms": sorted(cpu)[math.ceil(0.95 * len(cpu)) - 1],
        "wall_p95_ms": sorted(wall)[math.ceil(0.95 * len(wall)) - 1],
        "separate_one_scrape_tracemalloc_peak_bytes": peak,
        "separate_traced_frame_prepare_cpu_us": prepare_cpu_us,
        "separate_frame_retained_bytes": retained_bytes,
        "separate_frame_peak_bytes": frame_peak,
        "prebuilt_pointer_publish_mean_us": (time.thread_time_ns() - start)
        / iterations
        / 1000,
    }


def contention(seconds, pois):
    registry, store, counter, histogram, _ = make_registry(pois, True)
    stop, barrier = threading.Event(), threading.Barrier(5)
    failures, counts = [], [0] * 4

    def worker(index):
        try:
            barrier.wait(5)
            deadline = time.monotonic()
            while not stop.is_set():
                if index == 0:
                    store.publish(prepare(counts[index] + 2, pois))
                    counter.inc()
                    histogram.observe(0.001)
                else:
                    assert len(set(values(registry.collect()))) == 1
                    generate_latest(registry)
                counts[index] += 1
                deadline += 1
                stop.wait(max(0, deadline - time.monotonic()))
        except BaseException as error:  # noqa: BLE001 - report worker failure to parent

            failures.append(repr(error))
            stop.set()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    try:
        for thread in threads:
            thread.start()
        barrier.wait(5)
        stop.wait(seconds)
    finally:
        stop.set()
        for thread in threads:
            thread.join(5)
    assert not failures and not any(t.is_alive() for t in threads), failures
    return {
        "seconds": seconds,
        "pois": pois,
        "writer_hz": 1,
        "scrapers": 3,
        "counts": counts,
        "mixed_frames": 0,
        "retries": 0,
        "remaining_threads": 0,
    }


def interrupted(signum, _frame):
    raise SystemExit(128 + signum)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--iterations", type=int, default=100)
    args = parser.parse_args()
    if (
        args.output.exists()
        or not 1 <= args.seconds <= 60
        or not 10 <= args.iterations <= 200
    ):
        parser.error("new output, seconds 1..60, iterations 10..200 required")
    result = {
        "pid": os.getpid(),
        "pgid": os.getpgrp(),
        "python": platform.python_version(),
        "client": importlib.metadata.version("prometheus-client"),
        "scope": __doc__,
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.output.write_text(json.dumps(result, indent=2))
    result["proofs"] = proofs()
    result["measurements"] = [
        benchmark(n, mode, args.iterations)
        for n in (0, 10, 100, 1100)
        for mode in (False, True)
    ]
    result["contention"] = contention(args.seconds, 1100)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
