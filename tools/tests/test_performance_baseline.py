"""Reject misleading comparisons and distinguish warm growth from startup."""

import copy
import unittest

from acceptance.performance.report import compare, summarize


class BaselineReportTests(unittest.TestCase):
    def setUp(self):
        self.metadata = {
            "candidate_sha": "a" * 40,
            "workload": {"viewers": 2, "window": 3600, "cadence": 1},
            "hardware": {"cpu": "test", "cores": 2},
            "instrumentation": "counters",
            "harness_sha": "c" * 40,
            "browser": {"version": "test", "renderer": "software"},
            "runtime": {"mode": "simulation", "scrape_seconds": 1},
        }
        self.rows = [
            {
                "seconds": t,
                "phase": phase,
                "backend": {"cpu_seconds": cpu, "memory_bytes": mem},
                "latency": {"/api/status": [latency]},
            }
            for t, phase, cpu, mem, latency in [
                (0, "warmup", 0, 10000, 9999),
                (60, "measured", 10, 100, 10),
                (120, "measured", 40, 160, 20),
                (180, "measured", 70, 220, 30),
            ]
        ]

    def test_startup_does_not_contaminate_latency_or_growth(self):
        result = summarize(self.metadata, self.rows)
        self.assertEqual(result["latency"]["/api/status"]["p95_ms"], 30)
        self.assertEqual(result["latency"]["/api/status"]["samples"], 3)
        self.assertEqual(
            result["resources"]["backend.memory_bytes"]["slope_per_minute"], 60
        )
        self.assertEqual(result["resources"]["backend.cpu_seconds"]["cores_used"], 0.5)

    def test_comparison_keeps_original_reference_and_reports_regression(self):
        baseline = summarize(self.metadata, self.rows)
        changed = copy.deepcopy(self.rows)
        changed[-1]["backend"]["memory_bytes"] = 440
        candidate = summarize(self.metadata | {"candidate_sha": "b" * 40}, changed)
        delta = compare(baseline, candidate)
        self.assertEqual(delta["original_baseline_sha"], "a" * 40)
        self.assertEqual(delta["resources"]["backend.memory_bytes"]["last_delta"], 220)
        self.assertEqual(
            delta["resources"]["backend.memory_bytes"]["last_percent"], 100
        )

    def test_incompatible_workloads_never_produce_speedup(self):
        baseline = summarize(self.metadata, self.rows)
        for field in (
            "workload",
            "hardware",
            "instrumentation",
            "harness_sha",
            "browser",
            "runtime",
        ):
            with self.subTest(field=field):
                other = copy.deepcopy(baseline)
                other["metadata"][field] = "different"
                with self.assertRaisesRegex(ValueError, field):
                    compare(baseline, other)

    def test_missing_measurement_is_not_zero(self):
        result = summarize(self.metadata, [{"seconds": 0, "phase": "measured"}])
        self.assertEqual(result["resources"], {})
        self.assertEqual(result["latency"], {})
        self.assertFalse(result["sustained_60_minutes"])

    def test_nonfinite_measurements_fail(self):
        self.rows[-1]["backend"]["memory_bytes"] = float("nan")
        with self.assertRaises(ValueError):
            summarize(self.metadata, self.rows)

    def test_lost_resource_coverage_cannot_look_like_an_improvement(self):
        baseline = summarize(self.metadata, self.rows)
        other = copy.deepcopy(baseline)
        del other["resources"]["backend.cpu_seconds"]
        with self.assertRaisesRegex(ValueError, "coverage"):
            compare(baseline, other)

    def test_counter_reset_cannot_look_like_negative_cpu(self):
        self.rows[-1]["backend"]["cpu_seconds"] = 1
        with self.assertRaisesRegex(ValueError, "counter"):
            summarize(self.metadata, self.rows)


if __name__ == "__main__":
    unittest.main()
