"""Fair local admission before the canonical cross-process file lock."""

import math
import os
import threading
import time
from collections import deque

from filelock import FileLock, Timeout


class _Acquired:
    def __init__(self, gate):
        self.lock = gate

    def __enter__(self):
        return self.lock

    def __exit__(self, *args):
        self.lock.release()


class RepositoryGate:
    def __init__(self, path):
        self.process_id = os.getpid()
        self._file_lock = FileLock(path)
        self._condition = threading.Condition()
        self._waiters = deque()
        self._owner = None

    def __getattr__(self, name):
        return getattr(self._file_lock, name)

    def acquire(self, timeout=None, poll_interval=0.05, **kwargs):
        timeout = self._file_lock.timeout if timeout is None else float(timeout)
        blocking = kwargs.get("blocking")
        if blocking is None:
            blocking = getattr(self._file_lock, "blocking", True)
        if poll_interval is None:
            poll_interval = getattr(self._file_lock, "poll_interval", 0.05)
        if math.isnan(timeout) and blocking:
            raise ValueError("timeout must not be nan")
        if timeout == math.inf:
            timeout = -1
        deadline = None if timeout < 0 else time.monotonic() + timeout
        owner = threading.get_ident()
        ticket = object()
        with self._condition:
            nested = self._owner == owner
            if not nested:
                self._waiters.append(ticket)
                try:
                    while self._owner is not None or self._waiters[0] is not ticket:
                        remaining = (
                            None if deadline is None else deadline - time.monotonic()
                        )
                        cancel = kwargs.get("cancel_check")
                        if (
                            not blocking
                            or (remaining is not None and remaining <= 0)
                            or (cancel is not None and cancel())
                        ):
                            raise Timeout(self.lock_file)
                        self._condition.wait(
                            min(remaining, poll_interval)
                            if remaining is not None
                            else poll_interval
                        )
                except BaseException:
                    self._waiters.remove(ticket)
                    self._condition.notify_all()
                    raise
                self._waiters.popleft()
                self._owner = owner
        try:
            remaining = (
                timeout if deadline is None else max(0, deadline - time.monotonic())
            )
            self._file_lock.acquire(
                timeout=remaining, poll_interval=poll_interval, **kwargs
            )
        except BaseException:
            if not nested:
                with self._condition:
                    self._owner = None
                    self._condition.notify_all()
            raise
        return _Acquired(self)

    def release(self, force=False):
        try:
            self._file_lock.release(force=force)
        finally:
            with self._condition:
                if (
                    self._owner == threading.get_ident()
                    and not self._file_lock.is_locked
                ):
                    self._owner = None
                    self._condition.notify_all()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()
