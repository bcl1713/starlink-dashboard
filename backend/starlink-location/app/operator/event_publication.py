"""Bounded pinned snapshots and leases over explicitly participating publishers."""

from collections import OrderedDict
from contextlib import contextmanager, nullcontext
from threading import RLock
from uuid import uuid4

from .errors import OperatorError


class EventPublication:
    """A local publication boundary; callers must prove every producer participates."""

    def __init__(self):
        self._lock = RLock()
        self._sources = {}
        self._validators = {}
        self.input_gate = nullcontext

    def publish(self, source, *, update=None, validate=None):
        with self.input_gate(), self._lock:
            if update is not None:
                # Input mutation and its replacement publication share the gate.
                # A failed update leaves the source invalid, never falsely current.
                self._sources.pop(source.source, None)
                update()
            self._sources[source.source] = source.model_copy(deep=True)
            if validate is not None:
                self._validators[source.source] = validate

    def invalidate(self, source):
        with self._lock:
            self._sources.pop(source, None)
            self._validators.pop(source, None)

    @contextmanager
    def guard(self, expected):
        with self.input_gate(), self._lock:
            for source in expected:
                if (
                    not source.guardable
                    or not source.aligned
                    or source.freshness != "fresh"
                ):
                    raise OperatorError("event_source_unavailable", retryable=True)
                validator = self._validators.get(source.source)
                if validator is not None:
                    validator()
                current = self._sources.get(source.source)
                if current is None:
                    raise OperatorError("event_source_unavailable", retryable=True)
                if current != source:
                    raise OperatorError("event_snapshot_changed", retryable=True)
            yield


class SnapshotRegistry:
    def __init__(self, *, clock, capacity=256):
        self.clock, self.capacity = clock, capacity
        self._snapshots = OrderedDict()
        self._lock = RLock()

    def issue(self, snapshot):
        token = str(uuid4())
        with self._lock:
            self._snapshots[token] = (
                self.clock.monotonic(),
                snapshot.model_copy(deep=True),
            )
            while len(self._snapshots) > self.capacity:
                self._snapshots.popitem(last=False)
        return token

    def resolve(self, token):
        with self._lock:
            entry = self._snapshots.get(token)
            age = self.clock.monotonic() - entry[0] if entry else -1
            if entry is None or age < 0 or age >= 120:
                self._snapshots.pop(token, None)
                raise OperatorError("event_snapshot_changed", retryable=True)
            return entry[1].model_copy(deep=True)

    def clear(self):
        with self._lock:
            self._snapshots.clear()
