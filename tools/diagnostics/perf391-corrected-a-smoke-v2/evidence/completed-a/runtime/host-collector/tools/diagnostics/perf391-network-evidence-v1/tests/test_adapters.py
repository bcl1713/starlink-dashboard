import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from perf391_network_evidence.adapters import (
    admission,
    diagnostic_worker,
    import_legacy,
    observe_once,
    sample_resources,
)
from perf391_network_evidence.analyze import analyze
from perf391_network_evidence.record import Recorder


class AdapterTests(unittest.TestCase):
    def test_resource_missing_and_ancestor_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "cpu.stat").write_text("nr_throttled 9\nthrottled_usec 120\n")
            (root / "cpu.max").write_text("200000 100000")
            data = sample_resources(
                proc_root=root / "absent", cgroups=[root], pids=[999999]
            )
            self.assertEqual(
                data["files"][str(root / "cpu.stat")]["value"],
                "nr_throttled 9\nthrottled_usec 120\n",
            )
            self.assertIsNone(data["files"][str(root / "cpu.pressure")]["value"])
            self.assertTrue(data["files"][str(root / "cpu.pressure")]["reason"])

    def test_legacy_import_preserves_missing_and_op_ids(self):
        trace = {
            "session": "s1",
            "dropped": 2,
            "events": [
                {
                    "event": "worker_dispatch.start",
                    "ns": 10,
                    "op": "diag-1",
                    "span": 1,
                    "pid": 3,
                    "tid": 3,
                },
                {
                    "event": "worker_execution.start",
                    "ns": 20,
                    "op": "diag-1",
                    "span": 2,
                    "pid": 3,
                    "tid": 4,
                },
                {
                    "event": "worker_execution.end",
                    "ns": 30,
                    "op": "diag-1",
                    "span": 2,
                    "pid": 3,
                    "tid": 4,
                },
                {
                    "event": "worker_dispatch.end",
                    "ns": 70,
                    "op": "diag-1",
                    "span": 1,
                    "pid": 3,
                    "tid": 3,
                },
            ],
        }
        rows = import_legacy(trace, run_id="legacy-run")
        result = analyze(rows)
        self.assertEqual(
            result["operations"]["diag-1"]["worker_completion"]["value_ns"], 40
        )
        self.assertIsNone(
            result["operations"]["diag-1"]["producer_completion"]["value_ns"]
        )
        self.assertEqual(result["dropped"], 2)
        self.assertTrue(any(not x["available"] for x in result["coverage"]))

    def test_diagnostic_worker_and_admission_cleanup(self):
        import threading

        with tempfile.TemporaryDirectory() as tmp:
            with Recorder(tmp) as rec:

                async def run():
                    def work():
                        with admission(rec, threading.RLock(), "tick1"):
                            return 42

                    return await diagnostic_worker(rec, "producer", "tick1", work)

                self.assertEqual(asyncio.run(run()), 42)
            rows = [
                json.loads(x)
                for x in (Path(tmp) / "events.jsonl").read_text().splitlines()
            ]
            result = analyze(rows)
            self.assertIsNotNone(
                result["operations"]["tick1"]["producer_completion"]["value_ns"]
            )
            self.assertEqual(len(result["admissions"]), 1)
            self.assertIsNotNone(result["admissions"][0]["wait"]["value_ns"])

    def test_observer_fake_response_body_parse_and_error_cleanup(self):
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.closed = True

            def read(self, size):
                return b'{"ready":true}'

        response = Response()
        with tempfile.TemporaryDirectory() as tmp:
            with Recorder(tmp) as rec:
                observe_once(
                    rec,
                    "http://fictional.invalid/state",
                    "diag-1",
                    0,
                    opener=lambda *a, **k: response,
                )
            self.assertTrue(response.closed)
            rows = [
                json.loads(x)
                for x in (Path(tmp) / "events.jsonl").read_text().splitlines()
            ]
            self.assertIsNotNone(
                analyze(rows)["operations"]["diag-1"]["observer_parse"]["value_ns"]
            )


if __name__ == "__main__":
    unittest.main()
