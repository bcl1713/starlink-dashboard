"""Bounded owned process teardown and time reserved for diagnostic evidence."""

from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import time
from pathlib import Path


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

    def __enter__(self):
        for number in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT):
            self.previous[number] = signal.signal(number, self._interrupt)
        signal.setitimer(signal.ITIMER_REAL, self.work_seconds)
        return self

    def _interrupt(self, number, _frame):
        if number != signal.SIGALRM:
            self.interrupted = True
            self.end = min(self.end, time.monotonic() + self.signal_seconds)
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


def stop_owned_groups(groups: list[int], *, grace=1.0, seconds=3.0) -> dict:
    """Signal only recorded private groups, even if their leaders already exited."""
    owned = set(groups)
    if any(group <= 1 or group == os.getpgrp() for group in owned):
        raise ValueError("refusing unowned/shared process group")
    end = time.monotonic() + max(0, seconds)
    killed = []

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
    while group_members(owned) and time.monotonic() < graceful_end:
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
    while group_members(owned) and time.monotonic() < end:
        reap()
        time.sleep(0.01)
    reap()
    return {"remaining": group_members(owned), "killed_descendants": killed}
