"""Reject misleading comparisons and distinguish warm growth from startup."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from acceptance.performance.lifecycle import identity, verify_browser
from acceptance.performance.report import compare, summarize


class BaselineReportTests(unittest.TestCase):
    def setUp(self):
        self.metadata = {
            "candidate_sha": "a" * 40,
            "request_outcomes": {"unexpected_failures": 0},
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
        baseline["latency"]["/api/status"]["samples"] = 200
        candidate["latency"]["/api/status"]["samples"] = 200
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

    def test_single_surviving_sample_is_not_comparable_coverage(self):
        baseline = summarize(self.metadata, self.rows)
        candidate = copy.deepcopy(baseline)
        candidate["resources"]["backend.memory_bytes"].update(samples=1, span_seconds=0)
        with self.assertRaisesRegex(ValueError, "coverage"):
            compare(baseline, candidate)


class LatencyCoverageTests(unittest.TestCase):
    def summaries(self, before, after, endpoint="/api/overview-history", span=120):
        metadata = {
            "candidate_sha": "a" * 40,
            "workload": {"viewers": 1, "cadence": 1},
            "request_outcomes": {"unexpected_failures": 0},
        }
        baseline = summarize(
            metadata,
            [
                {"phase": "measured", "seconds": 0},
                {"phase": "measured", "seconds": span},
            ],
        )
        baseline["latency"][endpoint] = {
            "samples": before,
            "p50_ms": 100,
            "p95_ms": 200,
            "p99_ms": 300,
        }
        candidate = copy.deepcopy(baseline)
        candidate["metadata"]["candidate_sha"] = "b" * 40
        candidate["latency"][endpoint]["samples"] = after
        return baseline, candidate

    def test_insufficient_samples_on_either_side_are_incomparable(self):
        for before, after in [(100, 1), (1, 100), (100, 2), (0, 100)]:
            with (
                self.subTest(before=before, after=after),
                self.assertRaisesRegex(ValueError, "latency coverage"),
            ):
                compare(*self.summaries(before, after))

    def test_material_count_differences_are_incomparable(self):
        for endpoint in (
            "/api/overview-history",
            "observer_status",
            "/api/v2/operator/events",
            "backend_/metrics",
            "frame",
        ):
            for before, after in [(200, 50), (50, 200)]:
                with (
                    self.subTest(endpoint=endpoint, before=before, after=after),
                    self.assertRaisesRegex(ValueError, "completion rate"),
                ):
                    compare(*self.summaries(before, after, endpoint))

    def test_normal_polling_jitter_reports_counts_and_rates(self):
        baseline, candidate = self.summaries(100, 97)
        result = compare(baseline, candidate)["latency"]["/api/overview-history"]
        self.assertEqual(result["coverage_class"], "polling")
        self.assertEqual(result["samples_before"], 100)
        self.assertEqual(result["samples_after"], 97)
        self.assertAlmostEqual(result["completions_per_second_before"], 100 / 120)
        self.assertAlmostEqual(result["completions_per_second_after"], 97 / 120)
        self.assertEqual(result["p95_ms_delta"], 0)

    def test_observer_requests_use_their_lower_frequency(self):
        baseline, candidate = self.summaries(25, 24, "observer_status")
        result = compare(baseline, candidate)["latency"]["observer_status"]
        self.assertEqual(result["coverage_class"], "observer")
        # The same count is insufficient for a two-viewer polling workload.
        for item in (baseline, candidate):
            item["metadata"]["workload"]["viewers"] = 2
            item["latency"]["/api/overview-history"] = item["latency"].pop(
                "observer_status"
            )
        with self.assertRaisesRegex(ValueError, "latency coverage"):
            compare(baseline, candidate)

    def test_low_frequency_endpoint_still_requires_enough_samples(self):
        with self.assertRaisesRegex(ValueError, "latency coverage"):
            compare(*self.summaries(3, 3, "/api/v2/operator/events"))
        compare(*self.summaries(8, 7, "/api/v2/operator/events"))

    def test_matching_but_stalled_polling_is_incomparable(self):
        with self.assertRaisesRegex(ValueError, "latency coverage"):
            compare(*self.summaries(100, 100, span=600))

    def test_failed_requests_cannot_hide_behind_successful_latencies(self):
        for side in (0, 1):
            pair = self.summaries(100, 100)
            pair[side]["metadata"]["request_outcomes"]["unexpected_failures"] = 1
            with self.assertRaisesRegex(ValueError, "failed requests"):
                compare(*pair)

    def test_duration_normalized_rate_detects_short_window_mismatch(self):
        pair = self.summaries(30, 30, span=30)
        pair[1]["measured_span_seconds"] = 40
        with self.assertRaisesRegex(ValueError, "completion rate"):
            compare(*pair)


class BrowserCleanupTests(unittest.TestCase):
    def test_history_validation_records_adaptive_grid_and_rejects_gaps(self):
        module = (
            Path(__file__).parents[1] / "acceptance/performance/polling.mjs"
        ).as_uri()
        result = subprocess.run(
            [
                "node",
                "--input-type=module",
                "-e",
                f"""
import {{validateHistory}} from {json.dumps(module)};
const series=Object.fromEntries(Array.from({{length:11}},(_,i)=>['metric'+i,Array.from({{length:1801}},(_,n)=>[n*2,1])]));
const history={{window_seconds:3600,step_seconds:2,start_timestamp_seconds:0,end_timestamp_seconds:3600,series}};
const values=[validateHistory(history,3600)];
series.metric0[20][1]=null;
try {{validateHistory(history,3600);values.push('accepted');}}
catch {{values.push('rejected');}}
series.metric0[20][1]=1;
series.metric0[20][0]=series.metric0[19][0];
try {{validateHistory(history,3600);values.push('accepted');}}
catch {{values.push('rejected');}}
console.log(JSON.stringify(values));
""",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(json.loads(result.stdout), [2, "rejected", "rejected"])

    def test_network_latency_uses_browser_offset_and_rejects_missing_timing(self):
        module = (
            Path(__file__).parents[1] / "acceptance/performance/polling.mjs"
        ).as_uri()
        result = subprocess.run(
            [
                "node",
                "--input-type=module",
                "-e",
                f"""
import {{networkMilliseconds}} from {json.dumps(module)};
const values=[networkMilliseconds({{startTime:1792530000000,responseEnd:125}})];
for (const value of [-1, NaN, Infinity]) {{
 try {{ networkMilliseconds({{responseEnd:value}}); values.push('accepted'); }}
 catch {{values.push('rejected');}}
}}
console.log(JSON.stringify(values));
""",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(
            json.loads(result.stdout), [125, "rejected", "rejected", "rejected"]
        )

    def test_polling_must_cover_both_boundaries_and_sustain_completions(self):
        module = (
            Path(__file__).parents[1] / "acceptance/performance/polling.mjs"
        ).as_uri()
        result = subprocess.run(
            [
                "node",
                "--input-type=module",
                "-e",
                f"""
import {{pollingCovered}} from {json.dumps(module)};
const good={{starts:400,successful_completions:400,first:61,last:659,max_gap_seconds:1.7}};
console.log(JSON.stringify([
 pollingCovered(good,60,660),
 pollingCovered({{...good,starts:2,successful_completions:2,last:63}},60,660),
 pollingCovered({{...good,first:70}},60,660),
 pollingCovered({{...good,last:640}},60,660),
 pollingCovered({{...good,successful_completions:2}},60,660),
 pollingCovered({{...good,max_gap_seconds:8}},60,660),
 pollingCovered({{...good,successful_completions:0}},60,660)
]));
""",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(
            json.loads(result.stdout), [True, False, False, False, False, False, False]
        )

    def test_separate_browser_group_is_verified_and_terminated(self):
        with tempfile.TemporaryDirectory(prefix="perf390-lifecycle-") as directory:
            child = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                start_new_session=True,
            )
            try:
                record = identity(child.pid) | {"pid": child.pid, "command": child.args}
                root = Path(directory)
                (root / "browser-owner.json").write_text(json.dumps(record))
                result = verify_browser(root)
                child.wait(timeout=2)
                self.assertEqual(result["remaining"], [])
                self.assertLess(child.returncode, 0)
            finally:
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=2)


if __name__ == "__main__":
    unittest.main()
