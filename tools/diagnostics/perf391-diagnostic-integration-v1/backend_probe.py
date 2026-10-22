"""Bounded in-memory hooks for diagnostic derivatives only (CPython 3.11).

No sink callbacks, files, schema walks, model serialization or new application
locks on the hot path. Drain/validation/export belongs to a later owner. Each
native thread has a distinct stream, sequence and start token, including TID
reuse. Captured mutex stamps are emitted after the existing critical section.
"""

import asyncio
import json
import math
import os
import threading
import time
import uuid
from collections import OrderedDict, deque
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from itertools import count
from pathlib import Path

_CONTRACT = json.loads(Path(__file__).with_name("contract.json").read_text())
_PHASES = frozenset(_CONTRACT["phases"])
_FIELDS = frozenset(_CONTRACT["identity_fields"])
_OUTCOMES = frozenset(_CONTRACT["outcomes"])
_TYPES = frozenset(
    (
        "tick",
        "replay",
        "derived_refresh",
        "scrape",
        "source_observer",
        "history",
        "presentation",
        "lifecycle",
    )
)
_A_PHASES = frozenset(
    (
        "producer.published",
        "producer.validated",
        "source.final.begin",
        "source.final.end",
        "publication.attempt",
        "publication.result",
        "publication.swap",
    )
)
_A_FIELDS = frozenset(
    (
        "expected_head",
        "publication_token",
        "frame_id",
        "cas_success",
        "publication_kind",
    )
)

_context = ContextVar("perf391_operation", default=None)
_collection = ContextVar("perf391_collection", default=None)
_publication_kind = ContextVar("perf391_publication_kind", default="ready")
_serial = count(1)
_local = threading.local()
_records = deque(maxlen=8192)
_free_record_slots = deque(range(8192))
_counts = {
    "dropped": 0,
    "invalid": 0,
    "failures": 0,
    "high_water": 0,
    "token_evictions": 0,
    "token_unavailable": 0,
}
_role, _run = "C", "unconfigured"
_process = str(uuid.uuid4())
_pid = os.getpid()
_process_start = str(time.monotonic_ns())
_generation = 0
_free_hold_slots = deque(range(256))
_tokens = OrderedDict()
_free_token_slots = deque(range(256))
_fault = False
_NOW = object()


def configure(role, run_id, *, capacity=8192):
    """Offline/owner setup, before starting workers; never changes application pools."""
    global _role, _run, _records, _counts, _generation, _free_hold_slots, _free_record_slots, _tokens, _free_token_slots
    if role not in ("A", "C") or not _ascii(run_id) or not 1 <= capacity <= 8192:
        raise ValueError("invalid probe configuration")
    _role, _run = role, run_id
    _records = deque(maxlen=capacity)
    _free_record_slots = deque(range(capacity))
    _counts = {
        "dropped": 0,
        "invalid": 0,
        "failures": 0,
        "high_water": 0,
        "token_evictions": 0,
        "token_unavailable": 0,
    }
    _generation += 1
    _free_hold_slots = deque(range(256))
    _tokens = OrderedDict()
    _free_token_slots = deque(range(256))


def _ascii(value):
    return (
        type(value) is str
        and 0 < len(value) <= 96
        and all(33 <= ord(c) <= 126 for c in value)
    )


def _thread():
    if getattr(_local, "generation", None) != _generation:
        _local.generation = _generation
        _local.start = "thread-" + str(next(_serial))
        _local.seq = 0
        _local.holds = {}
    return _local


def new_operation(kind="lifecycle"):
    try:
        return kind + "-" + str(next(_serial))
    except BaseException:
        return "unavailable"


def new_span():
    return new_operation("span")


def current_id():
    context = _context.get()
    return context[0] if context else "backend-local"


@contextmanager
def operation(op_id, operation_type="lifecycle"):
    previous = _context.get()
    token = _context.set(
        (
            op_id,
            operation_type,
            (
                (previous[2] if previous[0] == op_id else previous[0])
                if previous
                else None
            ),
        )
    )
    try:
        yield
    finally:
        _context.reset(token)


@contextmanager
def publication_kind(kind):
    token = _publication_kind.set(kind)
    try:
        yield
    finally:
        _publication_kind.reset(token)


@contextmanager
def faults():
    """Explicit offline sink-fault injection; no external sink runs on a hot path."""
    global _fault
    previous, _fault = _fault, True
    try:
        yield
    finally:
        _fault = previous


def stamp():
    try:
        return time.monotonic_ns(), time.thread_time_ns()
    except BaseException:
        _counts["failures"] += 1
        return None


def token(value):
    """One bounded process-wide identity map, using CPython atomic operations.

    Strong references prevent address reuse while cached. Atomic permit pop,
    popitem and setdefault canonicalize concurrent lookups without a new lock.
    Eviction deliberately ends that token's availability; reinsertion is fresh.
    """
    reserved = None
    try:
        if value is None:
            return None
        key = id(value)
        entry = _tokens.get(key)
        if entry is not None and entry[0] is value:
            return entry[1]
        try:
            reserved = _free_token_slots.pop()
        except IndexError:
            try:
                _, evicted = _tokens.popitem(last=False)
            except KeyError:
                # All permits can temporarily be owned by in-flight insertions.
                _counts["token_unavailable"] += 1
                return None
            _counts["token_evictions"] += 1
            reserved = evicted[2]
        candidate = (value, "object-" + str(next(_serial)), reserved)
        entry = _tokens.setdefault(key, candidate)
        if entry is not candidate:
            _free_token_slots.append(reserved)
        reserved = None
        return entry[1]
    except BaseException:
        if reserved is not None:
            _free_token_slots.append(reserved)
        _counts["failures"] += 1
        return None


def frame_identity(frame):
    """Only already exposed immutable scalar fields; never serialize a model."""
    try:
        identity = frame.identity
        return {
            "frame_id": token(frame),
            "source_mode": identity.mode,
            "source_lifecycle": identity.coordinator_id,
            "observation_id": identity.observation_id,
            "observation_timestamp": identity.observation_timestamp,
            "route_revision": identity.route_id,
            "input_revision": identity.input_revision,
            "replay_runtime": identity.replay_runtime_id,
            "replay_run": identity.replay_run_id,
            "replay_revision": identity.replay_revision,
            "replay_mission_time": identity.replay_mission_time,
        }
    except BaseException:
        return {}


def telemetry_identity(value):
    try:
        result = {"object_token": token(value)}
        timestamp = getattr(value, "timestamp", None)
        if timestamp is not None:
            result["observation_timestamp"] = timestamp.timestamp()
        return result
    except BaseException:
        return {}


def outcome(error):
    return "cancelled" if isinstance(error, asyncio.CancelledError) else "error"


def mark(phase, *, op_id=None, span_id=None, outcome="ok", identity=None, at=_NOW):
    """Nonthrowing bounded emission. No diagnostic exception crosses this function."""
    try:
        if _fault:
            raise OSError("offline injected sink failure")
        context = _context.get()
        op_id = op_id or (context[0] if context else "backend-local")
        if phase not in _PHASES or outcome not in _OUTCOMES or not _ascii(op_id):
            _counts["invalid"] += 1
            return
        if context and (
            context[1] not in _TYPES
            or (context[2] is not None and not _ascii(context[2]))
        ):
            _counts["invalid"] += 1
            return
        if _role == "A" and phase in _A_PHASES:
            _counts["invalid"] += 1
            return
        if span_id is not None and not _ascii(span_id):
            _counts["invalid"] += 1
            return
        if identity is not None and (
            type(identity) is not dict or len(identity) > len(_FIELDS)
        ):
            _counts["invalid"] += 1
            return
        fields, unavailable = {}, {}
        for key, value in (identity or {}).items():
            if key not in _FIELDS:
                _counts["invalid"] += 1
                return
            if value is None or (type(value) is float and not math.isfinite(value)):
                fields[key], unavailable[key] = None, "not exposed or nonfinite"
            elif key == "cas_success" and type(value) is bool:
                fields[key] = value
            elif (
                key != "cas_success"
                and type(value) in (int, float)
                and (type(value) is not int or value.bit_length() <= 256)
            ):
                fields[key] = str(value)
            elif key != "cas_success" and type(value) is str and 0 < len(value) <= 256:
                fields[key] = value
            else:
                _counts["invalid"] += 1
                return
        if _role == "A" and any(key in _A_FIELDS for key in fields):
            _counts["invalid"] += 1
            return
        captured = stamp() if at is _NOW else at
        if captured is None:
            _counts["failures"] += 1
            return
        local = _thread()
        local.seq += 1
        record = {
            "schema": "perf391-diagnostic-integration-v1",
            "version": 1,
            "role": _role,
            "emitter": "backend",
            "run_id": _run,
            "stream_id": _process + "-" + local.start,
            "seq": local.seq,
            "process_uuid": _process,
            "pid": _pid,
            "tid": threading.get_native_id(),
            "process_start_id": _process_start,
            "thread_start_id": local.start,
            "clock_id": _process + "-monotonic",
            "mono_ns": str(captured[0]),
            "thread_cpu_ns": str(captured[1]),
            "op_id": op_id,
            "parent_op_id": context[2] if context else None,
            "span_id": span_id,
            "operation_type": context[1] if context else "lifecycle",
            "phase": phase,
            "outcome": outcome,
            "identity": fields,
            "unavailable": unavailable,
        }
        # Atomic deque-pop reservation on the pinned CPython runtime. A len /
        # append check can race across workers and silently evict an old record.
        try:
            slot = _free_record_slots.pop()
        except IndexError:
            _counts["dropped"] += 1
            return
        try:
            _records.append(record)
        except BaseException:
            _free_record_slots.append(slot)
            raise
        _counts["high_water"] = max(_counts["high_water"], len(_records))
    except BaseException:
        _counts["failures"] += 1


def drain():
    """Owner-only after worker drain; no application hook calls this."""
    result = list(_records)
    _counts["high_water"] = max(_counts["high_water"], len(result))
    _records.clear()
    _free_record_slots.extend(range(len(result)))
    return result


def stats():
    return {**_counts, "buffered": len(_records), "capacity": _records.maxlen}


def bracket(begin, end, *, telemetry=False, kind=None):
    def decorate(fn):
        @wraps(fn)
        def invoke(*args, **kwargs):
            mark(begin)
            try:
                result = fn(*args, **kwargs)
            except BaseException as error:
                mark(end, outcome=outcome(error))
                raise
            mark(end, identity=telemetry_identity(result) if telemetry else None)
            return result

        return invoke

    return decorate


def publication(result, frame, *, kind=None, expected=None, published_state=None):
    try:
        if _role != "C":
            return
        kind = kind or _publication_kind.get()
        identity = frame_identity(frame)
        identity.update(
            publication_kind=kind,
            cas_success=result,
            expected_head=token(expected),
            publication_token=token(published_state) if result else None,
        )
        mark(
            "publication.result",
            outcome="ok" if result else "cas_lost",
            identity=identity,
        )
        context = _context.get()
        if (
            _role == "C"
            and result
            and kind == "ready"
            and context
            and context[1] in ("tick", "replay")
        ):
            mark("producer.published", identity=identity)
    except BaseException:
        _counts["failures"] += 1


def repository_granted(gate, span, entered, granted):
    try:
        holds = _thread().holds
        try:
            slot = _free_hold_slots.pop()
        except IndexError:
            _counts["dropped"] += 1
            return
        holds[id(gate)] = (span, current_id(), slot)
        mark("repo.wait", span_id=span, at=entered)
        mark("repo.local_grant", span_id=span, at=granted)
    except BaseException:
        _counts["failures"] += 1


def repository_acquired(gate):
    try:
        span, op, _slot = _thread().holds[id(gate)]
        mark("repo.acquired", op_id=op, span_id=span)
    except BaseException:
        _counts["failures"] += 1


def repository_failed(gate, span, entered, *, local=False):
    try:
        if local:
            mark("repo.wait", span_id=span, at=entered)
        else:
            previous = _thread().holds.pop(id(gate), None)
            if previous is not None:
                _free_hold_slots.append(previous[2])
        mark("repo.acquire_failed", span_id=span, outcome="error")
    except BaseException:
        _counts["failures"] += 1


def repository_released(gate, entry, released):
    try:
        span, op, slot = _thread().holds.pop(id(gate))
        _free_hold_slots.append(slot)
        # release-entry is a separate same-span marker; swap the phase via the
        # closed sidecar addition rather than inventing hold time from return.
        mark("repo.release_enter", op_id=op, span_id=span, at=entry)
        if released is None:
            mark(
                "probe.failure",
                op_id=op,
                span_id=span,
                outcome="unavailable",
                identity={"branch": "repo_release_timestamp"},
            )
        else:
            mark("repo.released", op_id=op, span_id=span, at=released)
    except BaseException:
        mark("probe.failure", outcome="unavailable")


@contextmanager
def validation(frame=None):
    """Bracket one existing predicate; caller branches on its original result."""
    mark("source.final.begin", identity=frame_identity(frame))
    result = [None]

    def completed(value):
        result[0] = value

    try:
        yield completed
    except BaseException as error:
        mark("source.final.end", outcome=outcome(error))
        raise
    else:
        mark(
            "source.final.end",
            outcome=(
                "ok"
                if result[0] is True
                else "rejected" if result[0] is False else "unavailable"
            ),
            identity=frame_identity(frame),
        )
        context = _context.get()
        if (
            result[0] is True
            and _role == "C"
            and context
            and context[1] in ("tick", "replay")
        ):
            mark("producer.validated", identity=frame_identity(frame))


def _collected_identity(value, previous):
    identity = telemetry_identity(value)
    identity["retained_token"] = (
        token(previous) if previous is not None and value is previous else None
    )
    return identity


def _collect_call(fn, args, kwargs, previous=None):
    state = [None]
    handle = _collection.set(state)
    mark("collection.enter")
    try:
        try:
            value = fn(*args, **kwargs)
        except BaseException as error:
            mark("collection.return", outcome=outcome(error))
            raise
        identity = (
            state[0] if state[0] is not None else _collected_identity(value, previous)
        )
        mark("collection.return", identity=identity)
        context = _context.get()
        if context and context[1] == "replay":
            # The replay outer collect returns after commit/publication; only
            # this inner coordinator return is an acquisition completion.
            mark("producer.collected", identity=identity)
        return value
    finally:
        _collection.reset(handle)


def collect_update(fn, *args, **kwargs):
    """The existing main coordinator call, including live implementations.

    A nested SimulationCoordinator decorator supplies retained metadata into this
    same bracket, avoiding a second collection pair or second invocation.
    """
    return _collect_call(fn, args, kwargs)


def source_collection(fn):
    @wraps(fn)
    def invoke(*args, **kwargs):
        # Existing coordinator field, no getter/manager/source check.
        try:
            previous = getattr(args[0], "_last_valid_telemetry", None)
        except BaseException:
            previous = None
        state = _collection.get()
        if state is None:
            return _collect_call(fn, args, kwargs, previous)
        value = fn(*args, **kwargs)
        state[0] = _collected_identity(value, previous)
        return value

    return invoke


def replay_collect(fn):
    @wraps(fn)
    def invoke(*args, **kwargs):
        with operation(current_id(), "replay"):
            try:
                value = fn(*args, **kwargs)
            except BaseException as error:
                mark("replay.return", outcome=outcome(error))
                raise
            mark("replay.return", identity=telemetry_identity(value))
            return value

    return invoke


def commit(fn, tick):
    try:
        value = fn(tick)
    except BaseException as error:
        mark("replay.commit", outcome=outcome(error))
        raise
    mark("replay.commit", identity=replay_identity(tick))
    return value


def replay_identity(tick):
    try:
        status = tick.status
        run = status.run
        return {
            "replay_runtime": status.runtime_id,
            "replay_run": run.run_id if run else None,
            "replay_revision": str(status.revision),
            "replay_mission_time": run.simulation_time.timestamp() if run else None,
        }
    except BaseException:
        return {}


def publication_scope(kind):
    def decorate(fn):
        @wraps(fn)
        def invoke(*args, **kwargs):
            with publication_kind(kind):
                return fn(*args, **kwargs)

        return invoke

    return decorate


def async_bracket(begin, end):
    def decorate(fn):
        @wraps(fn)
        async def invoke(*args, **kwargs):
            mark(begin)
            try:
                value = await fn(*args, **kwargs)
            except BaseException as error:
                mark(end, outcome=outcome(error))
                raise
            mark(end)
            return value

        return invoke

    return decorate


def branch(name):
    mark("producer.branch", identity={"branch": name})


def publication_attempt(fn):
    @wraps(fn)
    def invoke(self, expected, frame):
        mark(
            "publication.attempt",
            identity={
                **frame_identity(frame),
                "expected_head": token(expected),
                "publication_kind": _publication_kind.get(),
            },
        )
        try:
            return fn(self, expected, frame)
        except BaseException as error:
            mark(
                "publication.result",
                outcome=outcome(error),
                identity={
                    "expected_head": token(expected),
                    "publication_kind": _publication_kind.get(),
                },
            )
            raise

    return invoke


def swap_kind(status):
    return {"pending": "invalidate", "failed": "fail"}.get(
        status, _publication_kind.get()
    )


def refresh(fn):
    @wraps(fn)
    def invoke(*args, **kwargs):
        context = _context.get()
        if context and context[1] == "derived_refresh":
            with publication_kind("derived_refresh"):
                return fn(*args, **kwargs)
        with operation(new_operation("refresh"), "derived_refresh"), publication_kind(
            "derived_refresh"
        ):
            return bracket("refresh.start", "refresh.end")(fn)(*args, **kwargs)

    return invoke


def producer_mark(phase, op_id, *, outcome="ok"):
    with operation(op_id, "tick"):
        mark(phase, outcome=outcome)


def operation_type(default="lifecycle"):
    context = _context.get()
    return context[1] if context else default
