"""Opt-in in-memory timing only. No production imports or persistent worker."""

import contextvars
import functools
import hashlib
import json
import os
import threading
import time
from contextlib import contextmanager

operation = contextvars.ContextVar("diagnostic_operation", default="unowned")
ALLOWED = frozenset(
    {
        "span",
        "parent",
        "outcome",
        "wall_ns",
        "cpu_ns",
        "scheduled_ns",
        "delay_ns",
        "owner",
        "depth",
        "acquired",
        "identity",
        "status",
        "count",
        "schedstat",
        "pressure",
        "cpu_stat",
        "load",
        "host_cpu",
        "available",
        "input",
        "route",
        "replay",
        "config",
        "result",
        "boundary",
        "duration_ns",
    }
)


def token(value):
    return hashlib.sha256(str(value).encode()).hexdigest()[:16]


def model_token(value):
    dump = getattr(value, "model_dump_json", None)
    return token(
        dump() if dump else (type(value).__name__, getattr(value, "mode", None))
    )


class Trace:
    def __init__(self, enabled=True, limit=200000):
        self.enabled, self.limit = enabled, limit
        self.rows, self.dropped, self.restores = [], 0, []
        self.lock = threading.Lock()
        self.sequence = 0
        self.pid = os.getpid()
        self.session = token(f"{self.pid}:{time.monotonic_ns()}")

    def event(self, event, **fields):
        if not self.enabled:
            return
        if fields.keys() - ALLOWED:
            raise ValueError("Diagnostic metadata is not allowlisted")
        row = dict(
            event=event,
            ns=time.monotonic_ns(),
            pid=self.pid,
            tid=threading.get_native_id(),
            op=operation.get(),
            **fields,
        )
        with self.lock:
            if len(self.rows) < self.limit:
                self.rows.append(row)
            else:
                self.dropped += 1

    @contextmanager
    def span(self, name, **fields):
        if not self.enabled:
            yield
            return
        with self.lock:
            self.sequence += 1
            ident = self.sequence
        began, cpu = time.monotonic_ns(), time.thread_time_ns()
        self.event(name + ".start", span=ident, **fields)
        outcome = "ok"
        try:
            yield
        except BaseException as exc:
            outcome = type(exc).__name__
            raise
        finally:
            self.event(
                name + ".end",
                span=ident,
                outcome=outcome,
                wall_ns=time.monotonic_ns() - began,
                cpu_ns=time.thread_time_ns() - cpu,
            )

    def wrap(self, target, attribute, boundary, before=None, after=None):
        original = getattr(target, attribute)

        @functools.wraps(original)
        def wrapped(*args, **kwargs):
            with self.span(boundary):
                if before:
                    before()
                result = original(*args, **kwargs)
                if after:
                    try:
                        after(result)
                    except Exception as exc:  # noqa: BLE001
                        self.event("metadata.unavailable", outcome=type(exc).__name__)
                return result

        setattr(target, attribute, wrapped)
        self.restores.append((target, attribute, original))
        return wrapped

    def close(self):
        for target, attribute, original in reversed(self.restores):
            setattr(target, attribute, original)
        self.restores.clear()

    def flush(self, path):
        with self.lock:
            result = {
                "session": self.session,
                "clock": "process-local monotonic_ns",
                "dropped": self.dropped,
                "events": list(self.rows),
            }
        pending = path.with_suffix(".pending")
        pending.write_text(json.dumps(result, separators=(",", ":")))
        pending.replace(path)
