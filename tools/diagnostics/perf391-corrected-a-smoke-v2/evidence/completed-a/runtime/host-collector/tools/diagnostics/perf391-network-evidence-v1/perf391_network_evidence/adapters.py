"""Opt-in diagnostic helpers. No application imports or automatic patching."""

import asyncio
import json
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.request import Request, urlopen

from .model import event, validate


def sample_resources(*, proc_root=Path("/proc"), cgroups=(), pids=(), max_threads=256):
    """Caller supplies visible container + ancestor cgroup directories; never infer isolation."""
    files = {}

    def read(path):
        try:
            with path.open("r") as stream:
                value = stream.read(65537)
            files[str(path)] = {
                "value": value if len(value) <= 65536 else None,
                "reason": None if len(value) <= 65536 else "file_limit",
            }
        except OSError as exc:
            files[str(path)] = {"value": None, "reason": type(exc).__name__}

    proc_root = Path(proc_root)
    for name in ("stat", "loadavg", "pressure/cpu", "pressure/io", "pressure/memory"):
        read(proc_root / name)
    for group in cgroups:
        for name in (
            "cpu.stat",
            "cpu.max",
            "cpu.pressure",
            "cpuset.cpus.effective",
            "io.stat",
            "memory.current",
        ):
            read(Path(group) / name)
    for pid in pids:
        base = proc_root / str(pid)
        for name in ("stat", "io", "cgroup", "schedstat"):
            read(base / name)
        try:
            threads = sorted((base / "task").iterdir(), key=lambda p: int(p.name))
            for thread in threads[:max_threads]:
                read(thread / "stat")  # start time distinguishes reused TIDs
                read(thread / "schedstat")
            if len(threads) > max_threads:
                files[str(base / "task")] = {"value": None, "reason": "thread_limit"}
        except OSError as exc:
            files[str(base / "task")] = {"value": None, "reason": type(exc).__name__}
    return {"files": files}


def observe_once(recorder, url, op_id, scheduled_ns, *, opener=urlopen, timeout=2):
    """Separate supplemental HTTP traffic; never attach to primary acceptance."""

    def mark(name, **kw):
        recorder.emit("boundary", {"name": "observer." + name}, op_id=op_id, **kw)

    mark("scheduled", mono_ns=scheduled_ns)
    mark("wake")
    recorder.emit(
        "coverage",
        {
            "boundary": "observer.wire_send",
            "available": False,
            "reason": "urllib send is user-space entry; kernel wire timing unavailable",
        },
    )
    try:
        request = Request(url, headers={"x-diagnostic-id": op_id})
        mark("send")
        with opener(request, timeout=timeout) as response:
            mark("headers")
            body = response.read(recorder.max_body_bytes + 1)
            mark("received")
            artifact = recorder.artifact(body)
            recorder.emit(
                "body",
                {
                    "viewer": "source-observer",
                    "request_id": op_id,
                    "status": response.status,
                    "artifact": artifact,
                },
                op_id=op_id,
            )
            if artifact["state"] == "available":
                json.loads(body)
                mark("parsed")
            else:
                recorder.emit(
                    "coverage",
                    {
                        "boundary": "observer.parse",
                        "available": False,
                        "reason": "body limit exceeded",
                    },
                )
    except (OSError, ValueError) as exc:
        recorder.emit(
            "coverage",
            {
                "boundary": "observer.response",
                "available": False,
                "reason": type(exc).__name__,
            },
            op_id=op_id,
        )
    recorder.drain()
    mark("written")
    recorder.drain()


async def diagnostic_worker(recorder, kind, op_id, func, *args, **kwargs):
    """Explicit diagnostic-build call site only. No global asyncio replacement.

    Cancellation retains the unfinished worker boundary: the caller must await
    owned workers before closing the recorder. Shield prevents orphaning it.
    """
    if kind not in ("producer", "worker"):
        raise ValueError("unknown worker kind")

    def mark(suffix, outcome=None):
        recorder.emit(
            "boundary", {"name": kind + "." + suffix, "outcome": outcome}, op_id=op_id
        )

    def work():
        mark("start")
        try:
            return func(*args, **kwargs)
        finally:
            mark("end")

    mark("dispatch")
    task = asyncio.create_task(asyncio.to_thread(work))
    try:
        result = await asyncio.shield(task)
    except asyncio.CancelledError:
        try:
            await task
        finally:
            mark("returned", "cancelled")
        raise
    except BaseException:
        mark("returned", "error")
        raise
    mark("returned", "ok")
    return result


@contextmanager
def admission(recorder, lock, op_id):
    """Depth-zero call site only; not a replacement for application admission."""
    span = uuid.uuid4().hex

    def mark(name):
        recorder.emit("boundary", {"name": "repo." + name}, op_id=op_id, span_id=span)

    mark("wait")
    lock.acquire()
    try:
        mark("acquired")
        yield
    finally:
        lock.release()
        mark("released")


def import_legacy(trace, *, run_id):
    """Loss-aware composition with f7253c68 traces; no inferred absent spans.

    Tick collection completion is NOT the underlying acquisition timestamp.
    Source validation is NOT necessarily final validation. Neither is renamed.
    Legacy lock events lack a reliable join key; retained only as unavailable.
    """
    mapping = {
        "asgi.arrival": "asgi.entry",
        "asgi.end": "asgi.end",
        "worker_dispatch.start": "worker.dispatch",
        "worker_execution.start": "worker.start",
        "worker_execution.end": "worker.end",
        "worker_dispatch.end": "worker.returned",
        "tick.dispatch": "producer.dispatch",
        "tick.start": "producer.start",
        "tick.end": "producer.end",
        "acquisition": "producer.collected",
    }
    session = trace.get("session")
    if not session:
        raise ValueError("legacy session identity required")
    clock = "legacy-" + session
    rows = []

    def add(kind, data, source=None, **kwargs):
        row = event(
            kind,
            data,
            clock_id=clock,
            run_id=run_id,
            stream_id=clock,
            seq=len(rows) + 1,
            **kwargs,
        )
        if source is not None:
            row.update(pid=source["pid"], tid=source["tid"])
        rows.append(validate(row))

    for row in trace["events"]:
        if row["event"] in mapping:
            add(
                "boundary",
                {"name": mapping[row["event"]]},
                mono_ns=row["ns"],
                op_id=row.get("op"),
                span_id=str(row["span"]) if "span" in row else None,
                source=row,
            )
    for name in (
        "producer.returned",
        "producer.validated",
        "producer.published",
        "repo.wait",
        "repo.hold",
        "observer.wire_send",
        "plot.input",
        "paint",
    ):
        add(
            "coverage",
            {
                "boundary": name,
                "available": False,
                "reason": "legacy trace lacks unambiguous dedicated boundary/ID; never reconstructed",
            },
            mono_ns=0,
        )
    add(
        "summary",
        {
            "dropped_events": trace["dropped"],
            "dropped_bodies": 0,
            "written_bytes": None,
            "write_wall_ns": None,
            "reason": "legacy-import; write timing unavailable",
        },
        mono_ns=0,
    )
    return rows
