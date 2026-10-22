"""Bounded host sampling and conservative counter/anchor arithmetic.

The immutable #407 adapter supplies global/cgroup files. Process/thread reads
use a bounded directory iterator, avoiding an unbounded /proc task listing.
No process-local application timestamps are converted into host time.
"""

import itertools
import os
import time
from pathlib import Path

FILE_LIMIT = 65536
SAMPLE_LIMIT = 8 * 1024 * 1024


def sample(
    collector,
    *,
    proc_root=Path("/proc"),
    pids=(),
    cgroups=(),
    max_threads=256,
    now=time.monotonic_ns
):
    pids, cgroups = tuple(pids), tuple(cgroups)
    if (
        len(pids) > 8
        or len(cgroups) > 16
        or not 1 <= max_threads <= 256
        or any(type(p) is not int or p < 1 for p in pids)
    ):
        raise ValueError("host input budget")
    root = Path(proc_root)
    began = now()
    files = collector.adapters.sample_resources(proc_root=root, cgroups=cgroups)[
        "files"
    ]
    remaining = SAMPLE_LIMIT
    for item in files.values():
        size = len((item["value"] or "").encode())
        if size > remaining:
            item.update(value=None, reason="sample_limit")
        else:
            remaining -= size

    def read(path):
        nonlocal remaining
        path = Path(path)
        try:
            with path.open("rb") as f:
                raw = f.read(min(FILE_LIMIT, remaining) + 1)
            if len(raw) > FILE_LIMIT:
                result = {"value": None, "reason": "file_limit"}
            elif len(raw) > remaining:
                result = {"value": None, "reason": "sample_limit"}
            else:
                remaining -= len(raw)
                result = {"value": raw.decode("utf-8", errors="strict"), "reason": None}
        except (OSError, UnicodeError) as error:
            result = {"value": None, "reason": type(error).__name__}
        files[str(path)] = result
        return result["value"]

    def identity(text):
        try:
            return text.rsplit(")", 1)[1].split()[19]
        except (AttributeError, IndexError):
            return None

    processes = []
    for pid in pids:
        base = root / str(pid)
        start = identity(read(base / "stat"))
        for name in ("io", "cgroup", "schedstat", "status"):
            read(base / name)
        threads = []
        try:
            with os.scandir(base / "task") as entries:
                selected = list(itertools.islice(entries, max_threads + 1))
            if len(selected) > max_threads:
                files[str(base / "task")] = {"value": None, "reason": "thread_limit"}
            for entry in sorted(selected[:max_threads], key=lambda e: int(e.name)):
                tid = int(entry.name)
                thread = base / "task" / entry.name
                threads.append(
                    {"tid": tid, "start_id": identity(read(thread / "stat"))}
                )
                read(thread / "schedstat")
        except (OSError, ValueError) as error:
            files[str(base / "task")] = {"value": None, "reason": type(error).__name__}
        # Re-read identity after counters; exited/reused processes cannot yield valid deltas.
        ending = identity(read(base / "stat"))
        processes.append(
            {
                "pid": pid,
                "start_id": start if start == ending else None,
                "reason": (
                    None
                    if start is not None and start == ending
                    else "process_identity_unavailable_or_changed"
                ),
                "threads": threads,
            }
        )
    boot = read(root / "sys/kernel/random/boot_id")
    namespace = {}
    for kind in ("pid", "time", "cgroup"):
        try:
            namespace[kind] = {
                "value": os.readlink(root / "self/ns" / kind),
                "reason": None,
            }
        except OSError as error:
            namespace[kind] = {"value": None, "reason": type(error).__name__}
    return {
        "files": files,
        "processes": processes,
        "bracket_ns": [str(began), str(now())],
        "boot_id": boot.strip() if boot else None,
        "namespaces": namespace,
        "clock_kind": "host-process CLOCK_MONOTONIC",
        "kernel": os.uname().release,
        "limits": {
            "file_bytes": FILE_LIMIT,
            "sample_bytes": SAMPLE_LIMIT,
            "threads_per_pid": max_threads,
            "pids": 8,
            "cgroups": 16,
        },
    }


def counter_delta(before, after):
    for key in ("clock_id", "identity", "epoch"):
        if not before.get(key) or before.get(key) != after.get(key):
            return {"value": None, "reason": key + "_changed_or_missing"}
    a, b = before.get("value"), after.get("value")
    if type(a) is not int or type(b) is not int or a < 0 or b < a:
        return {"value": None, "reason": "counter_missing_or_reset"}
    return {"value": b - a, "reason": None}


def anchor(clock_id, *, now=time.monotonic_ns, utc=time.time_ns):
    before = now()
    wall = utc()
    after = now()
    if after < before:
        raise ValueError("monotonic clock reset")
    return {
        "clock_id": clock_id,
        "mono_ns": str((before + after) // 2),
        "utc_ns": str(wall),
        "read_bracket_ns": [str(before), str(after)],
        "uncertainty_ns": str(after - before),
    }


def alignment(first, last):
    if first["clock_id"] != last["clock_id"] or int(last["mono_ns"]) <= int(
        first["mono_ns"]
    ):
        return {"available": False, "reason": "clock_identity_or_order"}
    drift = abs(
        (int(last["utc_ns"]) - int(last["mono_ns"]))
        - (int(first["utc_ns"]) - int(first["mono_ns"]))
    )
    uncertainty = int(first["uncertainty_ns"]) + int(last["uncertainty_ns"])
    return {
        "available": drift <= uncertainty,
        "reason": (
            "bounded_anchor_overlap" if drift <= uncertainty else "UTC_offset_step"
        ),
        "offset_change_ns": str(drift),
        "uncertainty_ns": str(uncertainty),
    }


async def observe_resources(
    collector,
    emit,
    *,
    clock_id,
    pids=(),
    cgroups=(),
    samples=1,
    now=time.monotonic_ns,
    wait=None,
    utc=time.time_ns,
    proc_root=Path("/proc")
):
    """Caller owns this coroutine; absolute deadlines, no catch-up samples."""
    import asyncio

    if not 1 <= samples <= 3600:
        raise ValueError("sample budget")

    async def default_wait(deadline):
        await asyncio.sleep(max(0, (deadline - now()) / 1e9))

    wait = wait or default_wait
    deadline = now()
    count = skipped = 0
    await emit({"kind": "anchor", "value": anchor(clock_id, now=now, utc=utc)})
    try:
        for _ in range(samples):
            await wait(deadline)
            value = sample(
                collector, proc_root=proc_root, pids=pids, cgroups=cgroups, now=now
            )
            await emit(
                {
                    "kind": "resource",
                    "clock_id": clock_id,
                    "scheduled_ns": str(deadline),
                    "value": value,
                }
            )
            await emit({"kind": "anchor", "value": anchor(clock_id, now=now, utc=utc)})
            count += 1
            deadline += 1000000000
            if deadline <= now():
                missed = (now() - deadline) // 1000000000 + 1
                skipped += missed
                deadline += missed * 1000000000
    finally:
        await emit({"kind": "anchor", "value": anchor(clock_id, now=now, utc=utc)})
        await emit(
            {
                "kind": "summary",
                "completed": count,
                "skipped": skipped,
                "complete": count == samples,
            }
        )
