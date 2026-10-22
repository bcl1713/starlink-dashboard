"""Behavioral checks for bounded, payload-free diagnostic tracing."""

import asyncio
import tempfile
import time
import unittest
from pathlib import Path

import trace391


class TraceTests(unittest.TestCase):
    def test_disabled_does_not_read_clock_or_retain_events(self):
        trace = trace391.Trace(enabled=False)
        with trace.span("disabled"):
            pass
        self.assertEqual(trace.rows, [])

    def test_spans_preserve_exceptions_and_attribute_wall_and_thread_cpu(self):
        trace = trace391.Trace()
        with self.assertRaisesRegex(ValueError, "secret"), trace.span("collection"):
            time.sleep(0.025)
            raise ValueError("secret")
        end = trace.rows[-1]
        self.assertEqual(end["outcome"], "ValueError")
        self.assertGreater(end["wall_ns"], 20_000_000)
        self.assertLess(end["cpu_ns"], end["wall_ns"])
        self.assertNotIn("secret", str(trace.rows))

    def test_bounded_buffer_reports_loss_instead_of_silently_accepting(self):
        trace = trace391.Trace(limit=3)
        for _ in range(10):
            trace.event("wake")
        self.assertEqual(len(trace.rows), 3)
        self.assertEqual(trace.dropped, 7)

    def test_cross_thread_context_has_same_request_and_distinct_thread(self):
        trace = trace391.Trace()

        async def run():
            token = trace391.operation.set("request-1")
            try:
                trace.event("dispatch")
                await asyncio.to_thread(trace.event, "worker")
            finally:
                trace391.operation.reset(token)

        asyncio.run(run())
        self.assertEqual([x["op"] for x in trace.rows], ["request-1"] * 2)
        self.assertNotEqual(trace.rows[0]["tid"], trace.rows[1]["tid"])

    def test_wrapper_restores_original_and_preserves_result(self):
        class Target:
            def calculate(self):
                return 42

        trace = trace391.Trace()
        original = Target.calculate
        trace.wrap(Target, "calculate", "prepare")
        self.assertEqual(Target().calculate(), 42)
        self.assertEqual(
            [r["event"] for r in trace.rows], ["prepare.start", "prepare.end"]
        )
        trace.close()
        self.assertIs(Target.calculate, original)

    def test_metadata_failure_does_not_change_wrapped_result(self):
        class Target:
            def calculate(self):
                return 42

        trace = trace391.Trace()

        def broken_metadata(result):
            raise AttributeError("missing optional field")

        trace.wrap(Target, "calculate", "work", after=broken_metadata)
        self.assertEqual(Target().calculate(), 42)
        self.assertTrue(any(r["event"] == "metadata.unavailable" for r in trace.rows))
        trace.close()

    def test_config_token_accepts_startup_namespace(self):
        from types import SimpleNamespace

        self.assertEqual(
            len(trace391.model_token(SimpleNamespace(mode="simulation"))), 16
        )

    def test_only_allowlisted_metadata_and_identity_hashes(self):
        trace = trace391.Trace()
        with self.assertRaises(ValueError):
            trace.event("bad", mission_payload={"secret": 1})
        self.assertNotEqual(trace391.token("mission-secret"), "mission-secret")
        self.assertEqual(len(trace391.token("mission-secret")), 16)

    def test_atomic_flush_keeps_events_and_loss_count(self):
        trace = trace391.Trace(limit=1)
        trace.event("first")
        trace.event("second")
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "events.json"
            trace.flush(path)
            import json

            result = json.loads(path.read_text())
        self.assertEqual(result["dropped"], 1)
        self.assertEqual(len(result["events"]), 1)


if __name__ == "__main__":
    unittest.main()
