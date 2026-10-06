"""Bounded owned process teardown and time reserved for diagnostic evidence."""

from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

SEAL_RESERVE_SECONDS = 3.0


class CleanupDeadlineExpired(BaseException):
    """Cannot be swallowed by a platform helper's ordinary exception fallback."""


class Deadline:
    """Stop work early; retain cleanup/sealing inside the outer 20-minute cap."""

    def __init__(self, work_seconds=960.0, total_seconds=1200.0, signal_seconds=8.0):
        if not 0 < work_seconds < total_seconds <= 1200 or not 0 < signal_seconds <= 8:
            raise ValueError("invalid diagnostic deadline")
        self.work_seconds = work_seconds
        self.end = time.monotonic() + total_seconds
        self.signal_seconds = signal_seconds
        self.cleaning = False
        self.interrupted = False
        self.work_stopped = False
        self.previous: dict = {}
        self.phase_reserve: float | None = None

    def __enter__(self):
        for number in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT):
            self.previous[number] = signal.signal(number, self._interrupt)
        signal.setitimer(signal.ITIMER_REAL, self.work_seconds)
        return self

    def _interrupt(self, number, _frame):
        if (
            number == signal.SIGALRM
            and self.cleaning
            and self.phase_reserve is not None
        ):
            raise CleanupDeadlineExpired("cleanup operation exhausted mutable deadline")
        if number != signal.SIGALRM:
            self.interrupted = True
            self.end = min(self.end, time.monotonic() + self.signal_seconds)
            if self.phase_reserve is not None:
                signal.setitimer(
                    signal.ITIMER_REAL, max(0.001, self.remaining(self.phase_reserve))
                )
        if not self.cleaning:
            self.work_stopped = True
            if number == signal.SIGALRM:
                raise TimeoutError("diagnostic work deadline; cleanup time reserved")
            raise InterruptedError(f"diagnostic signal {number}")

    def begin_cleanup(self):
        self.cleaning = True
        signal.setitimer(signal.ITIMER_REAL, 0)

    def remaining(self, reserve=0.0):
        return max(0.0, self.end - time.monotonic() - reserve)

    def wait(self, child: subprocess.Popen, seconds: float, reserve=2.0):
        end = time.monotonic() + seconds
        while child.poll() is None:
            available = min(end - time.monotonic(), self.remaining(reserve))
            if available <= 0:
                raise subprocess.TimeoutExpired(child.args, seconds)
            try:
                return child.wait(timeout=min(0.05, available))
            except subprocess.TimeoutExpired:
                pass
        return child.returncode

    @contextmanager
    def cleanup_phase(self, *, reserve=SEAL_RESERVE_SECONDS):
        """Bound platform/file operations, including a signal arriving mid-call."""
        if not self.cleaning or self.phase_reserve is not None:
            raise ValueError("cleanup phase must be unnested and follow begin_cleanup")
        if self.remaining(reserve) <= 0:
            raise CleanupDeadlineExpired("no time available for cleanup operation")
        self.phase_reserve = reserve
        signal.setitimer(signal.ITIMER_REAL, self.remaining(reserve))
        try:
            yield
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            self.phase_reserve = None

    def __exit__(self, *_):
        signal.setitimer(signal.ITIMER_REAL, 0)
        for number, handler in self.previous.items():
            signal.signal(number, handler)


def enable_subreaper():
    """Adopt orphaned owned grandchildren so dead leaders cannot leave zombies."""
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # Linux PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), "cannot enable owned-child reaping")


def group_members(groups: set[int]) -> list[int]:
    members = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
            if int(fields[2]) in groups:
                members.append(int(entry.name))
        except (OSError, ValueError, IndexError):
            continue
    return members


def stop_owned_groups(
    groups: list[int],
    *,
    grace=1.0,
    seconds=3.0,
    budget: Deadline | None = None,
    reserve=SEAL_RESERVE_SECONDS,
) -> dict:
    """Signal only recorded private groups, even if their leaders already exited."""
    owned = set(groups)
    if any(group <= 1 or group == os.getpgrp() for group in owned):
        raise ValueError("refusing unowned/shared process group")
    end = time.monotonic() + max(0, seconds)
    killed = []

    def available(until, force_reserve=0):
        return max(
            0,
            min(
                until - time.monotonic(),
                budget.remaining(reserve + force_reserve) if budget else float("inf"),
            ),
        )

    def reap():
        # Only adopted children in explicitly owned groups; never unrelated children.
        for pid in group_members(owned):
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                pass

    def send(number):
        for group in owned:
            try:
                os.killpg(group, number)
            except ProcessLookupError:
                pass

    send(signal.SIGTERM)
    graceful_end = min(end, time.monotonic() + grace)
    while group_members(owned) and available(graceful_end, 0.25) > 0:
        reap()
        time.sleep(0.01)
    reap()
    for group in owned:
        if group_members({group}):
            killed.append(group)
            try:
                os.killpg(group, signal.SIGKILL)
            except ProcessLookupError:
                pass
    while group_members(owned) and available(end) > 0:
        reap()
        time.sleep(0.01)
    reap()
    return {"remaining": group_members(owned), "killed_descendants": killed}


def stop_owned_process(
    child: subprocess.Popen, budget: Deadline, *, grace=0.5, reserve=1.0
) -> dict:
    """Stop an exact owned child that legitimately shares the wrapper group."""
    if child.pid <= 1 or child.pid == os.getpid():
        raise ValueError("refusing unowned process")
    killed = []
    if child.poll() is None:
        child.terminate()
        try:
            budget.wait(child, grace, reserve=reserve + 0.25)
        except subprocess.TimeoutExpired:
            killed.append(child.pid)
            child.kill()
            try:
                budget.wait(child, 0.5, reserve=reserve)
            except subprocess.TimeoutExpired:
                pass
    return {
        "remaining": [child.pid] if child.poll() is None else [],
        "killed_descendants": killed,
    }
