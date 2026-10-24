"""Immutable coupled gauges using only public Prometheus collector APIs.

Not registered by importing this module. Producers stage complete frames, then
publish with an expected head after their own authoritative source admission.
Independent instruments are deliberately outside this consistency domain.
"""

from asyncio import current_task
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Lock, get_ident
from typing import Literal

from prometheus_client.core import GaugeMetricFamily


@dataclass(frozen=True, slots=True)
class GaugeDefinition:
    name: str
    documentation: str
    labelnames: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "documentation", str(self.documentation))
        labels = tuple(str(label) for label in self.labelnames)
        if len(set(labels)) != len(labels):
            raise ValueError("Duplicate label names")
        object.__setattr__(self, "labelnames", labels)


@dataclass(frozen=True, slots=True)
class FrameIdentity:
    mode: str = "unknown"
    coordinator_id: str | None = None
    observation_id: str | None = None
    observation_timestamp: float | None = None
    route_id: str | None = None
    poi_id: str | None = None
    phase_id: str | None = None
    input_revision: int = 0
    replay_runtime_id: str | None = None
    replay_run_id: str | None = None
    replay_revision: str | None = None
    replay_mission_time: float | None = None

    def __post_init__(self):
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if name == "input_revision":
                if type(value) is not int or value < 0:
                    raise ValueError("Input revision must be a nonnegative integer")
            elif value is not None:
                scalar = (
                    float
                    if name in ("observation_timestamp", "replay_mission_time")
                    else str
                )
                object.__setattr__(self, name, scalar(value))


# Each family is ordered samples of (normalized label tuple, float).
@dataclass(frozen=True, slots=True, weakref_slot=True)
class GaugeFrame:
    identity: FrameIdentity
    families: tuple[tuple[tuple[tuple[str, ...], float], ...], ...]
    last_observation_publication_time: float

    def __post_init__(self):
        if type(self.identity) is not FrameIdentity:
            raise TypeError("Frame identity must be immutable")
        object.__setattr__(
            self,
            "families",
            tuple(
                tuple(
                    (tuple(str(label) for label in labels), float(value))
                    for labels, value in family
                )
                for family in self.families
            ),
        )
        object.__setattr__(
            self,
            "last_observation_publication_time",
            float(self.last_observation_publication_time),
        )


@dataclass(frozen=True, slots=True)
class PublicationState:
    frame: GaugeFrame | None
    status: Literal["uninitialized", "ready", "pending", "failed"]
    reason: str | None = None
    input_revision: int = 0


class FrameStore:
    """One head; no history, numeric shadow, source callback or retrying readers."""

    def __init__(self, schema):
        self.schema = tuple(schema)
        if len({definition.name for definition in self.schema}) != len(self.schema):
            raise ValueError("Duplicate gauge family")
        self._lock = Lock()
        self._head = PublicationState(None, "uninitialized")

    def read(self) -> PublicationState:
        with self._lock:
            return self._head

    def publish(self, expected: PublicationState, frame: GaugeFrame) -> bool:
        # All traversal/conversion and allocation precedes the pointer mutex.
        self._validate(frame)
        if frame.identity.input_revision != expected.input_revision:
            raise ValueError("Frame does not match expected input revision")
        state = PublicationState(frame, "ready", input_revision=expected.input_revision)
        return self._swap(expected, state)

    def _swap(self, expected, state):
        with self._lock:
            if self._head is not expected:
                return False
            self._head = state
            return True

    def invalidate(self, reason: str) -> PublicationState:
        reason = str(reason)
        while True:
            expected = self.read()
            state = PublicationState(
                expected.frame, "pending", reason, expected.input_revision + 1
            )
            if self._swap(expected, state):
                return state

    def fail(self, expected: PublicationState, reason: str) -> bool:
        state = PublicationState(
            expected.frame, "failed", str(reason), expected.input_revision
        )
        return self._swap(expected, state)

    def prepare(self, identity, last_observation_publication_time):
        return _Preparation(self, identity, last_observation_publication_time)

    def _validate(self, frame):
        if type(frame) is not GaugeFrame or len(frame.families) != len(self.schema):
            raise ValueError("Frame must contain the complete schema")
        for definition, samples in zip(self.schema, frame.families):
            seen = set()
            for labels, _ in samples:
                if len(labels) != len(definition.labelnames) or labels in seen:
                    raise ValueError("Incorrect or duplicate sample labels")
                seen.add(labels)
            if not definition.labelnames and len(samples) != 1:
                raise ValueError("Unlabelled family requires exactly one sample")


_preparation: ContextVar = ContextVar("metric_frame_preparation", default=None)


class _Preparation:
    """Single synchronous producer scope; temporary numeric state only."""

    def __init__(self, store, identity, timestamp):
        self.store, self.identity, self.timestamp = store, identity, timestamp
        self._samples = {definition: {} for definition in store.schema}
        self._active = False
        self._sealed = False

    def __enter__(self):
        if _preparation.get() is not None or self._active or self._sealed:
            raise RuntimeError("Preparation scopes cannot nest or be reused")
        self._owner = self._producer()
        self._active = True
        self._token = _preparation.set(self)
        return self

    def __exit__(self, *exc):
        _preparation.reset(self._token)
        self._active = False
        self._sealed = True
        self._samples.clear()
        self._owner = None

    @staticmethod
    def _producer():
        try:
            task = current_task()
        except RuntimeError:  # synchronous worker, no event loop
            task = None
        return get_ident(), task

    def _check_owner(self):
        if not self._active or self._sealed or self._producer() != self._owner:
            raise RuntimeError("No active preparation for this producer")

    def set(self, definition, labels, value):
        self._check_owner()
        if definition not in self._samples:
            raise ValueError("Gauge does not belong to preparation schema")
        labels = tuple(str(label) for label in labels)
        if len(labels) != len(definition.labelnames):
            raise ValueError("Incorrect label count")
        self._samples[definition][labels] = float(value)

    def seal(self) -> GaugeFrame:
        self._check_owner()
        frame = GaugeFrame(
            self.identity,
            tuple(
                tuple(self._samples[definition].items())
                for definition in self.store.schema
            ),
            self.timestamp,
        )
        self.store._validate(frame)
        self._sealed = True
        return frame


_POSITION = (
    ("latitude", "starlink_dish_latitude_degrees"),
    ("longitude", "starlink_dish_longitude_degrees"),
    ("altitude", "starlink_dish_altitude_feet"),
)
_POSITION_HELP = "Current aircraft position with latitude, longitude, and altitude"
_TIMESTAMP = "starlink_metrics_last_update_timestamp_seconds"


def _family(state, definition, index):
    metric = GaugeMetricFamily(
        definition.name, definition.documentation, labels=definition.labelnames
    )
    samples = (
        state.frame.families[index]
        if state.frame
        else (() if definition.labelnames else (((), float("nan")),))
    )
    for labels, value in samples:
        if state.status != "ready" and definition.name != _TIMESTAMP:
            value = float("nan")
        metric.add_metric(labels, value)
    return metric


class TelemetryFrameCollector:
    def __init__(self, store: FrameStore, schema):
        self.store, self.schema = store, tuple(schema)
        if self.schema != store.schema:
            raise ValueError("Collector schema differs from store")
        indices = {definition.name: i for i, definition in enumerate(self.schema)}
        self._position = tuple(
            (dimension, indices[name])
            for dimension, name in _POSITION
            if name in indices
        )

    def describe(self):
        for definition in self.schema:
            yield GaugeMetricFamily(
                definition.name, definition.documentation, labels=definition.labelnames
            )
        if len(self._position) == 3:
            yield GaugeMetricFamily(
                "starlink_aircraft_position", _POSITION_HELP, labels=["dimension"]
            )

    def collect(self):
        state = self.store.read()  # retained once until the iterator is exhausted
        for index, definition in enumerate(self.schema):
            yield _family(state, definition, index)
        if len(self._position) == 3:
            metric = GaugeMetricFamily(
                "starlink_aircraft_position", _POSITION_HELP, labels=["dimension"]
            )
            for dimension, index in self._position:
                value = (
                    state.frame.families[index][0][1]
                    if state.frame and state.status == "ready"
                    else float("nan")
                )
                metric.add_metric([dimension], value)
            yield metric


@dataclass(frozen=True, slots=True)
class FrameGaugeView:
    store: FrameStore
    definition: GaugeDefinition
    labelvalues: tuple[str, ...] = ()

    def __post_init__(self):
        if self.definition not in self.store.schema:
            raise ValueError("Unknown gauge definition")
        object.__setattr__(self, "labelvalues", tuple(str(v) for v in self.labelvalues))
        if self.labelvalues and len(self.labelvalues) != len(
            self.definition.labelnames
        ):
            raise ValueError("Incorrect label count")

    def labels(self, *args, **kwargs):
        if self.labelvalues or (args and kwargs) or not self.definition.labelnames:
            raise ValueError("Invalid label binding")
        if kwargs:
            if set(kwargs) != set(self.definition.labelnames):
                raise ValueError("Incorrect label names")
            args = tuple(kwargs[name] for name in self.definition.labelnames)
        if len(args) != len(self.definition.labelnames):
            raise ValueError("Incorrect label count")
        return FrameGaugeView(self.store, self.definition, args)

    def set(self, value):
        builder = _preparation.get()
        if builder is None or builder.store is not self.store:
            raise RuntimeError("Coupled gauge writes require producer preparation")
        builder.set(self.definition, self.labelvalues, value)

    def collect(self):
        index = self.store.schema.index(self.definition)
        yield _family(self.store.read(), self.definition, index)
