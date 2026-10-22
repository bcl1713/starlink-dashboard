"""Bounded queue plus bounded owned disk; explicit loss and synchronous drain."""

import hashlib
import json
import threading
import time
import uuid
from collections import deque
from pathlib import Path

from .model import CLOCK, event, validate


class Recorder:
    RESERVE = 4096

    def __init__(
        self,
        root,
        *,
        run_id="offline",
        stream_id=None,
        max_events=4096,
        max_bytes=8 * 1024**2,
        max_event_bytes=1024**2,
        max_disk_bytes=256 * 1024**2,
        max_body_bytes=2 * 1024**2,
    ):
        if (
            min(max_events, max_bytes, max_event_bytes, max_body_bytes) <= 0
            or max_disk_bytes <= self.RESERVE
        ):
            raise ValueError("positive limits and summary reserve required")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.file = (self.root / "events.jsonl").open("xb")
        self.run_id, self.stream_id = run_id, stream_id or uuid.uuid4().hex
        self.max_events, self.max_bytes, self.max_event_bytes = (
            max_events,
            max_bytes,
            max_event_bytes,
        )
        self.max_disk_bytes, self.max_body_bytes = max_disk_bytes, max_body_bytes
        self.pending, self.pending_bytes, self.disk_bytes = deque(), 0, 0
        self.seq = self.dropped_events = self.dropped_bodies = self.write_wall_ns = 0
        self.closed, self.lock = False, threading.RLock()

    def emit(
        self, kind, data, *, mono_ns=None, op_id=None, span_id=None, clock_id=CLOCK
    ):
        with self.lock:
            if self.closed:
                raise RuntimeError("closed recorder")
            self.seq += 1
            row = event(
                kind,
                data,
                mono_ns=mono_ns,
                clock_id=clock_id,
                run_id=self.run_id,
                stream_id=self.stream_id,
                seq=self.seq,
                op_id=op_id,
                span_id=span_id,
                thread_cpu_ns=time.thread_time_ns(),
            )
            validate(row)
            raw = (
                json.dumps(row, allow_nan=False, separators=(",", ":")) + "\n"
            ).encode()
            if (
                len(self.pending) >= self.max_events
                or len(raw) > self.max_event_bytes
                or self.pending_bytes + len(raw) > self.max_bytes
                or self.disk_bytes + self.pending_bytes + len(raw)
                > self.max_disk_bytes - self.RESERVE
            ):
                self.dropped_events += 1
                return False
            self.pending.append(raw)
            self.pending_bytes += len(raw)
            return True

    def artifact(self, body):
        with self.lock:
            if self.closed:
                raise RuntimeError("closed recorder")
            digest = hashlib.sha256(body).hexdigest()
            path = Path("bodies") / (digest + ".bin")
            if (
                len(body) > self.max_body_bytes
                or self.disk_bytes + self.pending_bytes + len(body)
                > self.max_disk_bytes - self.RESERVE
            ):
                self.dropped_bodies += 1
                return {
                    "state": "unavailable",
                    "path": None,
                    "sha256": None,
                    "bytes": len(body),
                    "reason": "body_or_disk_limit",
                }
            destination = self.root / path
            destination.parent.mkdir(exist_ok=True)
            if not destination.exists():
                began = time.monotonic_ns()
                with destination.open("xb") as stream:
                    stream.write(body)
                self.write_wall_ns += time.monotonic_ns() - began
                self.disk_bytes += len(body)
            return {
                "state": "available",
                "path": str(path),
                "sha256": digest,
                "bytes": len(body),
                "reason": None,
            }

    def drain(self):
        with self.lock:
            began = time.monotonic_ns()
            while self.pending:
                raw = self.pending[0]
                self.file.write(raw)
                self.disk_bytes += len(raw)
                self.pending_bytes -= len(raw)
                self.pending.popleft()
            self.file.flush()
            self.write_wall_ns += time.monotonic_ns() - began

    def close(self, reason="closed"):
        with self.lock:
            if self.closed:
                return
            try:
                self.drain()
                self.seq += 1
                row = event(
                    "summary",
                    {
                        "dropped_events": self.dropped_events,
                        "dropped_bodies": self.dropped_bodies,
                        "written_bytes": self.disk_bytes,
                        "write_wall_ns": str(self.write_wall_ns),
                        "reason": reason[:128],
                    },
                    run_id=self.run_id,
                    stream_id=self.stream_id,
                    seq=self.seq,
                )
                validate(row)
                raw = (json.dumps(row, separators=(",", ":")) + "\n").encode()
                if len(raw) > self.RESERVE:
                    raise RuntimeError("summary reserve exceeded")
                self.file.write(raw)
            finally:
                self.file.close()
                self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        self.close("exception:" + kind.__name__ if kind else "closed")
