import multiprocessing
import os
import time
from types import SimpleNamespace

import pytest

from app.mission.planning import deadlines
from app.mission.planning.deadlines import (
    PlanningDeadlineError,
    PlanningWorkerError,
    run_bounded,
)


def _slow():
    time.sleep(30)


def _value(value):
    return value


def _failed():
    raise ValueError("sanitized failure")


def test_success_and_failure_reap_workers():
    before = {p.pid for p in multiprocessing.active_children()}
    assert run_bounded(_value, ("ok",), 3) == "ok"
    with pytest.raises(ValueError, match="sanitized"):
        run_bounded(_failed, (), 3)
    assert {p.pid for p in multiprocessing.active_children()} == before


def test_timeout_kills_and_reaps_worker():
    before = {p.pid for p in multiprocessing.active_children()}
    start = time.monotonic()
    with pytest.raises(PlanningDeadlineError) as e:
        run_bounded(_slow, (), 0.2)
    assert e.value.code == "planning_deadline_exceeded" and e.value.retryable
    assert time.monotonic() - start < 3
    assert {p.pid for p in multiprocessing.active_children()} == before


def _crashed():
    import os

    os._exit(7)


def _slow_started(path):
    from pathlib import Path

    Path(path).write_text("started")
    time.sleep(30)


def test_crashed_worker_is_typed_and_reaped():
    from app.mission.planning.deadlines import PlanningWorkerError

    before = {p.pid for p in multiprocessing.active_children()}
    with pytest.raises(PlanningWorkerError):
        run_bounded(_crashed, (), 3)
    assert {p.pid for p in multiprocessing.active_children()} == before


def test_started_worker_is_killed(tmp_path):
    marker = tmp_path / "started"
    before = {p.pid for p in multiprocessing.active_children()}
    with pytest.raises(PlanningDeadlineError):
        run_bounded(_slow_started, (str(marker),), 1)
    assert marker.exists()
    assert {p.pid for p in multiprocessing.active_children()} == before


def _released_outcome(release, outcome):
    assert release.wait(5), "Parent did not release the owned worker"
    if outcome == "error":
        raise ValueError("released failure")
    if outcome in ("crash", "empty"):
        os._exit(17 if outcome == "crash" else 0)
    return "completed-value"


class _ExitBetweenPollAndAlive:
    """Schedule a real worker's send/exit after a real false pipe poll."""

    def __init__(self):
        self.context = multiprocessing.get_context("spawn")
        self.release = self.context.Event()
        self.process = None
        self.first_poll = True
        self.exitcode = None

    def Pipe(self, *, duplex):
        self.reader, writer = self.context.Pipe(duplex=duplex)
        return self, writer

    def Process(self, **kwargs):
        self.process = self.context.Process(**kwargs)
        return self.process

    def poll(self, timeout=0):
        ready = self.reader.poll(timeout)
        if self.first_poll:
            self.first_poll = False
            assert not ready, "Worker must wait until after the false poll"
            self.release.set()
            self.process.join(timeout=3)
            assert not self.process.is_alive(), "Owned worker did not exit"
            self.exitcode = self.process.exitcode
            assert self.reader.poll(0), "Exited worker must expose payload or EOF"
        return ready

    def recv(self):
        assert self.reader.poll(0), "Never read a pipe without payload or EOF"
        return self.reader.recv()

    def close(self):
        self.reader.close()


@pytest.mark.parametrize("outcome", ["success", "error", "crash", "empty"])
def test_result_or_eof_after_false_poll_and_worker_exit(monkeypatch, outcome):
    before = {p.pid for p in multiprocessing.active_children()}
    context = _ExitBetweenPollAndAlive()
    monkeypatch.setattr(
        deadlines,
        "multiprocessing",
        SimpleNamespace(get_context=lambda method: context),
    )
    try:
        if outcome == "success":
            assert (
                run_bounded(_released_outcome, (context.release, outcome), 5)
                == "completed-value"
            )
        elif outcome == "error":
            with pytest.raises(ValueError, match="released failure"):
                run_bounded(_released_outcome, (context.release, outcome), 5)
        else:
            with pytest.raises(PlanningWorkerError, match="exited without a result"):
                run_bounded(_released_outcome, (context.release, outcome), 5)
        assert context.exitcode == (17 if outcome == "crash" else 0)
    finally:
        assert {p.pid for p in multiprocessing.active_children()} == before
        assert not deadlines._workers
