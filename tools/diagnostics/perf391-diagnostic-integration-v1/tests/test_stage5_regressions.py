"""Independent Stage 4 recheck: unavailable chart input still requires integrity."""

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from test_stage4 import COLLECTOR, summaries
from test_stage4_integration import wrapped

from analyze import analyze
from evidence import BrowserProjection, Evidence
from integration import Integration
from verify_evidence import verify_analysis


class Stage5RegressionTests(unittest.TestCase):
    def test_snapshot_missing_without_module_hashes_still_fails_integrity(self):
        row, artifacts = wrapped("plot.commit", {"retained": {"fixture": True}})
        row["snapshots"]["retained"]["artifact"] = "missing"
        with tempfile.TemporaryDirectory(prefix="perf391-stage5-regression-") as tmp:
            sink = Evidence(Path(tmp) / "evidence", COLLECTOR, run="synthetic-test")
            adapter = Integration(sink, role="C", run="synthetic-test")
            try:
                with self.assertRaises(ValueError):
                    adapter.browser_record(row, load=artifacts.__getitem__)
                self.assertFalse(sink.close()["complete"])
            finally:
                if not sink.closed:
                    sink.close()

    def test_snapshot_is_retained_when_chart_capability_is_unavailable(self):
        row, artifacts = wrapped("plot.commit", {"retained": {"fixture": True}})
        digest = hashlib.sha256(artifacts["retained"]).hexdigest()
        with tempfile.TemporaryDirectory(prefix="perf391-stage5-regression-") as tmp:
            sink = Evidence(Path(tmp) / "evidence", COLLECTOR, run="synthetic-test")
            adapter = Integration(sink, role="C", run="synthetic-test")
            try:
                adapter.browser_record(row, load=artifacts.__getitem__)
                adapter.finish_browser({"closed": True, "failed": False, "lost": 0})
                self.assertTrue(sink.close()["complete"])
                self.assertTrue((sink.root / "v1/bodies" / (digest + ".bin")).exists())
            finally:
                if not sink.closed:
                    sink.close()

    def test_verifier_rejects_duration_between_distinct_plot_tokens(self):
        projection = BrowserProjection("C", "synthetic-test", "p")
        rows = []
        for seq, (token, phase) in enumerate(
            [
                ("plot-a", "history.retained"),
                ("plot-a", "plot.commit"),
                ("plot-b", "history.retained"),
                ("plot-b", "plot.commit"),
            ],
            1,
        ):
            rows.append(
                projection.event(
                    {
                        "run": "synthetic-test",
                        "stream": "synthetic-test/p/doc",
                        "clock": "browser/p/doc",
                        "seq": seq,
                        "monotonic_ms": seq,
                        "phase": phase,
                        "op": "synthetic-test/p/doc/r1",
                        "outcome": "ok",
                        "detail": {"commit": token},
                    },
                    artifact={"state": "available", "sha256": "a" * 64},
                )
            )
        report = analyze(rows, summaries(rows))
        verify_analysis(report, rows)
        forged = copy.deepcopy(report)
        claim = next(
            d for d in forged["durations"] if d["boundary"] == "chart_input.commit"
        )
        claim.update(
            ns=3000000,
            thread_cpu_ns=None,
            reason=None,
            events=[
                {k: e[k] for k in ("stream_id", "seq", "phase", "clock_id", "mono_ns")}
                for e in (rows[0], rows[3])
            ],
        )
        with self.assertRaises(ValueError):
            verify_analysis(forged, rows)
