"""Task 1 component costs, not application savings or a soak. Run from repo root."""

import argparse
import dataclasses
import gc
import hashlib
import importlib.metadata
import json
import math
import os
import statistics
import sys
import threading
import time
import tracemalloc
import weakref
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend/starlink-location"))
from app.core.metrics.frames import (
    FrameIdentity,
    FrameStore,
    GaugeFrame,
    TelemetryFrameCollector,
)
from prometheus_client import CollectorRegistry, generate_latest
from tests.unit.metrics_frame_support import actual_schema


def fixture(schema, count, generation=1):
    families = []
    for definition in schema:
        size = (
            count
            if definition.name
            in ("starlink_eta_poi_seconds", "starlink_distance_to_poi_meters")
            else 1
        )
        families.append(
            tuple(
                (
                    tuple(f"{generation}-{i}-{name}" for name in definition.labelnames),
                    float(generation),
                )
                for i in range(size)
            )
        )
    return tuple(families)


def prepare(store, data, generation=1):
    identity = FrameIdentity(
        mode="simulation",
        observation_id=str(generation),
        input_revision=store.read().input_revision,
    )
    with store.prepare(identity, 123) as builder:
        for definition, family in zip(store.schema, data):
            for labels, value in family:
                builder.set(definition, labels, value)
        return builder.seal()


def distribution(values):
    ordered = sorted(values)
    return {
        "p50": statistics.median(ordered),
        "p95": ordered[math.ceil(len(ordered) * 0.95) - 1],
        "p99": ordered[math.ceil(len(ordered) * 0.99) - 1],
    }


def measure(operation, iterations):
    cpu, wall = [], []
    for _ in range(10):
        operation()
    for _ in range(iterations):
        start_wall, start_cpu = time.perf_counter_ns(), time.thread_time_ns()
        operation()
        cpu.append(time.thread_time_ns() - start_cpu)
        wall.append(time.perf_counter_ns() - start_wall)
    return {"thread_cpu_ns": distribution(cpu), "wall_ns": distribution(wall)}


def allocation(operation):
    gc.collect()
    tracemalloc.start()
    result = operation()
    current, peak = tracemalloc.get_traced_memory()
    blocks = sum(
        stat.count for stat in tracemalloc.take_snapshot().statistics("filename")
    )
    tracemalloc.stop()
    del result
    return {
        "retained_result_bytes": current,
        "peak_bytes": peak,
        "retained_result_blocks": blocks,
    }


def owned_size(value, seen=None):
    seen = set() if seen is None else seen
    if id(value) in seen:
        return 0
    seen.add(id(value))
    size = sys.getsizeof(value)
    if dataclasses.is_dataclass(value):
        return size + sum(
            owned_size(getattr(value, f.name), seen) for f in dataclasses.fields(value)
        )
    if isinstance(value, tuple):
        return size + sum(owned_size(item, seen) for item in value)
    return size


def row(schema, count, iterations):
    store = FrameStore(schema)
    data = fixture(schema, count)
    frame = prepare(store, data)
    store.publish(store.read(), frame)
    collector = TelemetryFrameCollector(store, schema)
    registry = CollectorRegistry()
    registry.register(collector)
    operations = {
        "freeze_detached_samples": lambda frame=frame: GaugeFrame(
            frame.identity, data, 123
        ),
        "stage_and_seal": lambda: prepare(store, data),
        "validated_publish": lambda frame=frame: store.publish(store.read(), frame),
        "capture_head": store.read,
        "collect": lambda: list(collector.collect()),
        "serialize_registry": lambda: generate_latest(registry),
    }
    result = {
        "pois": count,
        "samples": sum(len(f.samples) for f in collector.collect()),
        "frame_reachable_bytes": owned_size(frame),
        "timings": {name: measure(op, iterations) for name, op in operations.items()},
        "allocation": {name: allocation(op) for name, op in operations.items()},
    }
    refs = []
    del operations, frame
    for generation in range(100):
        candidate = prepare(store, fixture(schema, count, generation), generation)
        refs.append(weakref.ref(candidate))
        store.publish(store.read(), candidate)
    del candidate
    gc.collect()
    result["live_frames_after_100_replacements"] = sum(
        ref() is not None for ref in refs
    )
    return result


def contention(schema, seconds):
    store = FrameStore(schema)
    store.publish(store.read(), prepare(store, fixture(schema, 1100)))
    collector = TelemetryFrameCollector(store, schema)
    stop = threading.Event()
    barrier = threading.Barrier(4)
    costs = {"publish": [], "capture_head": []}

    def worker(writer):
        barrier.wait(timeout=5)
        count = 0
        deadline = time.monotonic()
        while count < seconds and not stop.is_set():
            if writer:
                frame = prepare(store, fixture(schema, 1100, count + 2), count + 2)
                expected = store.read()
                start = time.perf_counter_ns()
                assert store.publish(expected, frame)
                costs["publish"].append(time.perf_counter_ns() - start)
            else:
                start = time.perf_counter_ns()
                store.read()
                costs["capture_head"].append(time.perf_counter_ns() - start)
                samples = [sample for f in collector.collect() for sample in f.samples]
                assert len({sample.value for sample in samples}) == 1
            count += 1
            deadline += 1
            stop.wait(max(0, deadline - time.monotonic()))
        return count

    try:
        with ThreadPoolExecutor(4, thread_name_prefix="perf391-task1") as pool:
            futures = [
                pool.submit(worker, writer) for writer in (True, False, False, False)
            ]
            counts = [future.result(seconds + 10) for future in futures]
    finally:
        stop.set()
    return {
        "seconds": seconds,
        "writer_and_reader_operations": counts,
        "mixed_frames": 0,
        "wall_ns": {name: distribution(values) for name, values in costs.items()},
        "remaining_owned_threads": sum(
            t.name.startswith("perf391-task1") for t in threading.enumerate()
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--contention-seconds", type=int, default=30)
    args = parser.parse_args()
    schema = actual_schema()
    print(
        json.dumps(
            {
                "owner_pid": os.getpid(),
                "owner_pgid": os.getpgrp(),
                "output": str(args.output),
            }
        ),
        flush=True,
    )
    result = {
        "client": importlib.metadata.version("prometheus-client"),
        "python": sys.version,
        "pid": os.getpid(),
        "pgid": os.getpgrp(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "frame_module_sha256": hashlib.sha256(
            (ROOT / "backend/starlink-location/app/core/metrics/frames.py").read_bytes()
        ).hexdigest(),
        "schema_fixture_sha256": hashlib.sha256(
            (
                ROOT
                / "backend/starlink-location/tests/fixtures/metrics-coupled-schema.json"
            ).read_bytes()
        ).hexdigest(),
        "iterations": args.iterations,
        "rows": [row(schema, n, args.iterations) for n in (0, 10, 100, 1100)],
        "contention": contention(schema, args.contention_seconds),
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "client": result["client"],
                "output": str(args.output),
                "contention": result["contention"],
            }
        )
    )


if __name__ == "__main__":
    main()
