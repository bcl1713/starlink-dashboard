"""Deterministic envelope bytes and refusal to fabricate mutex/identity evidence."""

import json
import threading
import unittest
from itertools import count
from pathlib import Path
from unittest.mock import patch

from backend_support import module_at, probe, roots

import build
import contract

PACKAGE = Path(__file__).resolve().parents[1]


class BoundsTests(unittest.TestCase):
    def test_fixed_clock_fixture_is_byte_identical(self):
        fixed = json.loads((PACKAGE / "fixtures/stage2-event.json").read_text())
        captures = []
        for _ in range(2):
            with patch.object(
                probe, "_process", "11111111-1111-4111-8111-111111111111"
            ), patch.object(probe, "_process_start", "proc-start-1"), patch.object(
                probe, "_pid", 100
            ), patch.object(
                probe, "_serial", count(1)
            ), patch.object(
                probe.time, "monotonic_ns", return_value=100
            ), patch.object(
                probe.time, "thread_time_ns", return_value=10
            ), patch.object(
                probe.threading, "get_native_id", return_value=101
            ):
                probe.configure("C", "fixture")
                with probe.operation("tick-1", "tick"):
                    probe.mark("collection.enter", span_id="span-1")
                record = probe.drain()[0]
                self.assertEqual(record, fixed)
                captures.append(build.canonical(record) + b"\n")
                contract.validate_event(record)
        self.assertEqual(captures[0], captures[1])
        self.assertEqual(
            build.digest(captures[0]),
            (PACKAGE / "fixtures/stage2-event.sha256").read_text().strip(),
        )

    def test_concurrent_saturation_counts_every_lost_record(self):
        probe.configure("C", "offline", capacity=4)
        barrier = threading.Barrier(12)
        original_tid = probe.threading.get_native_id

        def delayed_tid():
            barrier.wait(timeout=5)
            return original_tid()

        threads = [
            threading.Thread(target=probe.mark, args=("producer.start",))
            for _ in range(12)
        ]
        with patch.object(
            probe,
            "threading",
            __import__("types").SimpleNamespace(get_native_id=delayed_tid),
        ):
            try:
                for thread in threads:
                    thread.start()
            finally:
                for thread in threads:
                    if thread.ident is not None:
                        thread.join(6)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(len(probe.drain()), 4)
        self.assertEqual(probe.stats()["dropped"], 8)
        self.assertEqual(probe.stats()["failures"], 0)

    def test_concurrent_lookup_canonicalizes_one_process_token(self):
        probe.configure("C", "offline")
        target = object()
        barrier = threading.Barrier(12)
        results = []

        def lookup():
            barrier.wait(timeout=5)
            results.append(probe.token(target))

        threads = [threading.Thread(target=lookup) for _ in range(12)]
        try:
            for thread in threads:
                thread.start()
        finally:
            for thread in threads:
                if thread.ident is not None:
                    thread.join(6)
        self.assertFalse(any(t.is_alive() for t in threads))
        self.assertEqual(len(results), 12)
        self.assertNotIn(None, results)
        self.assertEqual(len(set(results)), 1)

    def test_global_admission_span_cap_and_token_reuse(self):
        probe.configure("C", "offline")
        gates = [object() for _ in range(257)]
        for i, gate in enumerate(gates):
            probe.repository_granted(
                gate, "span-" + str(i), probe.stamp(), probe.stamp()
            )
        events = probe.drain()
        self.assertEqual(sum(e["phase"] == "repo.local_grant" for e in events), 256)
        self.assertEqual(probe.stats()["dropped"], 1)
        self.assertEqual(len(probe._free_hold_slots), 0)
        for gate in gates[:256]:
            probe.repository_released(gate, probe.stamp(), probe.stamp())
        self.assertEqual(len(probe._free_hold_slots), 256)
        first = object()
        old = probe.token(first)
        for _ in range(256):
            probe.token(object())
        self.assertNotEqual(probe.token(first), old)
        self.assertLessEqual(len(probe._tokens), 256)
        self.assertEqual(len(probe._tokens) + len(probe._free_token_slots), 256)
        self.assertGreater(probe.stats()["token_evictions"], 0)

    def test_no_emission_or_tokens_inside_pointer_mutex(self):
        root = roots("C")[True]
        frames = module_at(root, "app/core/metrics/frames.py")
        store = frames.FrameStore(())
        active = threading.local()
        active.held = False

        class Lock:
            def __init__(self):
                self.lock = threading.Lock()

            def __enter__(self):
                self.lock.acquire()
                active.held = True

            def __exit__(self, *a):
                active.held = False
                self.lock.release()

        store._lock = Lock()
        violations = []
        original_mark, original_token = probe.mark, probe.token

        def mark(*a, **kw):
            if active.held:
                violations.append("mark")
            return original_mark(*a, **kw)

        def token(*a, **kw):
            if active.held:
                violations.append("token")
            return original_token(*a, **kw)

        probe.configure("C", "offline")
        with patch.object(probe, "mark", mark), patch.object(
            probe, "token", token
        ), probe.operation("tick", "tick"):
            expected = store.read()
            frame = frames.GaugeFrame(frames.FrameIdentity(), (), 1.0)
            self.assertTrue(store.publish(expected, frame))
            self.assertFalse(store.publish(expected, frame))
            store.invalidate("source changed")
            store.fail(store.read(), "failed")
        self.assertEqual(violations, [])
        self.assertEqual(
            sum(e["phase"] == "publication.swap" for e in probe.drain()), 3
        )

    def test_no_emission_inside_repository_condition(self):
        import tempfile

        for role in ("A", "C"):
            root = roots(role)[True]
            gate_type = module_at(root, "app/mission/repository_gate.py").RepositoryGate
            with tempfile.TemporaryDirectory(prefix="perf391-stage2-condition-") as tmp:
                gate = gate_type(tmp + "/gate")
                violations = []
                original_mark = probe.mark

                def mark(*a, **kw):
                    if gate._condition._is_owned():
                        violations.append(a[0])
                    return original_mark(*a, **kw)

                probe.configure(role, "offline")
                with patch.object(probe, "mark", mark):
                    with gate:
                        with gate:
                            pass
                self.assertEqual(violations, [])
                self.assertFalse(gate.is_locked)
