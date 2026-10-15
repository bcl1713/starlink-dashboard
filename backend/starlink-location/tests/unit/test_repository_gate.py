"""Repository readers cannot be overtaken by repeated short local acquisitions."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from filelock import FileLock, Timeout

from app.mission import storage


def test_waiting_reader_precedes_a_barging_previous_owner(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    gate = storage.get_active_leg_lock()
    started = threading.Event()
    order = []

    def reader():
        started.set()
        with gate.acquire(timeout=2, poll_interval=0.25):
            order.append("reader")

    with ThreadPoolExecutor(max_workers=1) as workers:
        with gate:
            result = workers.submit(reader)
            assert started.wait(1)
            # The reader has reached its initial wait before the owner releases.
            time.sleep(0.05)
        with gate.acquire(timeout=2):
            order.append("barger")
        result.result(timeout=3)
    assert order == ["reader", "barger"]


def test_timed_out_waiter_does_not_strand_later_readers(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    gate = storage.get_active_leg_lock()

    def timed_reader():
        with pytest.raises(Timeout), gate.acquire(timeout=0.03):
            pytest.fail("Entered an owned gate")

    with ThreadPoolExecutor(max_workers=1) as workers:
        with gate:
            workers.submit(timed_reader).result(timeout=1)
        with gate.acquire(timeout=0.1):
            assert gate.is_locked
    assert not gate.is_locked


def test_nested_owner_releases_only_after_outer_scope(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    gate = storage.get_active_leg_lock()
    with gate:
        with gate.acquire(timeout=0):
            assert gate.is_locked
        assert gate.is_locked
    assert not gate.is_locked


def test_external_file_wait_timeout_releases_local_admission(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    gate = storage.get_active_leg_lock()
    entered, release = threading.Event(), threading.Event()

    def external_writer():
        with FileLock(gate.lock_file):
            entered.set()
            assert release.wait(2)

    with ThreadPoolExecutor(max_workers=1) as workers:
        result = workers.submit(external_writer)
        try:
            assert entered.wait(1)
            with pytest.raises(Timeout), gate.acquire(timeout=0.03):
                pytest.fail("Entered an externally owned file lock")
        finally:
            release.set()
        result.result(timeout=2)
    with gate.acquire(timeout=0.1, poll_interval=None, blocking=None):
        assert gate.is_locked
    assert not gate.is_locked
