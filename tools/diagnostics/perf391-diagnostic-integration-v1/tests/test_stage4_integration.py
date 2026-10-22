"""Real adapter-shaped artifact joins and loss accounting, including schema closure."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from test_stage4 import COLLECTOR, backend, summaries

from analyze import analyze
from evidence import Evidence
from integration import Integration


def wrapped(phase, detail, seq=1):
    raw = {
        "run": "synthetic-test",
        "stream": "synthetic-test/p/doc",
        "clock": "browser/p/doc",
        "seq": seq,
        "monotonic_ms": 1.25 * seq,
        "phase": phase,
        "op": "synthetic-test/p/doc/r1",
        "outcome": "ok",
        "detail": detail,
    }
    body = json.dumps(raw, separators=(",", ":")).encode()
    row = {
        "origin": "browser",
        "event": {k: v for k, v in raw.items() if k != "detail"},
        "sha256": hashlib.sha256(body).hexdigest(),
        "artifact": "full",
        "snapshots": {},
    }
    artifacts = {"full": body}
    for name in ("retained", "projection", "plot"):
        if name in detail:
            data = json.dumps(detail[name], separators=(",", ":")).encode()
            artifacts[name] = data
            row["snapshots"][name] = {
                "sha256": hashlib.sha256(data).hexdigest(),
                "artifact": name,
            }
    return row, artifacts


class AdapterJoinTests(unittest.TestCase):
    def test_history_and_actual_committed_chart_have_independent_hashed_inputs(self):
        history = {
            "window_seconds": 60,
            "start_timestamp_seconds": 1,
            "end_timestamp_seconds": 3,
            "step_seconds": 1,
            "series": {"latency": [[1, 2], [2, 3], [3, 4]]},
        }
        with tempfile.TemporaryDirectory(prefix="perf391-stage4-join-") as tmp:
            sink = Evidence(Path(tmp) / "run", COLLECTOR, run="synthetic-test")
            owner = Integration(
                sink,
                role="C",
                run="synthetic-test",
                module_hashes={"projection": "a" * 64},
            )
            row, artifacts = wrapped(
                "app.parse_available",
                {"bundle": "o1", "metric": "latency", "history": history},
            )
            owner.browser_record(row, load=artifacts.__getitem__)
            detail = {
                "accepted": "o1",
                "acceptedRequest": "synthetic-test/p/doc/r1",
                "metric": "latency",
                "commit": "p/c1",
                "retained": history,
                "projection": {"times": [1, 2, 3]},
                "logFloor": 1,
                "plot": {
                    "data": [
                        [1, 2, 3],
                        [None, None, None],
                        [None, None, None],
                        [None, None, None],
                        [2, 3, 4],
                    ],
                    "scales": {"x": {"min": 1, "max": 3}},
                },
            }
            row, artifacts = wrapped("plot.commit", detail, seq=2)
            owner.browser_record(row, load=artifacts.__getitem__)
            owner.finish_browser({"closed": True, "failed": False, "lost": 0})
            self.assertTrue(sink.close()["complete"])
            v1 = [
                json.loads(line)
                for line in (Path(tmp) / "run/v1/events.jsonl").read_text().splitlines()
            ]
            for event in v1:
                COLLECTOR.model.validate(event)
            chart = next(e for e in v1 if e["kind"] == "chart")["data"]
            self.assertEqual(chart["traces"]["observed"], [2, 3, 4])
            self.assertIsNone(chart["visible_gaps"])
            self.assertEqual(chart["projection_input"]["series"], history["series"])
            self.assertEqual(len(list((Path(tmp) / "run/v1/bodies").glob("*"))), 2)

    def test_wrong_artifact_and_incomplete_browser_summary_never_qualify(self):
        with tempfile.TemporaryDirectory(prefix="perf391-stage4-badjoin-") as tmp:
            sink = Evidence(Path(tmp) / "run", COLLECTOR, run="synthetic-test")
            owner = Integration(sink, role="A", run="synthetic-test")
            row, artifacts = wrapped("app.parse_available", {"bundle": "o1"})
            with self.assertRaises(ValueError):
                owner.browser_record(row, load=lambda _: b"wrong")
            owner.browser_record(row, load=artifacts.__getitem__)
            owner.finish_browser(
                {"closed": True, "failed": False, "lost": 0, "bindingJobs": 1}
            )
            self.assertFalse(sink.close()["complete"])

    def test_restart_new_stream_is_visible_and_never_pairs_across_processes(self):
        rows = backend(["worker.dispatch", "worker.start"])
        restarted = backend(["worker.end", "worker.returned"])
        for row in restarted:
            row.update(
                process_uuid="22222222-2222-4222-8222-222222222222",
                clock_id="restart-clock",
                stream_id="restart",
                process_start_id="restart",
            )
        result = analyze(rows + restarted, summaries(rows + restarted))
        self.assertTrue(result["integrity"]["complete"])
        self.assertTrue(
            all(
                d["ns"] is None
                for d in result["durations"]
                if d["boundary"] == "worker.execution"
            )
        )


class EmitterIdentityTests(unittest.TestCase):
    def test_node_clock_metadata_is_supplied_by_node_not_python_owner(self):
        with tempfile.TemporaryDirectory(prefix="perf391-stage4-node-id-") as tmp:
            sink = Evidence(Path(tmp) / "run", COLLECTOR, run="synthetic-test")
            owner = Integration(sink, role="C", run="synthetic-test")
            row = {
                "phase": "browser.request",
                "host_received_ns": "123",
                "requestId": "synthetic-test/p/doc/r1",
            }
            with self.assertRaises(ValueError):
                owner.browser_record(row)
            node = {
                "process_uuid": "33333333-3333-4333-8333-333333333333",
                "pid": 1234,
                "process_start_id": "node-start",
                "clock_id": "node-clock",
            }
            owner.browser_record({**row, "host_identity": node})
            sink.drain()
            owner.finish_browser({"closed": True, "failed": False, "lost": 0})
            sink.close()
            event = json.loads(
                (Path(tmp) / "run/integration.jsonl").read_text().splitlines()[0]
            )
            self.assertEqual(event["pid"], 1234)
            self.assertEqual(event["clock_id"], "node-clock")
            self.assertIsNone(event["tid"])

    def test_observer_node_and_paint_clocks_preserve_domains_and_complete_pairs(self):
        node = {
            "process_uuid": "33333333-3333-4333-8333-333333333333",
            "pid": 1234,
            "process_start_id": "node-start",
            "clock_id": "node-clock",
        }
        with tempfile.TemporaryDirectory(prefix="perf391-stage4-sourcejoin-") as tmp:
            sink = Evidence(Path(tmp) / "run", COLLECTOR, run="synthetic-test")
            owner = Integration(sink, role="C", run="synthetic-test")
            for i, phase in enumerate(
                (
                    "observer.scheduled",
                    "observer.wake",
                    "observer.send",
                    "observer.headers",
                    "observer.received",
                    "observer.parsed",
                    "observer.written",
                    "observer.record_complete",
                )
            ):
                owner.source_record(
                    {
                        "host_identity": node,
                        "event": {
                            "op": "synthetic-test/source/1",
                            "phase": phase,
                            "mono_ns": str(100 + i * 10),
                            "seq": i + 1,
                        },
                    }
                )
            owner.finish_source({"closed": True, "failed": False})
            owner.browser_record(
                {
                    "phase": "paint.artifact",
                    "host_identity": node,
                    "host_received_ns": "300",
                    "started_ns": "200",
                    "received_ns": "250",
                    "outcome": "ok",
                }
            )
            owner.finish_browser({"closed": True, "failed": False, "lost": 0})
            sink.close()
            rows = [
                json.loads(line)
                for line in (Path(tmp) / "run/integration.jsonl")
                .read_text()
                .splitlines()
            ]
            report = analyze(
                rows,
                json.loads((Path(tmp) / "run/summary.json").read_text())["streams"],
            )
            self.assertTrue(report["integrity"]["complete"])
            self.assertEqual(
                next(
                    d
                    for d in report["durations"]
                    if d["boundary"] == "observer.late_wake"
                )["ns"],
                10,
            )
            self.assertEqual(
                next(
                    d
                    for d in report["durations"]
                    if d["boundary"] == "presentation.capture"
                )["ns"],
                50,
            )
