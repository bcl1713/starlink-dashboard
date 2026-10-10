import multiprocessing
import time

import pytest
from app.mission.planning.deadlines import PlanningDeadlineError, run_bounded


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
