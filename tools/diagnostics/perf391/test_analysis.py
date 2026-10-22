"""Reject attribution that subtracts clocks or silently drops failed samples."""

import unittest

import analyze


class AnalysisTests(unittest.TestCase):
    def test_durations_join_by_request_without_subtracting_clock_origins(self):
        observer = {
            "events": [
                {"event": "http.send", "ns": 100, "op": "diag-1"},
                {"event": "http.body", "ns": 1100, "op": "diag-1"},
            ],
            "captures": [],
        }
        backend = {
            "events": [
                {"event": "asgi.arrival", "ns": 10**15, "op": "diag-1"},
                {"event": "asgi.end", "ns": 10**15 + 700, "op": "diag-1"},
            ],
            "dropped": 0,
        }
        result = analyze.correlate(observer, backend)
        self.assertEqual(result[0]["rtt_ns"], 1000)
        self.assertEqual(result[0]["server_ns"], 700)
        self.assertEqual(result[0]["unallocated_ns"], 300)
        backend["events"].extend(
            [
                {"event": "worker_dispatch.start", "ns": 10**15 + 10, "op": "diag-1"},
                {"event": "worker_execution.start", "ns": 10**15 + 40, "op": "diag-1"},
                {"event": "worker_execution.end", "ns": 10**15 + 90, "op": "diag-1"},
                {"event": "worker_dispatch.end", "ns": 10**15 + 650, "op": "diag-1"},
            ]
        )
        detailed = analyze.correlate(observer, backend)[0]
        self.assertEqual(detailed["worker_queue_ns"], 30)
        self.assertEqual(detailed["worker_service_ns"], 50)
        self.assertEqual(detailed["worker_return_to_loop_ns"], 560)

    def test_failed_or_unmatched_request_remains_explicit(self):
        result = analyze.correlate(
            {
                "events": [
                    {"event": "http.send", "ns": 1, "op": "diag-0"},
                    {"event": "http.error", "ns": 4, "op": "diag-0"},
                ],
                "captures": [],
            },
            {"events": []},
        )
        self.assertEqual(result[0]["outcome"], "incomplete")
        self.assertIsNone(result[0]["server_ns"])

    def test_async_dispatch_cpu_is_not_assigned_to_worker(self):
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "trace").mkdir()
            (root / "run.json").write_text(
                json.dumps({"status": "diagnostic-measured", "candidate_sha": "test"})
            )
            (root / "observer.json").write_text(
                json.dumps({"events": [], "captures": [], "traffic": []})
            )
            (root / "trace/backend.json").write_text(
                json.dumps(
                    {
                        "dropped": 0,
                        "events": [
                            {
                                "event": "worker_dispatch.end",
                                "ns": 100,
                                "wall_ns": 100,
                                "cpu_ns": 70,
                            },
                            {
                                "event": "worker_execution.end",
                                "ns": 90,
                                "wall_ns": 80,
                                "cpu_ns": 10,
                            },
                        ],
                    }
                )
            )
            result = analyze.analyze(root)
        self.assertNotIn("worker_dispatch", result["thread_cpu_ns"])
        self.assertEqual(result["thread_cpu_ns"]["worker_execution"]["max"], 10)

    def test_off_control_does_not_report_missing_backend_instrumentation_as_failure(
        self,
    ):
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "run.json").write_text(
                json.dumps(
                    {
                        "status": "diagnostic-measured",
                        "candidate_sha": "test",
                        "instrumentation": "off",
                    }
                )
            )
            (root / "observer.json").write_text(
                json.dumps(
                    {
                        "events": [
                            {"event": "http.send", "ns": 0, "op": "diag-0"},
                            {"event": "http.body", "ns": 100, "op": "diag-0"},
                        ],
                        "captures": [],
                        "traffic": [],
                    }
                )
            )
            result = analyze.analyze(root)
        self.assertEqual(result["requests"], [])
        self.assertEqual(result["backend_attribution"], "disabled by control design")
        self.assertEqual(result["durations_ns"]["observer_http"]["max"], 100)

    def test_gap_distribution_retains_failure(self):
        result = analyze.capture_gaps(
            [{"capture_ns": 0}, {"capture_ns": 1000000000}, {"capture_ns": 2600000000}]
        )
        self.assertEqual(result["over_1_5_seconds"], 1)
        self.assertEqual(result["ns"]["max"], 1600000000)


if __name__ == "__main__":
    unittest.main()
