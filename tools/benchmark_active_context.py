#!/usr/bin/env python3
"""Synthetic active-context benchmark; never points at real mission storage.

Run the same committed harness with --backend-root selecting each application.
Reports resolver/admission CPU and actual Python filesystem boundaries. This is
an instrumented microbenchmark, not a production latency or whole-stack claim.
"""

import argparse
import builtins
import io
import json
import logging
import os
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from contextlib import ExitStack, contextmanager
from hashlib import sha256
from math import ceil
from pathlib import Path
from unittest.mock import patch


@contextmanager
def counters():
    counts = Counter()
    original_open, original_io_open = builtins.open, io.open
    original_stat, original_iterdir, original_glob = Path.stat, Path.iterdir, Path.glob
    os_operations = {
        name: getattr(os, name)
        for name in ("stat", "lstat", "scandir", "listdir", "open")
    }

    def os_operation(name, original):
        def called(*args, **kwargs):
            counts["os_" + name + "_calls"] += 1
            return original(*args, **kwargs)

        return called

    class Reader:
        def __init__(self, handle, kind):
            self.handle, self.kind = handle, kind

        def __getattr__(self, name):
            return getattr(self.handle, name)

        def __enter__(self):
            self.handle.__enter__()
            return self

        def __exit__(self, *args):
            return self.handle.__exit__(*args)

        def read(self, *args):
            value = self.handle.read(*args)
            counts[self.kind + "_reads"] += 1
            counts["bytes_read"] += len(
                value.encode() if isinstance(value, str) else value
            )
            return value

    def opener(original):
        def opened(path, *args, **kwargs):
            handle = original(path, *args, **kwargs)
            name = str(path)
            if name.endswith("/mission.json"):
                return Reader(handle, "metadata")
            if (
                "/legs/" in name
                and name.endswith(".json")
                and not name.endswith(".timeline.json")
            ):
                return Reader(handle, "leg")
            return handle

        return opened

    def counted_stat(path, *args, **kwargs):
        counts["stat_calls"] += 1
        return original_stat(path, *args, **kwargs)

    def counted_iterdir(path):
        counts["directory_enumerations"] += 1
        return original_iterdir(path)

    def counted_glob(path, pattern, *args, **kwargs):
        counts["glob_enumerations"] += 1
        return original_glob(path, pattern, *args, **kwargs)

    class Logs(logging.Handler):
        def emit(self, record):
            counts[record.levelname.lower() + "_logs"] += 1

    from pydantic import BaseModel

    original_init = BaseModel.__init__
    original_validate = BaseModel.model_validate.__func__
    original_validate_json = BaseModel.model_validate_json.__func__

    def initialized(self, *args, **kwargs):
        counts["model_initializations"] += 1
        original_init(self, *args, **kwargs)

    def validated(cls, *args, **kwargs):
        counts["model_validations"] += 1
        return original_validate(cls, *args, **kwargs)

    def validated_json(cls, *args, **kwargs):
        counts["json_model_validations"] += 1
        return original_validate_json(cls, *args, **kwargs)

    try:
        from app.mission.repository_gate import RepositoryGate
    except ImportError:
        RepositoryGate = None
    if RepositoryGate is not None:
        original_acquire = RepositoryGate.acquire

        def acquired(self, *args, **kwargs):
            start = time.perf_counter_ns()
            try:
                return original_acquire(self, *args, **kwargs)
            finally:
                counts["gate_acquisitions"] += 1
                counts["gate_acquire_wall_ns"] += time.perf_counter_ns() - start

    handler = Logs()
    logging.getLogger().addHandler(handler)
    try:
        with ExitStack() as stack:
            for context in [
                patch("builtins.open", opener(original_open)),
                patch("io.open", opener(original_io_open)),
                patch.object(Path, "stat", counted_stat),
                patch.object(Path, "iterdir", counted_iterdir),
                patch.object(Path, "glob", counted_glob),
                patch.object(BaseModel, "__init__", initialized),
                patch.object(BaseModel, "model_validate", classmethod(validated)),
                patch.object(
                    BaseModel, "model_validate_json", classmethod(validated_json)
                ),
            ]:
                stack.enter_context(context)
            for name, original in os_operations.items():
                stack.enter_context(
                    patch.object(os, name, os_operation(name, original))
                )
            if RepositoryGate is not None:
                stack.enter_context(patch.object(RepositoryGate, "acquire", acquired))
            yield counts
    finally:
        logging.getLogger().removeHandler(handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-root", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=250)
    parser.add_argument("--application-sha")
    parser.add_argument("--missions", type=int, nargs="+", default=[0, 1, 10, 100])
    parser.add_argument("--legs", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Evidence is write-once; choose a new output path")
    if min(args.iterations, args.legs) < 1 or min(args.missions) < 0:
        parser.error("Invalid workload size")
    backend = args.backend_root.resolve()
    sys.path.insert(0, str(backend))
    from app.mission import storage
    from app.mission.active_context import resolve_active_mission_leg_context
    from app.mission.models import Mission, MissionLeg, TransportConfig
    from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
    from app.services.route_manager import RouteManager

    try:
        from app.mission.active_context_cache import (
            active_mission_snapshot_is_current,
            get_active_mission_snapshot,
        )
    except ImportError:
        get_active_mission_snapshot = None
    logging.getLogger().setLevel(logging.INFO)
    cases = []
    for count in args.missions:
        with tempfile.TemporaryDirectory(prefix="issue392-benchmark-") as temporary:
            root = Path(temporary)
            storage.MISSIONS_DIR = root / "missions"
            storage.ensure_missions_directory()
            routes = RouteManager(root / "routes")
            route = ParsedRoute(
                metadata=RouteMetadata(
                    name="fictional", file_path="fixture.kml", point_count=2
                ),
                points=[
                    RoutePoint(latitude=0, longitude=0, sequence=0),
                    RoutePoint(latitude=0, longitude=1, sequence=1),
                ],
            )
            routes.add_route("fixture", route)
            routes.activate_route("fixture")
            for index in range(count):
                mission = Mission(
                    id=f"mission-{index}",
                    name=f"Fictional {index}",
                    legs=[
                        MissionLeg(
                            id=f"leg-{leg}",
                            name=f"Leg {leg}",
                            route_id="fixture",
                            is_active=index == 0 and leg == 0,
                            transports=TransportConfig(initial_x_satellite_id="X-1"),
                        )
                        for leg in range(args.legs)
                    ],
                )
                folder = storage.MISSIONS_DIR / mission.id
                (folder / "legs").mkdir(parents=True)
                (folder / "mission.json").write_text(
                    mission.model_copy(update={"legs": []}).model_dump_json()
                )
                for leg in mission.legs:
                    (folder / "legs" / f"{leg.id}.json").write_text(
                        leg.model_dump_json()
                    )

            def operation(routes=routes, count=count):
                if get_active_mission_snapshot is not None:
                    snapshot = get_active_mission_snapshot(routes)
                    if snapshot.binding is not None:
                        assert active_mission_snapshot_is_current(routes, snapshot)
                        assert active_mission_snapshot_is_current(routes, snapshot)
                    available = snapshot.binding is not None
                else:
                    resolved = resolve_active_mission_leg_context(routes)
                    available = resolved.context is not None
                    if available:
                        expected = sha256(
                            resolved.context.parent_mission.model_dump_json().encode()
                        ).digest()
                        for _ in range(2):
                            loaded = storage.load_mission_v2(
                                resolved.context.parent_mission_id
                            )
                            assert (
                                sha256(loaded.model_dump_json().encode()).digest()
                                == expected
                            )
                assert available == (count > 0)

            with counters() as cold_counts:
                cold_start = time.perf_counter_ns()
                operation()
                cold_wall = time.perf_counter_ns() - cold_start
            walls, cpus = [], []
            with counters() as warm_counts:
                for _ in range(args.iterations):
                    start, cpu = time.perf_counter_ns(), time.thread_time_ns()
                    operation()
                    cpus.append(time.thread_time_ns() - cpu)
                    walls.append(time.perf_counter_ns() - start)

            def timing(values):
                return {
                    "mean_us": statistics.mean(values) / 1000,
                    "p95_us": sorted(values)[ceil(len(values) * 0.95) - 1] / 1000,
                }

            cases.append(
                {
                    "missions": count,
                    "legs_per_mission": args.legs,
                    "iterations": args.iterations,
                    "cold_wall_us": cold_wall / 1000,
                    "cold_counts": dict(cold_counts),
                    "warm_counts": dict(warm_counts),
                    "wall": timing(walls),
                    "thread_cpu": timing(cpus),
                }
            )
    report = {
        "harness_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
        ).strip(),
        "counter_scope": "Python file-read, Path and os boundaries; overlapping Path/os counts must not be added; no kernel trace",
        "application_sha": args.application_sha
        or subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=backend, text=True
        ).strip(),
        "scope": "Instrumented context resolution plus two admitted mission identity checks; no telemetry transport, SQLite, HTTP or browser",
        "implementation": "snapshot" if get_active_mission_snapshot else "uncached",
        "python": sys.version,
        "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
