"""Process-isolated deadlines with explicit worker termination and reaping."""

import multiprocessing
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


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


def run_bounded(fn: Callable[..., T], args: tuple, seconds: float) -> T:
    """Run a picklable function in an owned spawn worker, reap on every path."""
    if seconds <= 0:
        raise ValueError("Deadline must be positive")
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
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PlanningDeadlineError(
                    "Planning computation exceeded its deadline"
                )
            if reader.poll(min(remaining, 0.05)):
                try:
                    success, result = reader.recv()
                except EOFError as exc:
                    raise PlanningWorkerError(
                        "Planning worker exited without a result"
                    ) from exc
                if success:
                    return result
                raise result
            if not process.is_alive():
                raise PlanningWorkerError("Planning worker exited without a result")
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
