import copy
import json
import unittest
from pathlib import Path

from perf391_network_evidence.analyze import analyze
from perf391_network_evidence.model import event


class StatisticsTests(unittest.TestCase):
    def test_throttle_deltas_counter_reset_and_clock_scope(self):
        def sample(ns, stat, clock="c"):
            return event(
                "resource",
                {"files": {"/cg/cpu.stat": {"value": stat, "reason": None}}},
                mono_ns=ns,
                clock_id=clock,
                seq=ns,
            )

        r = analyze(
            [
                sample(1, "nr_throttled 2\nthrottled_usec 10"),
                sample(2, "nr_throttled 5\nthrottled_usec 30"),
            ]
        )
        self.assertEqual(r["resource_deltas"][0]["delta"]["nr_throttled"], 3)
        r = analyze([sample(1, "nr_throttled 5"), sample(2, "nr_throttled 2")])
        self.assertIsNone(r["resource_deltas"][0]["delta"])

    def test_plot_log_floor_is_not_finite_deletion(self):
        c = copy.deepcopy(
            json.loads(
                (
                    Path(__file__).resolve().parents[1] / "fixtures/cases.json"
                ).read_text()
            )[0]
        )
        chart = c["events"][-1]["data"]
        chart["input_stage"] = "plot"
        chart["log_floor"] = 1
        chart["projection_input"] = copy.deepcopy(c["events"][0]["data"])
        chart["traces"]["observed"][0] = 1
        self.assertEqual(
            analyze(c["events"])["charts"][0]["classification"], "complete"
        )

    def test_scrape_jitter_does_not_become_acquisition_jitter(self):
        rows = [
            event(
                "scrape",
                {
                    "series": "x",
                    "timestamp": t,
                    "value": 0,
                    "state": "finite",
                    "segment": "measured",
                },
                seq=i,
            )
            for i, t in enumerate([100, 101.1, 102])
        ]
        result = analyze(rows)
        self.assertAlmostEqual(
            result["scrape_timing"]["x/measured"]["signed_error_seconds"]["max"], 0.1
        )
        self.assertEqual(
            result["timing_distributions_ns"]["producer_acquisition"]["count"], 0
        )
