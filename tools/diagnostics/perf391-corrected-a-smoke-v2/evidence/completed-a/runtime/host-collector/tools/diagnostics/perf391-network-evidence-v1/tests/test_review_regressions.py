import copy
import json
import unittest
from pathlib import Path

from perf391_network_evidence.analyze import analyze
from perf391_network_evidence.model import event


class ReviewRegressions(unittest.TestCase):
    def base(self):
        return copy.deepcopy(
            json.loads(
                (
                    Path(__file__).resolve().parents[1] / "fixtures/cases.json"
                ).read_text()
            )[0]["events"]
        )

    def test_incomplete_store_and_stale_sample_provenance_are_unknown(self):
        rows = self.base()
        rows[1]["data"]["sample_timestamps"] = [99, 99, 99, 103]
        rows = [
            r for r in rows if r["kind"] != "scrape" or r["data"]["timestamp"] == 103
        ]
        c = analyze(rows)["charts"][0]
        self.assertEqual(c["classification"], "unknown")
        self.assertIn("stored_window_coverage", c["unavailable"])
        self.assertIn("evaluation_sample_provenance", c["unavailable"])

    def test_actual_plot_without_retained_input_is_unknown(self):
        rows = self.base()
        c = rows[-1]["data"]
        c["input_stage"] = "plot"
        c["times"].insert(0, 99)
        for name, values in c["traces"].items():
            values.insert(0, 1 if name == "observed" else None)
        result = analyze(rows)["charts"][0]
        self.assertEqual(result["classification"], "unknown")
        self.assertIn("retained_projection_input", result["unavailable"])

    def test_summaries_are_required_for_every_stream(self):
        rows = self.base()
        rows.append(
            event(
                "summary",
                {
                    "dropped_events": 0,
                    "dropped_bodies": 0,
                    "written_bytes": 0,
                    "write_wall_ns": "0",
                    "reason": "fixture",
                },
                run_id=rows[0]["run_id"],
                stream_id="other",
            )
        )
        result = analyze(rows)
        self.assertIsNone(result["dropped"])
        self.assertIn("missing_stream_summary", result["issues"])

    def test_segment_mismatch_never_joins(self):
        rows = self.base()
        rows[0]["data"]["segment"] = "seeded"
        self.assertEqual(analyze(rows)["charts"][0]["classification"], "unknown")

    def test_unrelated_evaluation_cannot_prove_api_defect(self):
        rows = self.base()
        rows[1]["data"]["request_id"] = "unrelated"
        rows[1]["data"]["values"][0] = 123
        c = analyze(rows)["charts"][0]
        self.assertEqual(c["classification"], "unknown")
        self.assertIn("exact_evaluation_grid", c["unavailable"])

    def test_removed_event_with_zero_drop_summary_is_detected(self):
        rows = self.base()
        last = rows[-1]["seq"]
        rows.append(
            event(
                "summary",
                {
                    "dropped_events": 0,
                    "dropped_bodies": 0,
                    "written_bytes": None,
                    "write_wall_ns": None,
                    "reason": "fixture",
                },
                run_id=rows[0]["run_id"],
                stream_id="fixture",
                seq=last + 1,
            )
        )
        del rows[2]
        result = analyze(rows)
        self.assertIn("unaccounted_sequence_gap", result["issues"])
        self.assertIsNone(result["dropped"])
