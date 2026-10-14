"""Process-isolated deadlines with explicit worker termination and reaping."""

import multiprocessing
import threading
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")
_registry_lock = threading.Lock()
_workers = {}
_shutting_down = False


def start_workers():
    global _shutting_down
    with _registry_lock:
        _shutting_down = False


def shutdown_workers():
    """Signal owned runners; each runner alone terminates and reaps its child."""
    global _shutting_down
    with _registry_lock:
        _shutting_down = True
        entries = list(_workers.items())
        for cancel, _ in entries:
            cancel.set()
    for _, done in entries:
        done.wait()


class PlanningDeadlineError(RuntimeError):
    code = "planning_deadline_exceeded"
    retryable = True


class PlanningWorkerError(RuntimeError):
    code = "planning_worker_failed"
    retryable = True


def _worker(connection, fn, args):
    try:
        connection.send((True, fn(*args)))
    except Exception as exc:  # noqa: BLE001 - worker boundary transports caller errors
        connection.send((False, exc))
    finally:
        connection.close()


def run_bounded(
    fn: Callable[..., T], args: tuple, seconds: float, *, cancel_event=None
) -> T:
    """Run a picklable function in an owned spawn worker, reap on every path."""
    if seconds <= 0:
        raise ValueError("Deadline must be positive")
    cancel = threading.Event()
    done = threading.Event()
    with _registry_lock:
        if _shutting_down:
            raise PlanningWorkerError("Planning computation cancelled for shutdown")
        _workers[cancel] = done
    context = multiprocessing.get_context("spawn")
    reader, writer = context.Pipe(duplex=False)
    process = context.Process(
        target=_worker, args=(writer, fn, args), name="planning-bounded-worker"
    )
    started = False
    deadline = time.monotonic() + seconds
    try:
        process.start()
        started = True
        writer.close()
        while True:
            if cancel.is_set() or cancel_event is not None and cancel_event.is_set():
                raise PlanningWorkerError("Planning computation cancelled")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PlanningDeadlineError(
                    "Planning computation exceeded its deadline"
                )
            if not reader.poll(min(remaining, 0.05)):
                if process.is_alive():
                    continue
                # A worker can send and exit between the poll and liveness check.
                if not reader.poll():
                    raise PlanningWorkerError("Planning worker exited without a result")
            try:
                success, result = reader.recv()
            except EOFError as exc:
                raise PlanningWorkerError(
                    "Planning worker exited without a result"
                ) from exc
            if success:
                return result
            raise result
    finally:
        reader.close()
        writer.close()
        if started:
            process.join(timeout=0.2)
            if process.is_alive():
                process.terminate()
                process.join(timeout=0.5)
            if process.is_alive():
                process.kill()
                process.join()
            process.close()
        with _registry_lock:
            _workers.pop(cancel, None)
            done.set()
