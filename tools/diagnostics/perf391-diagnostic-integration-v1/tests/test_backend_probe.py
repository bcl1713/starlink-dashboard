"""Probe failures must never replace application outcomes or retain unbounded data."""

import asyncio
import importlib
import math
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import contract  # noqa: E402


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(
            (PACKAGE / "backend_probe.py").is_file(), "backend probe missing"
        )
        self.p = importlib.import_module("backend_probe")
        self.p.configure("C", "offline", capacity=8)

    def test_closed_records_parent_context_and_unavailable_nonfinite(self):
        with self.p.operation("parent", "tick"):
            with self.p.operation("child", "replay"):
                self.p.mark("replay.commit", identity={"replay_mission_time": math.nan})
        records = self.p.drain()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["op_id"], "child")
        self.assertEqual(records[0]["parent_op_id"], "parent")
        self.assertIsNone(records[0]["identity"]["replay_mission_time"])
        self.assertIn("replay_mission_time", records[0]["unavailable"])
        contract.validate_stream(records)

    def test_bounded_overflow_invalid_identity_and_faults_are_counted(self):
        for _ in range(20):
            self.p.mark("producer.start", op_id="tick")
        self.assertEqual(len(self.p.drain()), 8)
        self.assertEqual(self.p.stats()["dropped"], 12)
        self.p.mark("invented.phase", op_id="tick")
        self.p.mark("producer.start", op_id="x" * 97)
        self.p.mark("producer.start", identity={"unapproved": "secret"})
        self.assertEqual(self.p.stats()["invalid"], 3)
        self.assertEqual(self.p.drain(), [])

    def test_sync_bracket_preserves_result_and_baseexception(self):
        @self.p.bracket("collection.enter", "collection.return", telemetry=True)
        def normal(value):
            return value

        sentinel = object()
        self.assertIs(normal(sentinel), sentinel)
        self.assertEqual(
            [e["phase"] for e in self.p.drain()],
            ["collection.enter", "collection.return"],
        )
        failure = asyncio.CancelledError("owned")

        @self.p.bracket("collection.enter", "collection.return")
        def fail():
            raise failure

        with self.assertRaises(asyncio.CancelledError) as raised:
            fail()
        self.assertIs(raised.exception, failure)
        self.assertEqual(self.p.drain()[-1]["outcome"], "cancelled")
        with self.p.faults():
            self.assertIs(normal(sentinel), sentinel)
            with self.assertRaises(asyncio.CancelledError) as raised:
                fail()
            self.assertIs(raised.exception, failure)
        self.assertGreater(self.p.stats()["failures"], 0)

    def test_numeric_scalars_follow_closed_string_identity_contract(self):
        self.p.mark(
            "collection.return",
            identity={"observation_timestamp": 100.5, "input_revision": 3},
        )
        record = self.p.drain()[0]
        self.assertEqual(
            record["identity"],
            {"observation_timestamp": "100.5", "input_revision": "3"},
        )
        contract.validate_event(record)

    def test_nested_collection_is_one_pair_with_retained_identity(self):
        from types import SimpleNamespace

        value = object()
        source = SimpleNamespace(_last_valid_telemetry=value)

        @self.p.source_collection
        def update(source):
            return source._last_valid_telemetry

        self.assertIs(self.p.collect_update(update, source), value)
        records = self.p.drain()
        self.assertEqual(
            [e["phase"] for e in records], ["collection.enter", "collection.return"]
        )
        self.assertEqual(
            records[-1]["identity"]["retained_token"],
            records[-1]["identity"]["object_token"],
        )
        failure = ValueError("sensor")

        @self.p.source_collection
        def fail(source):
            raise failure

        with self.assertRaises(ValueError) as raised:
            self.p.collect_update(fail, source)
        self.assertIs(raised.exception, failure)
        self.assertEqual([e["outcome"] for e in self.p.drain()], ["ok", "error"])

    def test_invalid_context_and_a_frame_fields_cannot_escape_closed_contract(self):
        with self.p.operation("x" * 97, "tick"):
            with self.p.operation("child", "tick"):
                self.p.mark("producer.start")
        with self.p.operation("valid", "invented"):
            self.p.mark("producer.start")
        self.assertEqual(self.p.drain(), [])
        self.assertEqual(self.p.stats()["invalid"], 2)
        self.p.configure("A", "offline")
        self.p.mark("publication.swap")
        self.p.mark("collection.return", identity={"frame_id": "frame"})
        self.assertEqual(self.p.drain(), [])
        self.assertEqual(self.p.stats()["invalid"], 2)

    def test_a_never_projects_atomic_publication(self):
        self.p.configure("A", "offline")
        for name in ("immutable_frame", "final_authority", "ready_frame_cas"):
            self.assertFalse(contract.capability("A", name)["available"])
        self.p.publication(True, object(), kind="ready")
        self.assertNotIn("producer.published", [e["phase"] for e in self.p.drain()])

    def test_missing_captured_clock_is_not_replaced_by_emission_time(self):
        self.p.mark("publication.swap", at=None)
        self.assertEqual(self.p.drain(), [])
        self.assertEqual(self.p.stats()["failures"], 1)

    def test_swap_timestamp_is_captured_before_emission(self):
        stamp = self.p.stamp()
        self.p.mark("publication.swap", at=stamp, identity={"publication_kind": "fail"})
        record = self.p.drain()[0]
        self.assertEqual(record["mono_ns"], str(stamp[0]))
        self.assertEqual(record["identity"]["publication_kind"], "fail")
        contract.validate_event(record)


if __name__ == "__main__":
    unittest.main()
