import copy
import json
import tempfile
import unittest
from pathlib import Path

from test_stage4 import COLLECTOR, backend, summaries

from analyze import analyze
from evidence import Evidence
from verify_evidence import validate_document, verify_analysis, verify_artifacts


class VerificationTests(unittest.TestCase):
    def test_analyzer_claims_are_backed_by_actual_same_clock_event_pairs(self):
        rows = backend(
            ["worker.dispatch", "worker.start", "worker.end", "worker.returned"]
        )
        result = analyze(rows, summaries(rows))
        verify_analysis(result, rows)
        for mutation in ("duration", "clock", "reference", "missing"):
            broken = copy.deepcopy(result)
            if mutation == "duration":
                broken["durations"][0]["ns"] = 12345
            if mutation == "clock":
                broken["durations"][0]["events"][1]["clock_id"] = "invented"
            if mutation == "reference":
                broken["durations"][0]["events"][1]["seq"] = 999
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                verify_analysis(broken, rows[:-1] if mutation == "missing" else rows)

    def test_hashed_artifact_tampering_and_missing_files_fail_verification(self):
        with tempfile.TemporaryDirectory(prefix="perf391-stage4-hash-") as tmp:
            root = Path(tmp) / "run"
            sink = Evidence(root, COLLECTOR, run="synthetic-test")
            rows = backend(["worker.start", "worker.end"])
            for row in rows:
                sink.accept(row)
            sink.summary(rows[0]["stream_id"], last_seq=2, dropped=0, complete=True)
            sink.close()
            self.assertTrue(verify_artifacts(root))
            validate_document(
                json.loads((root / "summary.json").read_text()), "summary"
            )
            (root / "integration.jsonl").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                verify_artifacts(root)

    def test_closed_analysis_schema_rejects_unavailable_zero_and_unknown_fields(self):
        rows = backend(["worker.start"])
        result = analyze(rows, summaries(rows))
        validate_document(result, "analysis")
        with self.assertRaises(ValueError):
            validate_document({**result, "invented": True}, "analysis")

    def test_fixed_adapter_fixture_is_byte_identical_and_claims_hand_checked_values(
        self,
    ):
        from stage4_fixture import fixture

        first, second = fixture(), fixture()
        self.assertEqual(first, second)
        report = json.loads(first["analysis.json"])
        self.assertEqual(
            next(d for d in report["durations"] if d["boundary"] == "worker.execution")[
                "ns"
            ],
            30,
        )
        self.assertEqual(
            next(
                d
                for d in report["durations"]
                if d["boundary"] == "polling.request_to_response"
            )["ns"],
            1000000,
        )
        self.assertEqual(report["request_joins"][0]["state"], "joined")
