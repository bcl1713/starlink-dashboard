"""Real depth-zero FileLock grants, FIFO admission and release, for each role."""

import contextlib
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from backend_support import module_at, probe, roots
from filelock import Timeout

import contract


class AdmissionTests(unittest.TestCase):
    def exercise(self, role, patched, case, fault=False):
        root = roots(role)[patched]
        gate_type = module_at(root, "app/mission/repository_gate.py").RepositoryGate
        probe.configure(role, "offline")
        with tempfile.TemporaryDirectory(prefix="perf391-stage2-lock-") as tmp:
            gate = gate_type(str(Path(tmp) / "gate.lock"))
            values = []
            with probe.faults() if fault else contextlib.nullcontext():
                if case == "nested":
                    with gate.acquire() as outer:
                        self.assertIs(outer, gate)
                        with gate:
                            values.append(gate.lock_counter)
                        values.append(gate.lock_counter)
                    values.append(gate.is_locked)
                elif case == "exception":
                    with self.assertRaises(ValueError):
                        with gate:
                            raise ValueError("inside hold")
                    values.append(gate.is_locked)
                elif case == "force":
                    gate.acquire()
                    gate.acquire()
                    gate.release(force=True)
                    gate.release()
                    gate.release(force=True)
                    values.append(gate.is_locked)
                elif case in ("timeout", "cancel"):
                    entered, release = threading.Event(), threading.Event()

                    def holder():
                        with gate:
                            entered.set()
                            if not release.wait(5):
                                raise TimeoutError("holder barrier")

                    thread = threading.Thread(target=holder)
                    thread.start()
                    try:
                        self.assertTrue(entered.wait(5))
                        kwargs = (
                            {"cancel_check": lambda: True} if case == "cancel" else {}
                        )
                        with self.assertRaises(Timeout):
                            gate.acquire(timeout=0, **kwargs)
                        values.append(len(gate._waiters))
                    finally:
                        release.set()
                        thread.join(5)
                    self.assertFalse(thread.is_alive())
                    with gate:
                        values.append(gate.lock_counter)
                elif case == "file_timeout":
                    # Separate process really owns the cross-process lock.
                    command = [
                        sys.executable,
                        "-c",
                        'from filelock import FileLock; import sys; lock=FileLock(sys.argv[1]); lock.acquire(); print("held",flush=True); sys.stdin.readline(); lock.release()',
                        gate.lock_file,
                    ]
                    child = subprocess.Popen(
                        command,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        text=True,
                    )
                    try:
                        self.assertEqual(child.stdout.readline().strip(), "held")
                        with self.assertRaises(Timeout):
                            gate.acquire(timeout=0)
                        values.extend([gate._owner, len(gate._waiters), gate.is_locked])
                    finally:
                        try:
                            child.communicate("\n", timeout=5)
                        except subprocess.TimeoutExpired:
                            child.terminate()
                            try:
                                child.wait(2)
                            except subprocess.TimeoutExpired:
                                child.kill()
                                child.wait(2)
                    self.assertEqual(child.returncode, 0)
                    with gate:
                        values.append(gate.lock_counter)
                elif case == "fifo":
                    gate.acquire()
                    errors = []
                    threads = []

                    def contender(index):
                        try:
                            with gate.acquire(timeout=5):
                                values.append(index)
                        except BaseException as error:
                            errors.append(type(error).__name__)

                    try:
                        for index in range(2):
                            thread = threading.Thread(target=contender, args=(index,))
                            threads.append(thread)
                            thread.start()
                            deadline = time.monotonic() + 5
                            while True:
                                with gate._condition:
                                    queued = len(gate._waiters)
                                if queued == index + 1:
                                    break
                                if time.monotonic() >= deadline:
                                    self.fail("FIFO enqueue deadline")
                                time.sleep(0.001)
                    finally:
                        gate.release()
                        for thread in threads:
                            thread.join(6)
                    self.assertFalse(any(t.is_alive() for t in threads))
                    self.assertEqual(errors, [])
                    self.assertEqual(values, [0, 1])
                else:
                    raise AssertionError(case)
            self.assertFalse(gate.is_locked)
            self.assertIsNone(gate._owner)
            self.assertEqual(len(gate._waiters), 0)
        return values, probe.drain()

    def test_per_role_control_equivalence_and_exact_outer_pairs(self):
        for role in ("A", "C"):
            for case, holds, failed in (
                ("nested", 1, 0),
                ("exception", 1, 0),
                ("force", 1, 0),
                ("timeout", 2, 1),
                ("cancel", 2, 1),
                ("file_timeout", 1, 1),
                ("fifo", 3, 0),
            ):
                with self.subTest(role=role, case=case):
                    control, _ = self.exercise(role, False, case)
                    actual, events = self.exercise(role, True, case)
                    self.assertEqual(actual, control)
                    self.assertEqual(
                        sum(e["phase"] == "repo.acquired" for e in events), holds
                    )
                    self.assertEqual(
                        sum(e["phase"] == "repo.acquire_failed" for e in events), failed
                    )
                    acquired = {
                        e["span_id"] for e in events if e["phase"] == "repo.acquired"
                    }
                    released = {
                        e["span_id"] for e in events if e["phase"] == "repo.released"
                    }
                    self.assertEqual(acquired, released)
                    self.assertEqual(len(acquired), holds)
                    contract.validate_stream(events)

    def test_sink_failure_cannot_keep_lock_or_suppress_notify(self):
        for role in ("A", "C"):
            for case in (
                "nested",
                "exception",
                "force",
                "timeout",
                "file_timeout",
                "fifo",
            ):
                with self.subTest(role=role, case=case):
                    control, _ = self.exercise(role, False, case)
                    actual, _ = self.exercise(role, True, case, fault=True)
                    self.assertEqual(actual, control)
